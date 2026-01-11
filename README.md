# 🧠 Mem0: Supabase Edition

> **The 12-Layer Cognitive Memory Architecture for AI Agents, hyper-optimized for Supabase.**

[![GitHub](https://img.shields.io/github/license/mem0ai/mem0)](https://github.com/mem0ai/mem0)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Supabase Powered](https://img.shields.io/badge/Supabase-Powered-3ecf8e?logo=supabase)](https://supabase.com)

Mem0-Supabase is an enterprise-grade memory system that transforms AI agents into cognitively aware entities. By leveraging **Graph-on-Postgres**, **Hybrid Search**, and a **Human-Inspired 12-Layer Recall System**, it provides the most sophisticated long-term memory solution in the Supabase ecosystem.

---

## 🚀 The 12-Layer Architecture

Mem0 emulates human cognition through 12 hierarchical memory layers:

1.  **Perceptual**: Sensory processing (Multimodal).
2.  **Reflexive**: Real-time instinctive reaction.
3.  **Working**: Zero-latency Semantic Cache.
4.  **Episodic**: Continuous sequential history.
5.  **Lifecycle**: Dynamic decay & "Forgetting Curve".
6.  **Consolidation**: Nightly "Dreaming" (Summarization).
7.  **Enterprise Nexus**: Multi-tier authoritative sharing.
8.  **Semantic**: Consolidated world facts.
9.  **Procedural**: Skills and instructions.
10. **Graphic**: Associative relational links.
11. **Recollection**: Human-like weighted retrieval.
12. **The Ego**: Meta-cognitive Identity Synthesis.

---

## ⚡ Key Features

- **⚓ Universal Recall**: Human-like recordation via Weighted Ranking (Similarity + Importance + Recency + Graph Associations).
- **🛠️ Universal AI Access (MCP)**: Native support for Claude Desktop, Cursor, and IDEs.
- **🕰️ Temporal Memory**: Direct time-travel queries (Recall what you knew 7 days ago).
- **🕸️ Graph-on-Postgres**: Massive relational knowledge without Neo4j.
- **🛡️ Enterprise Ready**: Native RLS security and multi-org visibility.

---

## 🏁 Quickstart

```bash
pip install mem0ai
export SUPABASE_CONNECTION_STRING="postgresql://postgres:password@host:5432/postgres"
python scripts/setup_wizard.py
```

```python
from mem0 import Memory

# 1. Initialize Memory
m = Memory()

# 2. Smart Pipe Interaction (Unified Capture & Recall)
# This single call retrieves context (memories + graph + history) AND learns from the input.
context = m.process_interaction(
    "How does my interest in architecture relate to my work?", 
    user_id="user_123"
)

# 3. Use the Context
print(f"Persona: {context['persona']}")
print(f"Related Memories: {len(context['memories'])}")
print(f"Knowledge Graph Links: {len(context['associations'])}")
```

## 📂 Documentation

- [**Cognitive Blueprint**](./docs/architecture/memory_layers.mdx): Detailed breakdown of the 11 layers.
- [**Technical Innovations**](./docs/architecture/supabase_innovations.md): Hybrid search, Graph-on-Postgres, and Vault.
- [**Setup Guide**](./docs/SETUP.md): Comprehensive environment and SQL configuration.

## 📜 License
Apache 2.0