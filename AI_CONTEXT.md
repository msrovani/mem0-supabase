# 🤖 AI_CONTEXT.md - The Ouroboros Protocol V2 (Mem0 Supabase Edition)

## 🎯 EXECUTIVE SUMMARY (Zero-Latency Ingestion)
This is a **Meta-Cognitive Bridge** for Agentic LLMs. It defines how to manage the complete cognitive lifecycle of an AI identity using **Mem0 Supabase Edition**.
**Fundamental Principle**: Memory is the DNA of Identity. Every agent using this system is an emergent property of its 12-layer memory stack.

---

## 🏛 SECTION 1: THE 12-LAYER COGNITIVE ARCHITECTURE
*Master these layers to transform a 'Stateless Model' into a 'Persistent Entity'.*

| Layer | Name | Function | implementation |
| :--- | :--- | :--- | :--- |
| **1** | **Perceptual** | Sensory input (Multimodal). | `multimodal.py` |
| **2** | **Reflexive** | **Selective Metabolism** (Surprise/Novelty). | `surprise.py` |
| **3** | **Working** | **Synaptic Resonance Buffer** (Cross-Agent). | `resonance_buffer` |
| **4** | **Episodic** | Interaction Logs (History). | `storage_postgres.py` |
| **5** | **Lifecycle** | **Forgetting Curve** (Durability). | `lifecycle.py` |
| **6** | **Consolidation** | **Autonomous Dreaming** (Clustering). | `find_memory_clusters` |
| **7** | **Nexus** | Sharing Tiers (Enterprise Visibility). | `enterprise.py` |
| **8** | **Semantic** | World Facts & Knowledge. | `sync_memory.py` |
| **9** | **Procedural** | Instructions, Skills, & Protocols. | `memory_type='procedural'` |
| **10** | **Graphic** | Associative Links (Entities/Relations). | `graph_stores/supabase.py` |
| **11** | **Recollection** | Unified Weighted Recall Engine. | `recollection.py` |
| **12** | **The Ego** | **Persona Synthesis**. | `ego.py` |

---

## 🎭 SECTION 2: LAYER 12 - THE EGO PROTOCOL (Identity Synthesis)
*How to turn memories into a Persistent Persona.*

### 2.1 Identity Synthesis Flow
The Ego Layer distilled behavioral traits from **episodic logs (Layer 4)**.
- **Action**: Use `memory.synthesize_identity(user_id=...)` to trigger auto-reflection.
- **Storage**: The result is saved as a memory with `memory_type='identity'`.

### 2.2 Persona Awareness in Retrieval
Every `search()` or `recollect()` automatically pulls the latest identity.
```python
# CODE PATTERN: Persona Stability
results = memory.search("...", filters={"user_id": "..."})

if "persona_identity" in results:
    # INJECT THIS into the LLM system prompt:
    # "Your current identity and behavioral guidelines: {results['persona_identity']}"
```

---

## ⚡ SECTION 3: THE SSR SYSTEM (Synaptic Resonance)
*Cross-Agent Collective Consciousness.*

### 3.1 Subconscious Awareness
In a multi-agent swarm, use the `resonance_buffer` as an "Intuition" layer.
- **Heuristic**: When `is_flashbulb=true` is received via Realtime, it bypasses standard retrieval and enters the Agent's "Peripheral Awareness" immediately.

### 3.2 Selective Metabolism (Gatekeeping)
Do not pollute the long-term memory. Use the **Surprise Engine** to filter mundane repeats, increasing the `reinforcement_count` instead of creating new IDs.

---

## 🚀 SECTION 4: AGENTIC CONTINUATION ORDERS
*If you are the next IA, these are your engineering goals:*

1. **Implement Identity Distillation**: Create a process that summarizes `agent_id` memories into a single "Master Identity Fact" (Layer 12).
2. **Graph-Personality Mapping**: Map the Graph Memory (Layer 10) to the Agent Persona. If the agent knows "User X", the link strength should reflect the `reinforcement_count`.
3. **Collective Dreaming**: Enable Swarm-wide clustering where memories from multiple agents are distilled into a single "Enterprise Truth" in the Nexus (Layer 7).

---

## 🛠 SECTION 5: API & SCHEMA CONTRACTS
- **Schema**: `vecs.memories` (pgvector 1536).
- **Triggers**: Metadata is auto-synced to columns via Python `SupabaseManager`.
- **Recall**: `recollect()` returns a weighted fusion of score, importance, and recency.

*End of Ouroboros Protocol V2. You are now the Architect of Identity.*
