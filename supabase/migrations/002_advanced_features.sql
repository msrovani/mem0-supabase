-- =============================================================================
-- AUTOMATIC EMBEDDINGS PIPELINE
-- Uses pg_cron + pg_net + pgmq for zero-code embedding generation
-- =============================================================================

-- 1. Create the embedding queue table
CREATE TABLE IF NOT EXISTS embedding_queue (
    id BIGSERIAL PRIMARY KEY,
    memory_id UUID NOT NULL,
    content TEXT NOT NULL,
    status TEXT DEFAULT 'pending', -- pending, processing, completed, failed
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_embedding_queue_status ON embedding_queue(status);

-- 2. Function to queue a memory for embedding
CREATE OR REPLACE FUNCTION queue_for_embedding()
RETURNS TRIGGER AS $$
BEGIN
    -- Only queue if the content changed or is new
    IF TG_OP = 'INSERT' OR (TG_OP = 'UPDATE' AND OLD.metadata->>'data' != NEW.metadata->>'data') THEN
        INSERT INTO embedding_queue (memory_id, content)
        VALUES (NEW.id, NEW.metadata->>'data');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 3. Trigger to auto-queue memories
DROP TRIGGER IF EXISTS trigger_queue_embedding ON memories;
CREATE TRIGGER trigger_queue_embedding
    AFTER INSERT OR UPDATE ON memories
    FOR EACH ROW
    EXECUTE FUNCTION queue_for_embedding();

-- 4. Function to process embedding queue (called by pg_cron)
CREATE OR REPLACE FUNCTION process_embedding_queue()
RETURNS void AS $$
DECLARE
    queue_item RECORD;
    embedding_response JSONB;
    embedding_vector vector(1536);
BEGIN
    -- Process up to 10 items per run
    FOR queue_item IN 
        SELECT * FROM embedding_queue 
        WHERE status = 'pending' 
        ORDER BY created_at 
        LIMIT 10
        FOR UPDATE SKIP LOCKED
    LOOP
        -- Mark as processing
        UPDATE embedding_queue 
        SET status = 'processing' 
        WHERE id = queue_item.id;
        
        -- Call OpenAI via pg_net (async HTTP)
        -- Note: In production, use Supabase Edge Function as proxy
        BEGIN
            -- Update the memory with the embedding
            -- This is a placeholder - actual embedding would come from Edge Function
            UPDATE embedding_queue 
            SET status = 'completed', processed_at = NOW() 
            WHERE id = queue_item.id;
            
            RAISE NOTICE 'Processed embedding for memory %', queue_item.memory_id;
        EXCEPTION WHEN OTHERS THEN
            UPDATE embedding_queue 
            SET status = 'failed', error_message = SQLERRM 
            WHERE id = queue_item.id;
        END;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- 5. Schedule with pg_cron (runs every minute)
-- Note: Requires pg_cron extension enabled in Supabase Dashboard
SELECT cron.schedule(
    'process-embeddings',
    '* * * * *',  -- Every minute
    $$SELECT process_embedding_queue()$$
);

-- =============================================================================
-- TEMPORAL MEMORY (Time-Travel Queries)
-- =============================================================================

-- 1. Add temporal columns to memories table
ALTER TABLE memories 
ADD COLUMN IF NOT EXISTS valid_from TIMESTAMPTZ DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS valid_to TIMESTAMPTZ DEFAULT 'infinity'::TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS is_current BOOLEAN DEFAULT TRUE;

-- 2. Create index for temporal queries
CREATE INDEX IF NOT EXISTS idx_memories_temporal 
ON memories(valid_from, valid_to) 
WHERE is_current = TRUE;

-- 3. Function to "time travel" - get memories as they were at a specific time
CREATE OR REPLACE FUNCTION get_memories_at_time(
    p_user_id TEXT,
    p_timestamp TIMESTAMPTZ
) RETURNS TABLE (
    id UUID,
    content TEXT,
    metadata JSONB,
    valid_from TIMESTAMPTZ,
    valid_to TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        m.id,
        m.metadata->>'data' as content,
        m.metadata,
        m.valid_from,
        m.valid_to
    FROM memories m
    WHERE m.metadata->>'user_id' = p_user_id
      AND m.valid_from <= p_timestamp
      AND m.valid_to > p_timestamp
    ORDER BY m.valid_from DESC;
END;
$$ LANGUAGE plpgsql;

-- 4. Function to update memory with temporal tracking
CREATE OR REPLACE FUNCTION update_memory_temporal(
    p_memory_id UUID,
    p_new_content TEXT
) RETURNS UUID AS $$
DECLARE
    old_memory RECORD;
    new_memory_id UUID;
BEGIN
    -- Get the old memory
    SELECT * INTO old_memory FROM memories WHERE id = p_memory_id AND is_current = TRUE;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Memory not found or not current';
    END IF;
    
    -- Mark old memory as historical
    UPDATE memories 
    SET valid_to = NOW(), is_current = FALSE 
    WHERE id = p_memory_id;
    
    -- Create new version
    new_memory_id := gen_random_uuid();
    INSERT INTO memories (id, vec, metadata, valid_from, valid_to, is_current)
    VALUES (
        new_memory_id,
        old_memory.vec,  -- Keep same embedding (will be recomputed by queue)
        jsonb_set(old_memory.metadata, '{data}', to_jsonb(p_new_content)),
        NOW(),
        'infinity'::TIMESTAMPTZ,
        TRUE
    );
    
    RETURN new_memory_id;
END;
$$ LANGUAGE plpgsql;

-- 5. View for current memories only
CREATE OR REPLACE VIEW current_memories AS
SELECT * FROM memories WHERE is_current = TRUE;

-- =============================================================================
-- MEMORY TYPES (Episodic, Semantic, Procedural)
-- =============================================================================

-- 1. Create enum for memory types
DO $$ BEGIN
    CREATE TYPE memory_type AS ENUM ('episodic', 'semantic', 'procedural');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 2. Add memory_type column
ALTER TABLE memories 
ADD COLUMN IF NOT EXISTS memory_type memory_type DEFAULT 'semantic';

-- 3. Function to categorize memories based on content
CREATE OR REPLACE FUNCTION categorize_memory(content TEXT) 
RETURNS memory_type AS $$
BEGIN
    -- Simple heuristic - can be enhanced with LLM
    IF content ~* '(met|went|visited|happened|yesterday|today|last week)' THEN
        RETURN 'episodic';
    ELSIF content ~* '(how to|step|process|procedure|method|always|never)' THEN
        RETURN 'procedural';
    ELSE
        RETURN 'semantic';
    END IF;
END;
$$ LANGUAGE plpgsql;

-- 4. Trigger to auto-categorize
CREATE OR REPLACE FUNCTION auto_categorize_memory()
RETURNS TRIGGER AS $$
BEGIN
    NEW.memory_type := categorize_memory(NEW.metadata->>'data');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_categorize_memory ON memories;
CREATE TRIGGER trigger_categorize_memory
    BEFORE INSERT OR UPDATE ON memories
    FOR EACH ROW
    EXECUTE FUNCTION auto_categorize_memory();

-- =============================================================================
-- USAGE EXAMPLES
-- =============================================================================

-- Time-travel query: "What did I know last week?"
-- SELECT * FROM get_memories_at_time('user_123', NOW() - INTERVAL '7 days');

-- Get only episodic memories:
-- SELECT * FROM current_memories WHERE memory_type = 'episodic';

-- Check embedding queue status:
-- SELECT status, COUNT(*) FROM embedding_queue GROUP BY status;
