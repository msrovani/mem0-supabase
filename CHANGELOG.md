# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Security**: JWT authentication middleware for all API endpoints
- **Security**: ContextFirewall — PII redaction engine (email, CPF, SSN, credit cards, phone, IP, API keys)
- **Security**: Audit logging with structured JSON, file rotation, async mode, retention policy
- **Performance**: SmartCache with warming, predictive pre-fetching, auto-invalidation, analytics, auto-tuning
- **Performance**: BatchEmbedder — groups multiple texts into efficient batch operations
- **Performance**: LazyEngineRegistry — on-demand initialization of memory engines
- **Performance**: QueryPlanCache — LRU cache for frequent filter combinations with TTL
- **Performance**: Retry with exponential backoff for external service calls
- **Performance**: Circuit breaker for LLM, vector store, and graph store
- **API**: Cursor-based pagination for GET /memories
- **API**: Bulk create endpoint (POST /memories/bulk)
- **API**: SSE streaming endpoint (POST /memories/stream)
- **API**: Idempotency key support for POST /memories
- **API**: Per-user rate limiting (not just IP-based)
- **API**: Request ID tracing (X-Request-Id header)
- **API**: Response time header (X-Response-Time)
- **API**: Health check with live DB/LLM connectivity tests
- **API**: Input validation with regex for user_id, agent_id, run_id
- **Infrastructure**: Docker + docker-compose (multi-stage build, non-root user, healthchecks)
- **Infrastructure**: CI/CD pipeline (lint, test, docker build, security scan)
- **Infrastructure**: Vector index tuning (HNSW + composite indexes)
- **Infrastructure**: Graceful shutdown with cleanup
- **Infrastructure**: Connection pooling configuration
- **Architecture**: Core interfaces (IVectorStore, IGraphStore, ILLM, IEmbedder, IReranker)
- **Architecture**: Event sourcing foundation (immutable event log, replay, projections)
- **Architecture**: CQRS foundation (CommandBus, QueryBus with caching)
- **Architecture**: Webhook system (event-driven notifications with HMAC signatures)
- **Architecture**: Memory templates (pre-defined schemas with validation)
- **Bug Fixes**: Fixed 15 critical bugs including metadata=None crashes, nested list assumptions, OR/NOT filter bugs, race conditions, mutable defaults, and immutability gaps
- **Bug Fixes**: Fixed bare excepts that silently swallowed errors
- **Bug Fixes**: Fixed typo in DEFAUT_CACHE_THRESHOLD → DEFAULT_CACHE_THRESHOLD
- **Bug Fixes**: Moved MemoryEvaluator from tests/ to mem0/evaluation/

### Changed
- Removed unsafe default credentials (fail-fast on missing env vars)
- Replaced global MEMORY_INSTANCE with thread-safe app.state + Lock
- Upgraded immutability gating from per-memory flag to config-level OR per-memory
- Optimized recollection entity extraction (regex-first, LLM fallback)
- Moved STOPWORDS to module-level frozenset constant
- Added __slots__ to all dataclasses for reduced memory footprint

### Removed
- Unsafe default credentials (postgres, mem0graph, etc.)
- sys.path manipulation hack from mem0/__init__.py
- Dead code in _process_config method

## [1.0.0] — 2024-01-01

### Added
- Initial release with 12-layer cognitive memory architecture
- Supabase/PostgreSQL vector store integration
- Graph store support (Neo4j, Memgraph, Supabase)
- Semantic search with weighted scoring (similarity + importance + recency)
- Associative graph jumps for context expansion
- Reflection engine (background self-correction)
- Dreaming mode (synthetic memory generation)
- Surprise engine (novelty detection)
- Ego engine (meta-cognitive identity)
- Context orchestrator (paging mechanism)
- Memory bridge (multi-agent shared/private memories)
- Tool-state memory (save game for tools)
- Hybrid search (semantic + keyword with RRF)
- Staleness detection
- Reranking pipeline
- Consent manager
- Identity resolver
- Experience indexer
- Voice memory manager
- LangGraph integration
- Temporal memory with time travel
- MCP server
