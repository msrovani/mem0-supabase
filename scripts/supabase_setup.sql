-- Enable necessary extensions
create extension if not exists vector with schema extensions;
create extension if not exists pg_trgm with schema extensions;
create extension if not exists "uuid-ossp";

-- Innovation: Security (Vault)
create extension if not exists supabase_vault with schema vault;

-- Innovation: Data Federation (Wrappers)
create extension if not exists wrappers with schema extensions;

-- Innovation: Autonomous (pg_net + pg_cron)
create extension if not exists pg_net with schema extensions;
create extension if not exists pg_cron with schema extensions;

-- =========================================
-- 1. Hybrid Search (Vector + Full-Text)
-- =========================================

create or replace function match_memories_hybrid(
  query_embedding vector(1536),
  match_threshold float,
  match_count int,
  query_text text,
  full_text_weight float default 1.0,
  semantic_weight float default 1.0,
  rrf_k int default 60,
  filter jsonb default '{}'::jsonb
)
returns table (
  id varchar,
  payload jsonb,
  similarity float
)
language plpgsql
as $$
begin
  return query
  with vector_search as (
    select
      id,
      row_number() over (order by vec <#> query_embedding) as rank_ix,
      1 - (vec <=> query_embedding) as score
    from
      vecs.memories
    where
      metadata @> filter
    order by
      vec <#> query_embedding
    limit match_count * 2
  ),
  keyword_search as (
    select
      id,
      row_number() over (order by ts_rank_cd(to_tsvector('english', cast(metadata->>'data' as text)), plainto_tsquery('english', query_text)) desc) as rank_ix,
      ts_rank_cd(to_tsvector('english', cast(metadata->>'data' as text)), plainto_tsquery('english', query_text)) as score
    from
      vecs.memories
    where
      to_tsvector('english', cast(metadata->>'data' as text)) @@ plainto_tsquery('english', query_text)
      and metadata @> filter
    limit match_count * 2
  )
  select
    coalesce(v.id, k.id) as id,
    (select metadata from vecs.memories where id = coalesce(v.id, k.id)) as payload,
    (
      coalesce(1.0 / (rrf_k + v.rank_ix), 0.0) * semantic_weight +
      coalesce(1.0 / (rrf_k + k.rank_ix), 0.0) * full_text_weight
    ) as similarity
  from
    vector_search v
  full outer join
    keyword_search k on v.id = k.id
  order by
    similarity desc
  limit match_count;
end;
$$;

-- =========================================
-- 2. Graph-on-Postgres (Nodes & Edges)
-- =========================================

create table if not exists nodes (
    id uuid primary key default uuid_generate_v4(),
    name text not null,
    label text,
    properties jsonb default '{}'::jsonb,
    created_at timestamptz default now(),
    unique(name, label)
);

create table if not exists edges (
    id uuid primary key default uuid_generate_v4(),
    source_node_id uuid references nodes(id) on delete cascade,
    target_node_id uuid references nodes(id) on delete cascade,
    relation text not null,
    properties jsonb default '{}'::jsonb,
    created_at timestamptz default now(),
    unique(source_node_id, target_node_id, relation)
);

create index if not exists idx_nodes_name on nodes(name);
create index if not exists idx_nodes_label on nodes(label);
create index if not exists idx_edges_source on edges(source_node_id);
create index if not exists idx_edges_target on edges(target_node_id);
create index if not exists idx_edges_relation on edges(relation);

-- 2.1 RPC for Simple Graph Traversal
create or replace function match_related_nodes(
    node_name text,
    recursive_depth int default 1
)
returns table (
    source text,
    relation text,
    target text
)
language plpgsql
as $$
begin
    return query
    select n1.name as source, e.relation, n2.name as target
    from nodes n1
    join edges e on n1.id = e.source_node_id
    join nodes n2 on e.target_node_id = n2.id
    where n1.name = node_name
    union
    select n1.name as source, e.relation, n2.name as target
    from nodes n1
    join edges e on n1.id = e.target_node_id
    join nodes n2 on e.source_node_id = n2.id
    where n1.name = node_name;
end;
$$;

-- =========================================
-- 3. Security (RLS)
-- =========================================

alter table vecs.memories enable row level security;
alter table nodes enable row level security;
alter table edges enable row level security;

-- We assume 'vecs.memories' exists. If not, vecs creates it on first add.
-- These policies use metadata->>'user_id' for multi-tenancy.

create policy "Users can see their own memories" on vecs.memories for select using (metadata->>'user_id' = auth.uid()::text or auth.role() = 'service_role');
create policy "Users can insert their own memories" on vecs.memories for insert with check (metadata->>'user_id' = auth.uid()::text or auth.role() = 'service_role');
create policy "Users can update their own memories" on vecs.memories for update using (metadata->>'user_id' = auth.uid()::text or auth.role() = 'service_role');
create policy "Users can delete their own memories" on vecs.memories for delete using (metadata->>'user_id' = auth.uid()::text or auth.role() = 'service_role');

create policy "Users can see their own nodes" on nodes for select using (properties->>'user_id' = auth.uid()::text or auth.role() = 'service_role');
create policy "Users can insert their own nodes" on nodes for insert with check (properties->>'user_id' = auth.uid()::text or auth.role() = 'service_role');
create policy "Users can update their own nodes" on nodes for update using (properties->>'user_id' = auth.uid()::text or auth.role() = 'service_role');
create policy "Users can delete their own nodes" on nodes for delete using (properties->>'user_id' = auth.uid()::text or auth.role() = 'service_role');

create policy "Users can see their own edges" on edges for select using (properties->>'user_id' = auth.uid()::text or auth.role() = 'service_role');
create policy "Users can insert their own edges" on edges for insert with check (properties->>'user_id' = auth.uid()::text or auth.role() = 'service_role');
create policy "Users can update their own edges" on edges for update using (properties->>'user_id' = auth.uid()::text or auth.role() = 'service_role');
create policy "Users can delete their own edges" on edges for delete using (properties->>'user_id' = auth.uid()::text or auth.role() = 'service_role');

-- =========================================
-- 4. History (Memory Audit Log)
-- =========================================

create table if not exists history (
    id           uuid primary key default uuid_generate_v4(),
    memory_id    text,
    old_memory   text,
    new_memory   text,
    event        text,
    created_at   timestamptz default now(),
    updated_at   timestamptz default now(),
    is_deleted   boolean default false,
    actor_id     text,
    role         text,
    user_id      text
);

create index if not exists idx_history_memory_id on history(memory_id);
alter table history enable row level security;

create policy "Users can see their own history" on history for select using (user_id = auth.uid()::text or auth.role() = 'service_role');
create policy "Users can insert their own history" on history for insert with check (user_id = auth.uid()::text or auth.role() = 'service_role');
create policy "Users can update their own history" on history for update using (user_id = auth.uid()::text or auth.role() = 'service_role');

-- =========================================
-- 5. Innovation: Multimodal Storage
-- =========================================

insert into storage.buckets (id, name, public)
values ('mem0_artifacts', 'mem0_artifacts', true)
on conflict (id) do nothing;

create policy "Users can upload their own artifacts"
on storage.objects for insert
with check ( bucket_id = 'mem0_artifacts' and auth.role() = 'service_role' ); 

create policy "Public can view artifacts"
on storage.objects for select
using ( bucket_id = 'mem0_artifacts' );

-- =========================================
-- 6. Innovation: Wrappers & Vault Helper
-- =========================================

create or replace function set_secret(name text, secret text, description text default '')
returns void
language plpgsql
security definer
as $$
begin
    if exists (select 1 from information_schema.tables where table_schema = 'vault' and table_name = 'secrets') then
        perform vault.create_secret(secret, name, description);
    end if;
end;
$$;

create or replace function get_secret(name text)
returns text
language plpgsql
security definer
as $$
declare
    secret_value text;
begin
    if exists (select 1 from information_schema.tables where table_schema = 'vault' and table_name = 'secrets') then
        select decrypted_secret into secret_value from vault.decrypted_secrets where name = get_secret.name limit 1;
        return secret_value;
    end if;
    return null;
end;
$$;

-- =========================================
-- 7. Innovation: Semantic Caching
-- =========================================

create table if not exists semantic_cache (
    id           uuid primary key default uuid_generate_v4(),
    query_text   text not null,
    embedding    vector(1536), -- Default OpenAI size
    response_text text not null,
    metadata     jsonb default '{}'::jsonb,
    created_at   timestamptz default now()
);

create index if not exists idx_semantic_cache_embedding on semantic_cache using hnsw (embedding vector_cosine_ops);

create or replace function match_semantic_cache(
  query_embedding vector(1536),
  match_threshold float default 0.95,
  match_count int default 1
)
returns table (
  response_text text,
  similarity float
)
language plpgsql
as $$
begin
  return query
  select
    c.response_text,
    1 - (c.embedding <=> query_embedding) as similarity
  from
    semantic_cache c
  where
    1 - (c.embedding <=> query_embedding) > match_threshold
  order by
    c.embedding <=> query_embedding
  limit match_count;
end;
$$;

-- =========================================
-- 8. Advanced: Auto Embeddings Queue
-- =========================================

create table if not exists embedding_queue (
    id bigserial primary key,
    memory_id uuid not null,
    content text not null,
    status text default 'pending',
    created_at timestamptz default now(),
    processed_at timestamptz,
    error_message text
);

create index if not exists idx_embedding_queue_status on embedding_queue(status);

-- =========================================
-- 9. Advanced: Temporal Memory (Time-Travel)
-- =========================================

alter table vecs.memories 
add column if not exists valid_from timestamptz default now(),
add column if not exists valid_to timestamptz default 'infinity'::timestamptz,
add column if not exists is_current boolean default true,
add column if not exists reinforcement_count int default 1,
add column if not exists importance_score float default 1.0,
add column if not exists is_flashbulb boolean default false;

create index if not exists idx_memories_temporal 
on vecs.memories(valid_from, valid_to) 
where is_current = true;

create index if not exists idx_memories_flashbulb
on vecs.memories(is_flashbulb)
where is_flashbulb = true;

create index if not exists idx_memories_importance
on vecs.memories(importance_score);

-- SSR: Trigger to sync metadata to optimized columns
create or replace function vecs.sync_memory_metadata_to_columns()
returns trigger as $$
begin
    if (new.payload ? 'is_flashbulb') then
        new.is_flashbulb := (new.payload->>'is_flashbulb')::boolean;
    end if;
    if (new.payload ? 'reinforcement_count') then
        new.reinforcement_count := (new.payload->>'reinforcement_count')::int;
    end if;
    if (new.payload ? 'importance_score') then
        new.importance_score := (new.payload->>'importance_score')::float;
    end if;
    return new;
end;
$$ language plpgsql;

drop trigger if exists trigger_sync_memory_metadata on vecs.memories;
create trigger trigger_sync_memory_metadata
before insert or update of payload on vecs.memories
for each row execute function vecs.sync_memory_metadata_to_columns();

-- SSR: Enable Realtime for the memories table
alter publication supabase_realtime add table vecs.memories;

create or replace function get_memories_at_time(
    p_user_id text,
    p_timestamp timestamptz
) returns table (
    id uuid,
    content text,
    metadata jsonb,
    valid_from timestamptz,
    valid_to timestamptz
) as $$
begin
    return query
    select 
        m.id,
        m.metadata->>'data' as content,
        m.metadata,
        m.valid_from,
        m.valid_to
    from vecs.memories m
    where m.metadata->>'user_id' = p_user_id
      and m.valid_from <= p_timestamp
      and m.valid_to > p_timestamp
    order by m.valid_from desc;
end;
$$ language plpgsql;

-- =========================================
-- 10. Advanced: LangGraph Checkpoints
-- =========================================

create table if not exists langgraph_checkpoints (
    id serial primary key,
    thread_id text not null,
    checkpoint_id text not null,
    parent_checkpoint_id text,
    checkpoint jsonb not null,
    metadata jsonb default '{}',
    created_at timestamptz default now(),
    unique(thread_id, checkpoint_id)
);

create index if not exists idx_checkpoints_thread on langgraph_checkpoints(thread_id);

-- =========================================
-- 11. Advanced: Memory Types
-- =========================================

do $$ begin
    create type memory_type as enum ('episodic', 'semantic', 'procedural', 'identity');
exception
    when duplicate_object then null;
end $$;

alter table vecs.memories 
add column if not exists memory_type memory_type default 'semantic';

-- =========================================
-- 12. SSR Phase 3: Recursive Knowledge Distillation (Dreaming Logic)
-- =========================================

-- Function to find clusters of similar memories
create or replace function vecs.find_memory_clusters(p_threshold float default 0.95)
returns table (
    cluster_representative_id uuid,
    member_ids uuid[],
    cluster_size int
) as $$
begin
    return query
    with similarity_pairs as (
        -- Find pairs of memories that are highly similar
        select 
            m1.id as id1,
            m2.id as id2,
            1 - (m1.vec <=> m2.vec) as similarity
        from vecs.memories m1
        join vecs.memories m2 on m1.id < m2.id
        where 1 - (m1.vec <=> m2.vec) > p_threshold
          and m1.payload->>'user_id' = m2.payload->>'user_id' -- Must belong to same user
    ),
    clusters as (
        -- Group by the first ID in the pair (simplistic clustering)
        select 
            id1 as rep_id,
            array_agg(id2) as members,
            count(*) + 1 as size
        from similarity_pairs
        group by id1
    )
    select 
        rep_id::uuid,
        members::uuid[],
        size::int
    from clusters
    where size > 1;
end;
$$ language plpgsql;

-- Function to consolidate a cluster (intended to be called by Edge Function after LLM summary)
create or replace function vecs.consolidate_memories(
    p_primary_id uuid,
    p_to_remove_ids uuid[],
    p_new_content text
) returns void as $$
begin
    -- 1. Update primary memory with new content (summary)
    update vecs.memories
    set payload = jsonb_set(payload, '{data}', to_jsonb(p_new_content)),
        updated_at = now(),
        reinforcement_count = reinforcement_count + array_length(p_to_remove_ids, 1)
    where id = p_primary_id;

    -- 2. Delete the redundant memories
    delete from vecs.memories
    where id = any(p_to_remove_ids);
end;
$$ language plpgsql;

-- Layer 12 Index: Meta-Identity Filtering
create index if not exists idx_memories_type on vecs.memories(memory_type);

-- =========================================
-- 13. Layer 5: Lifecycle (Forgetting Curve)
-- =========================================

create or replace function vecs.decay_memory_importance(p_decay_factor float default 0.95)
returns void as $$
begin
    update vecs.memories
    set importance_score = importance_score * p_decay_factor,
        payload = jsonb_set(payload, '{importance_score}', to_jsonb(importance_score * p_decay_factor))
    where importance_score > 0.1
      and updated_at < now() - interval '1 day';
end;
$$ language plpgsql;

-- =========================================
-- 14. Layer 7: Nexus (Enterprise Promotion)
-- =========================================

create table if not exists vecs.memory_proposals (
    id uuid primary key default uuid_generate_v4(),
    memory_id text not null,
    proposed_by text,
    org_id text,
    team_id text,
    target_visibility text default 'team',
    status text default 'pending',
    created_at timestamptz default now()
);

create or replace function vecs.approve_memory_proposal(p_proposal_id uuid)
returns void as $$
declare
    v_memory_id text;
    v_visibility text;
begin
    select memory_id, target_visibility into v_memory_id, v_visibility
    from vecs.memory_proposals where id = p_proposal_id;

    if v_memory_id is not None then
        update vecs.memories
        set payload = jsonb_set(payload, '{visibility}', to_jsonb(v_visibility))
        where id = v_memory_id;

        update vecs.memory_proposals
        set status = 'approved'
        where id = p_proposal_id;
    end if;
end;
$$ language plpgsql;
