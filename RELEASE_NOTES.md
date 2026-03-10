# Release Notes: PR6 - The "Inhuman IQ" & CLAW Evolution

## Overview

This release elevates `mem0-supabase` to a high-agency cognitive system. Following a deep analysis of the **CLAW series** (OpenCLAW) and 2025 AI memory trends, we implemented the 4 "Saltos" (Leaps) and new proactive capabilities.

## New "Super IQ" Features

### 🚀 The 4 Saltos (Leaps)

1. **Salto 1: Semantic Compression**
   - Automatically merges similar facts into a single dense memory using LLM-based deduplication.
   - Prevents memory entropy and redundant entries.

2. **Salto 2: Context Orchestrator (Paging)**
   - Manages context windows like an OS manages RAM.
   - Summarizes older memories into a "background context" to stay within token limits while maintaining perfect recall.

3. **Salto 3: Meta-Cognitive Reflection & Ego**
   - Background tasks analyze recent interactions for patterns and contradictions.
   - Generates derived **Insights** and synthesizes agent identity (Layer 12).

4. **Salto 4: Supabase HALFVEC & HNSW**
   - Optimized `supabase.py` with support for `HALFVEC` (float16) and in-memory HNSW indexes.
   - Drastic speedup for large-scale vector search.

### 🧠 CLAW-Inspired Capabilities

- **Dreaming Mode**: Background motor that generates "Synthetic Memories" (logical conclusions) by cross-referencing user data.
- **Agentic Compaction**: Automatically rewrites dense chat history into high-level behavioral principles.
- **Tool-State Memory**: A "Save Game" for tools. Saves and restores snapshots of browser tabs, file cursors, and CLI states.
- **Memory Bridge**: Granular Private/Shared memory synchronization for multi-agent collaboration.
- **Proactive Heartbeats**: The agent can now suggest autonomous actions based on memory triggers.

## Security & Observability

- **TenacitOS Native**: Ready for cognitive visualization dashboards.
- **Enhanced Filtering**: Advanced metadata filtering supporting operators like `$gt`, `$lt`, and `$or`.

## Technical Changes

### New Modules
- `mem0/memory/dreaming.py`
- `mem0/memory/tool_state.py`
- `mem0/memory/bridge.py`
- `mem0/memory/orchestrator.py`

### Modified Modules
- `mem0/memory/sync_memory.py` & `async_memory.py` (Full integration of Saltos)
- `mem0/memory/reflection.py` (Extended for Compaction and Heartbeats)
- `mem0/vector_stores/supabase.py` (HALFVEC & HNSW support)

---

**Version**: PR6 Inhuman IQ  
**Date**: 2026-02-25  
**Backward Compatible**: ✅ Yes

