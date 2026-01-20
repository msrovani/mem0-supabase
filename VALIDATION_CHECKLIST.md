# Mem0-Supabase Validation Checklist

This document provides a comprehensive checklist for validating the Mem0-Supabase system after code changes, particularly following the quality sweep (PR5).

## 1. Unit Tests

Run the full unit test suite to ensure core functionality remains intact:

```bash
pytest tests/
```

### Critical Test Areas

- ✅ Memory CRUD operations (add, get, search, update, delete)
- ✅ Tenant scoping enforcement
- ✅ Multimodal envelope processing
- ✅ Graph store integration
- ✅ Reranking and recollection
- ✅ Lifecycle and decay functions

## 2. Integration Tests

### Memory Operations

```bash
# Test basic memory workflow
python -c "
from mem0 import Memory
m = Memory()
result = m.add('Test memory', user_id='test_user')
print('Add:', result)
memories = m.search('Test', user_id='test_user')
print('Search:', memories)
m.delete_all(user_id='test_user')
print('Cleanup: OK')
"
```

### Async Memory

```bash
# Test async operations
python -c "
import asyncio
from mem0 import AsyncMemory

async def test():
    m = AsyncMemory()
    result = await m.add('Async test', user_id='async_user')
    print('Async Add:', result)
    await m.delete_all(user_id='async_user')
    print('Async Cleanup: OK')

asyncio.run(test())
"
```

## 3. Security Checks

### Tenant Isolation

Verify that tenant scoping is enforced across all operations:

```python
from mem0 import Memory
from mem0.exceptions import MemoryError

m = Memory()

# Should raise SecurityException (missing tenant context)
try:
    m.search("test query")
    print("❌ FAILED: Tenant scoping not enforced")
except Exception as e:
    print(f"✅ PASSED: Tenant isolation enforced - {type(e).__name__}")
```

### SQL Injection Prevention

Verify that all database queries use parameterized statements:

```bash
# Audit supabase.py for f-string SQL
grep -n "text(f\"" mem0/vector_stores/supabase.py
# Expected: No results (all should use parameterized queries)
```

### URL Redaction

Verify that no sensitive URLs or tokens are logged:

```bash
# Check for exposed secrets in logs
grep -r "api_key" mem0/ --include="*.py" | grep -i "log"
# Expected: No direct logging of API keys
```

## 4. Supabase Infra Checks (If PR4/Step 4 Enabled)

### Extensions

Verify required Supabase extensions are enabled:

```sql
-- Run in Supabase SQL Editor
SELECT extname, extversion 
FROM pg_extension 
WHERE extname IN ('vector', 'pg_cron', 'pg_net', 'pgmq');
```

Expected: All 4 extensions present.

### RPCs

Test the hybrid search RPC:

```sql
-- Test match_memories_hybrid RPC
SELECT * FROM match_memories_hybrid(
    query_embedding := '[0.1, 0.2, ...]'::vector,
    query_text := 'test query',
    match_count := 5,
    match_threshold := 0.0,
    semantic_weight := 1.0,
    full_text_weight := 1.0,
    rrf_k := 60,
    filter := '{"user_id": "test_user"}'::jsonb
);
```

### Queues (pgmq)

Verify queues are initialized:

```sql
SELECT queue_name FROM pgmq.list_queues();
```

Expected queues:

- `mem0-derive-text`
- `mem0-derive-multimodal`
- `mem0-embed-memory`
- `mem0-security-scan`
- `mem0-ego-recompute`
- `mem0-dlq`

### Edge Functions

Test Edge Function deployment:

```bash
supabase functions list
```

Expected functions:

- `worker-derive`
- `worker-embed`
- `worker-security-scan`
- `worker-ego-recompute`

### Storage

Verify the `mem0` bucket exists with RLS enabled:

```sql
SELECT name, public FROM storage.buckets WHERE name = 'mem0';
```

Expected: `public = false` (private bucket).

## 5. Performance Validation

### Reranking Cap

Verify that reranking only processes up to 3x the limit:

```python
from mem0 import Memory

m = Memory()
# Add 100 test memories
for i in range(100):
    m.add(f"Test memory {i}", user_id="perf_test")

# Search with limit=5, rerank should process max 15 candidates
results = m.search("test", user_id="perf_test", limit=5, rerank=True)
print(f"Results: {len(results['results'])}")  # Should be capped at 5

# Cleanup
m.delete_all(user_id="perf_test")
```

## 6. Backward Compatibility

### Legacy String Inputs

Verify that the system still accepts plain strings for `add()`:

```python
from mem0 import Memory

m = Memory()

# Test legacy string input
result = m.add("Plain string memory", user_id="compat_test")
print("✅ Legacy string input works:", result)

# Test legacy list of dict messages
result = m.add(
    [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi"}],
    user_id="compat_test"
)
print("✅ Legacy message list works:", result)

# Cleanup
m.delete_all(user_id="compat_test")
```

### Multimodal Envelope

Verify that the system accepts the new envelope format:

```python
from mem0 import Memory
from mem0.contracts.multimodal_envelope_v1 import MultimodalInteractionEnvelopeV1

m = Memory()

envelope = {
    "version": "v1",
    "interaction_id": "test_interaction",
    "user_id": "envelope_test",
    "payloads": [
        {
            "payload_type": "text",
            "content": "This is a multimodal test"
        }
    ],
    "metadata": {}
}

result = m.add(envelope)
print("✅ Multimodal envelope works:", result)

# Cleanup
m.delete_all(user_id="envelope_test")
```

## 7. Feature Flags

Verify that all feature flags have defaults and can be toggled:

```python
from mem0.configs.base import MemoryConfig

config = MemoryConfig()
print("Feature Flags:")
print(f"  enable_resonance: {config.enable_resonance} (default: False)")
print(f"  enable_ego: {config.enable_ego} (default: False)")
print(f"  enable_firewall: {config.enable_firewall} (default: False)")
print(f"  enable_realtime: {config.enable_realtime} (default: False)")
print(f"  enable_vault: {config.enable_vault} (default: False)")
```

## Summary

**Before Deployment:**

- ✅ All unit tests pass
- ✅ Integration tests complete successfully
- ✅ Security checks pass (tenant isolation, SQL injection prevention)
- ✅ Supabase infra is properly configured (if using PR4 features)
- ✅ Performance optimizations are working (reranking cap)
- ✅ Backward compatibility is maintained
- ✅ Feature flags are correctly configured

**Post-Deployment:**

- Monitor error logs for any runtime exceptions
- Verify tenant isolation in production
- Check query performance metrics
- Validate that all scheduled jobs are executing (if using PR4 cron)
