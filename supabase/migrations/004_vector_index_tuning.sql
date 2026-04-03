-- Migration 004: Vector Index Tuning (#7)
-- Optimizes pgvector for production-scale search (1M+ vectors)
--
-- HNSW index: 10-50x faster than ivfflat for recall@10
-- Supports cosine, l2, and ip distance metrics
--
-- Apply: psql -f 004_vector_index_tuning.sql
-- Rollback: DROP INDEX IF EXISTS idx_memories_embedding_hnsw;

-- Create HNSW index on memories table for vector similarity search
-- m=16: 16 connections per node (higher = better recall, more memory)
-- ef_construction=64: search quality during index build (higher = better, slower build)
CREATE INDEX IF NOT EXISTS idx_memories_embedding_hnsw
ON memories
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Create composite index for common filter patterns
-- Speeds up: WHERE user_id = ? AND agent_id = ? ORDER BY embedding <=> ?
CREATE INDEX IF NOT EXISTS idx_memories_user_agent
ON memories (user_id, agent_id)
WHERE user_id IS NOT NULL OR agent_id IS NOT NULL;

-- Create index for run_id filtering
CREATE INDEX IF NOT EXISTS idx_memories_run_id
ON memories (run_id)
WHERE run_id IS NOT NULL;

-- Create index for memory_type filtering
CREATE INDEX IF NOT EXISTS idx_memories_type
ON memories ((metadata->>'memory_type'))
WHERE metadata->>'memory_type' IS NOT NULL;

-- Create index for created_at (recency queries)
CREATE INDEX IF NOT EXISTS idx_memories_created_at
ON memories (created_at DESC);

-- Create GIN index for metadata JSONB queries
CREATE INDEX IF NOT EXISTS idx_memories_metadata_gin
ON memories USING GIN (metadata);

-- Create index for immutable flag
CREATE INDEX IF NOT EXISTS idx_memories_immutable
ON memories ((metadata->>'immutable'))
WHERE metadata->>'immutable' = 'true';

-- Optimize planner statistics for better query plans
ANALYZE memories;

-- Set work_mem higher for this session (index build benefits)
-- SET work_mem = '256MB';
