# Memory Staleness Detection - Phase 1.4

## Origin & Research References

- **Mnemos Multi-Agent Memory OS**: Typed Conflict Resolution patterns
  - https://github.com/Sohamp2809/mnemos
- **SimpleMem** (arXiv:2601.02553): Semantic memory lifecycle management
  - https://arxiv.org/abs/2601.02553
- **Memory for Autonomous LLM Agents** (arXiv:2603.07670): Memory write-manage-read loop taxonomy
  - https://arxiv.org/abs/2603.07670
- **Ebbinghaus Forgetting Curve**: Natural memory decay model
  - Applied to AI memory confidence decay

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Memory Access/Query                        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Staleness Detector (4 Checks)                   │
│                                                              │
│  1. TTL Check ──────────────► Has memory exceeded its TTL?   │
│  2. Confidence Decay ───────► Has confidence fallen below    │
│                                threshold due to age?          │
│  3. Never Accessed ─────────► Has memory never been accessed │
│                                within grace period?           │
│  4. Contradiction ──────────► Do newer memories contradict   │
│                                this memory?                   │
└────────────────────────┬────────────────────────────────────┘
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
         FRESH       AGING      STALE/EXPIRED
         (keep)    (monitor)   (refresh/remove)
```

## Implementation

### Files Created

| File | Description |
|------|-------------|
| `mem0/memory/staleness.py` | Complete staleness detection system |
| `tests/test_staleness.py` | Unit tests for all staleness scenarios |

### Staleness Levels

| Level | Description | Action |
|-------|-------------|--------|
| FRESH | Memory is current and reliable | No action needed |
| AGING | Memory is getting old, monitor closely | Schedule verification |
| STALE | Memory is stale, should be refreshed | Trigger refresh |
| EXPIRED | Memory has expired | Remove from storage |

### Staleness Reasons

| Reason | Detection Method |
|--------|-----------------|
| TTL_EXPIRED | Time since creation exceeds configured TTL |
| CONFIDENCE_DECAY | Confidence decayed below min threshold |
| CONTRADICTION | Newer memories contradict this memory |
| CONTEXT_SHIFT | User context has changed significantly |
| NEVER_ACCESSED | Memory created but never accessed |

### Configuration

```python
from mem0.memory.staleness import StalenessDetector, StalenessConfig

config = StalenessConfig(
    # TTL-based staleness
    default_ttl_hours=720.0,          # 30 days
    high_confidence_ttl_hours=2160.0,  # 90 days (score >= 0.9)
    low_confidence_ttl_hours=168.0,    # 7 days (score <= 0.5)

    # Confidence decay (Ebbinghaus-inspired)
    confidence_decay_rate=0.01,        # 1% decay per day
    min_confidence_threshold=0.3,      # Below this = stale

    # Contradiction detection
    enable_contradiction_detection=True,
    contradiction_time_window_hours=168.0,  # 7 days

    # Context shift detection
    enable_context_shift_detection=False,
    context_shift_threshold=0.7,

    # Access tracking
    never_accessed_ttl_hours=72.0,     # 3 days
)

detector = StalenessDetector(config)
```

### Usage

```python
from mem0.memory.staleness import StalenessDetector, StalenessLevel

detector = StalenessDetector()

# Check single memory
result = detector.check_staleness(memory_item, all_memories)
if result.level in (StalenessLevel.STALE, StalenessLevel.EXPIRED):
    print(f"Memory {result.memory_id} is {result.level.value}")
    print(f"Reason: {result.reason.value}")
    print(f"Recommendation: {result.recommendation}")

# Batch check
results = detector.check_batch_staleness(memories)

# Get only stale memories
stale = detector.get_stale_memories(memories, include_aging=True)
for memory, result in stale:
    print(f"Stale: {memory['memory']} -> {result.recommendation}")
```

### Confidence Decay Model

Based on the Ebbinghaus Forgetting Curve:

```
decayed_confidence = initial_confidence * (1 - decay_rate) ^ days
```

With default `decay_rate=0.01` (1% per day):
- Day 0: 100% confidence
- Day 30: 74% confidence
- Day 60: 55% confidence
- Day 90: 41% confidence
- Day 120: 30% confidence (below threshold)

### Integration with Memory Lifecycle

```python
# In your memory retrieval pipeline:
def get_memories_with_staleness_check(query, user_id):
    # 1. Retrieve memories from vector store
    memories = vector_store.search(query, user_id)

    # 2. Check staleness
    detector = StalenessDetector()
    stale = detector.get_stale_memories(memories, include_aging=True)

    # 3. Remove/refresh stale memories
    for memory, result in stale:
        if result.level == StalenessLevel.EXPIRED:
            storage.delete(memory["id"])
        elif result.level == StalenessLevel.STALE:
            # Flag for refresh
            storage.flag_for_refresh(memory["id"])

    # 4. Return fresh memories
    return [m for m in memories if m["id"] not in [s[0]["id"] for s in stale]]
```

### Performance

- Single memory check: <1ms (pure Python, no I/O)
- Batch check (100 memories): <10ms
- Contradiction detection: O(n²) where n = number of memories
  - Optimized with time window filtering
