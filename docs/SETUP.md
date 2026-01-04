# Mem0: Supabase Edition - Setup Guide

This guide ensures your Supabase project is properly configured to support the 11-layer cognitive memory architecture.

## 1. Environment Variables 🔑

Set these in your local environment or serverless platform:

| Variable | Description | Example |
|----------|-------------|---------|
| `SUPABASE_CONNECTION_STRING` | Direct Postgres URI | `postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres` |
| `SUPABASE_URL` | Your project API URL | `https://[PROJECT].supabase.co` |
| `SUPABASE_KEY` | Your Service Role Key (for RLS bypass) | `ey...` |
| `OPENAI_API_KEY` | Needed for Embeddings and LLM | `sk-...` |

## 2. SQL Initialization 🛠️

Before using the library, you must run the unified SQL schema. This now includes the **SSR (Subconscious Synaptic Resonance)** infrastructure:
1.  **Surprise Columns**: `reinforcement_count` and `is_flashbulb`.
2.  **Realtime**: Enables `supabase_realtime` publication for the memories table.
3.  **Dreaming Functions**: SQL RPCs for autonomous memory clustering.

**Steps**:
1. Go to **Supabase Dashboard** -> **SQL Editor**.
2. Copy the contents of `scripts/supabase_setup.sql`.
3. Run the script.

## 3. Automated Setup Wizard 🧙‍♂️

We provide a script to verify your connection and optionally schedule "Dreaming" (Consolidation) jobs.

```bash
python scripts/setup_wizard.py
```

## 4. Initializing in Python 🐍

```python
from mem0 import Memory, MemoryConfig

# Configuration is automatically pulled from environment variables
m = Memory()

# Or pass explicitly
config = {
    "vector_store": {
        "provider": "supabase",
        "config": {
            "connection_string": "your-string",
            "collection_name": "my_memories"
        }
    }
}
m = Memory.from_config(config)
```

## 5. Troubleshooting 🔍

- **PGVector Error**: Ensure the `vector` extension is enabled.
- **Permission Denied**: Check if your `SUPABASE_CONNECTION_STRING` uses the `postgres` user.
- **MCP Connection**: Ensure `python -m mem0.mcp_server` runs without errors before adding to Claude Desktop.
