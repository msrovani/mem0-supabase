import os
from mem0 import Memory
import asyncio

async def test_fixes():
    # Test Configuration & Initialization
    print("Testing Memory Initialization...")
    try:
        # Mocking connection string for local test if needed, 
        # but here we just want to see if it instantiates without error due to missing fields
        # Using a dummy sqlite path for components that fall back to it
        config = {
            "vector_store": {
                "provider": "supabase",
                "config": {
                    "connection_string": "postgresql://postgres:postgres@localhost:5432/postgres",
                    "collection_name": "test_memories"
                }
            },
            "graph_store": {
                "provider": "supabase",
                "config": {
                    "connection_string": "postgresql://postgres:postgres@localhost:5432/postgres"
                }
            },
            "reranker": {
                "provider": "cohere",
                "config": {
                    "api_key": "test_key",
                    "model": "rerank-english-v3.0"
                }
            }
        }
        
        # We expect a ConfigurationError or connection error since localhost isn't running,
        # but we want to ensure it doesn't fail on MISSING FIELD access in config first.
        try:
            m = Memory.from_config(config)
            print("Sync Memory instantiated successfully (config keys present).")
        except Exception as e:
            print(f"Sync Memory instantiation error (expected connection fail but check keys): {type(e).__name__}: {e}")

        from mem0 import AsyncMemory
        try:
            am = await AsyncMemory.from_config(config)
            print("Async Memory instantiated successfully (config keys present).")
        except Exception as e:
            print(f"Async Memory instantiation error: {type(e).__name__}: {e}")

    except Exception as e:
        print(f"Critical initialization error: {e}")

    # Verify signature alignment
    print("\nVerifying 'add' signatures...")
    import inspect
    sync_add_sig = inspect.signature(Memory.add)
    async_add_sig = inspect.signature(AsyncMemory.add)
    
    sync_params = set(sync_add_sig.parameters.keys())
    async_params = set(async_add_sig.parameters.keys())
    
    # Common core params should match
    common_expected = {'messages', 'user_id', 'agent_id', 'run_id', 'metadata', 'infer', 'memory_type', 'prompt', 'org_id', 'team_id', 'visibility'}
    
    print(f"Sync add params: {sync_params}")
    print(f"Async add params: {async_params}")
    
    missing_in_async = common_expected - async_params
    if not missing_in_async:
        print("Success: Async add signature now includes enterprise parameters.")
    else:
        print(f"Fail: Async add is missing {missing_in_async}")

if __name__ == "__main__":
    asyncio.run(test_fixes())
