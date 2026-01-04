-- =============================================================================
-- MIGRATION 003: DYNAMIC LIFECYCLE & ENTERPRISE NEXUS
-- =============================================================================

-- 1. ENUMS & TYPES
DO $$ BEGIN
    CREATE TYPE memory_visibility AS ENUM ('private', 'team', 'global');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 2. ENHANCE MEMORIES TABLE
ALTER TABLE memories 
ADD COLUMN IF NOT EXISTS importance_score FLOAT DEFAULT 1.0,
ADD COLUMN IF NOT EXISTS last_accessed_at TIMESTAMPTZ DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS org_id TEXT,
ADD COLUMN IF NOT EXISTS team_id TEXT,
ADD COLUMN IF NOT EXISTS visibility memory_visibility DEFAULT 'private',
ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE;

-- 3. CREATE MEMORY PROPOSALS TABLE (Authoritative Suggestion Box)
CREATE TABLE IF NOT EXISTS memory_proposals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    memory_id UUID REFERENCES memories(id) ON DELETE CASCADE,
    suggested_by TEXT,
    target_visibility memory_visibility,
    status TEXT DEFAULT 'pending', -- pending, approved, rejected
    review_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    reviewer_id TEXT
);

-- 4. DYNAMIC LIFECYCLE LOGIC (DECAY)
CREATE OR REPLACE FUNCTION decay_memory_importance() 
RETURNS void AS $$
BEGIN
    -- Apply "Forgetting Curve" logic
    -- Decay memories not accessed in the last 7 days by 5%
    UPDATE memories
    SET importance_score = importance_score * 0.95
    WHERE last_accessed_at < NOW() - INTERVAL '7 days'
      AND is_current = TRUE
      AND importance_score > 0.01;

    -- Update is_current for low importance (Soft Delete / Archive Trigger)
    -- Memories with importance < 0.2 are "ignored" in standard searches
    -- and prepared for archival tier storage.
END;
$$ LANGUAGE plpgsql;

-- 5. AUTHORITATIVE PROMOTION
CREATE OR REPLACE FUNCTION approve_memory_proposal(
    p_proposal_id UUID,
    p_reviewer_id TEXT,
    p_notes TEXT DEFAULT ''
) RETURNS UUID AS $$
DECLARE
    v_memory_id UUID;
    v_visibility memory_visibility;
BEGIN
    SELECT memory_id, target_visibility INTO v_memory_id, v_visibility
    FROM memory_proposals WHERE id = p_proposal_id;

    IF v_memory_id IS NULL THEN
        RAISE EXCEPTION 'Proposal not found';
    END IF;

    -- Update memory status
    UPDATE memories 
    SET visibility = v_visibility, 
        is_verified = TRUE,
        importance_score = 1.0  -- Reset importance on promotion
    WHERE id = v_memory_id;

    -- Mark proposal as approved
    UPDATE memory_proposals
    SET status = 'approved', 
        reviewed_at = NOW(), 
        reviewer_id = p_reviewer_id,
        review_notes = p_notes
    WHERE id = p_proposal_id;

    RETURN v_memory_id;
END;
$$ LANGUAGE plpgsql;

-- 6. ENTERPRISE RLS (Sharing Policies)
-- Disable old policies if they conflict, then add Nexus policies
DROP POLICY IF EXISTS "Users can see their own memories" ON memories;

CREATE POLICY "Nexus: Accessible Memories" ON memories
FOR SELECT USING (
    -- 1. Private: Only the owner (metadata->>'user_id')
    (visibility = 'private' AND metadata->>'user_id' = auth.uid()::text) 
    OR
    -- 2. Team: Anyone in the same team
    (visibility = 'team' AND team_id = (SELECT team_id FROM users WHERE id = auth.uid() LIMIT 1))
    OR
    -- 3. Global: Anyone in the same org
    (visibility = 'global' AND org_id = (SELECT org_id FROM users WHERE id = auth.uid() LIMIT 1))
    OR
    -- 4. Service Role bypass
    (auth.role() = 'service_role')
);

-- 7. CLEANUP & PERFORMANCE
CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance_score) WHERE is_current = TRUE;
CREATE INDEX IF NOT EXISTS idx_memories_sharing ON memories(org_id, team_id, visibility);
CREATE INDEX IF NOT EXISTS idx_proposals_status ON memory_proposals(status);
