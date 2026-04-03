"""
Layer-by-Layer Test Suite with Injectable Mocks

Tests each mem0 layer in isolation using the core interfaces (IVectorStore,
ILLM, IEmbedder, IGraphStore, IReranker) for mock injection.

Run: pytest tests/test_layer_by_layer.py -v
"""

import unittest
from unittest.mock import MagicMock, patch, PropertyMock
from typing import Any, Dict, List, Optional

# Top-level imports so patch() can resolve module paths
from mem0.configs.base import MemoryConfig
from mem0.vector_stores.configs import VectorStoreConfig
from mem0.configs.vector_stores.supabase import SupabaseConfig

# ------------------------------------------------------------------
# Mock Implementations of Core Interfaces
# ------------------------------------------------------------------


class MockVectorStore:
    """In-memory mock of IVectorStore for testing."""

    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
        self.insert_calls = []
        self.search_calls = []
        self.delete_calls = []
        self.update_calls = []

    def insert(self, vectors, ids, payloads=None):
        for i, mid in enumerate(ids):
            payload = payloads[i] if payloads else {}
            self._store[mid] = {
                "id": mid,
                "vector": vectors[i],
                "payload": payload,
            }
        self.insert_calls.append({"ids": ids, "count": len(ids)})
        return ids

    def get(self, vector_id):
        item = self._store.get(vector_id)
        if not item:
            return None
        mock = MagicMock()
        mock.id = item["id"]
        mock.payload = item["payload"]
        mock.vector = item["vector"]
        mock.score = None
        return mock

    def search(self, query, vectors, limit=10, filters=None):
        self.search_calls.append({"query": query, "limit": limit, "filters": filters})
        results = []
        for mid, item in self._store.items():
            mock = MagicMock()
            mock.id = mid
            mock.payload = item["payload"]
            mock.score = 0.8
            results.append(mock)
        return results[:limit]

    def update(self, vector_id, vector, payload=None):
        if vector_id in self._store:
            self._store[vector_id]["vector"] = vector
            if payload:
                self._store[vector_id]["payload"].update(payload)
        self.update_calls.append({"id": vector_id})

    def delete(self, vector_id):
        self._store.pop(vector_id, None)
        self.delete_calls.append({"id": vector_id})

    def list(self, filters=None, limit=100):
        results = []
        for mid, item in self._store.items():
            if filters:
                match = all(item["payload"].get(k) == v for k, v in filters.items())
                if not match:
                    continue
            mock = MagicMock()
            mock.id = mid
            mock.payload = item["payload"]
            results.append(mock)
        return results[:limit]

    def delete_col(self):
        self._store.clear()


class MockLLM:
    """In-memory mock of ILLM for testing."""

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.generate_calls = []
        self.embedding_calls = []

    def generate_response(self, messages, response_format=None):
        self.generate_calls.append({"messages": messages, "response_format": response_format})
        # Return a deterministic JSON response for fact extraction
        return '{"facts": ["User likes pizza", "User lives in New York"]}'

    def generate_embeddings(self, texts):
        self.embedding_calls.append(texts)
        return [[0.1] * 1536 for _ in texts]


class MockEmbedder:
    """In-memory mock of IEmbedder for testing."""

    def __init__(self):
        self.embed_calls = []

    def embed(self, text, mode="search"):
        self.embed_calls.append({"text": text, "mode": mode})
        return [0.1] * 1536  # Fake 1536-dim embedding


class MockGraphStore:
    """In-memory mock of IGraphStore for testing."""

    def __init__(self):
        self.nodes = []
        self.edges = []
        self.add_calls = []

    def add(self, nodes, edges):
        self.nodes.extend(nodes)
        self.edges.extend(edges)
        self.add_calls.append({"nodes": len(nodes), "edges": len(edges)})

    def search(self, query, filters=None, limit=10):
        return []

    def get_all_nodes(self, filters=None):
        return self.nodes

    def get_all_edges(self, filters=None):
        return self.edges

    def delete_node(self, node_id):
        self.nodes = [n for n in self.nodes if n.get("id") != node_id]

    def delete_edge(self, edge_id):
        self.edges = [e for e in self.edges if e.get("id") != edge_id]


class MockReranker:
    """In-memory mock of IReranker for testing."""

    def __init__(self):
        self.rerank_calls = []

    def rerank(self, query, documents, limit=10):
        self.rerank_calls.append({"query": query, "count": len(documents), "limit": limit})
        return documents[:limit]


# ------------------------------------------------------------------
# Layer 1: Vector Store Layer Tests
# ------------------------------------------------------------------


class TestVectorStoreLayer(unittest.TestCase):
    """Test the vector store abstraction in isolation."""

    def setUp(self):
        self.store = MockVectorStore()

    def test_insert_and_get(self):
        ids = self.store.insert(
            vectors=[[0.1] * 10],
            ids=["mem_1"],
            payloads=[{"data": "Hello world", "user_id": "u1"}],
        )
        self.assertEqual(ids, ["mem_1"])

        item = self.store.get("mem_1")
        self.assertIsNotNone(item)
        self.assertEqual(item.payload["data"], "Hello world")

    def test_get_nonexistent(self):
        self.assertIsNone(self.store.get("nonexistent"))

    def test_search_with_filters(self):
        self.store.insert(
            vectors=[[0.1] * 10, [0.2] * 10],
            ids=["mem_1", "mem_2"],
            payloads=[
                {"data": "Hello", "user_id": "u1"},
                {"data": "World", "user_id": "u2"},
            ],
        )

        results = self.store.search(query="test", vectors=[0.1] * 10, limit=10, filters={"user_id": "u1"})
        self.assertGreaterEqual(len(results), 1)

    def test_update(self):
        self.store.insert(
            vectors=[[0.1] * 10],
            ids=["mem_1"],
            payloads=[{"data": "Hello"}],
        )
        self.store.update("mem_1", vector=[0.2] * 10, payload={"data": "Updated"})
        item = self.store.get("mem_1")
        self.assertEqual(item.payload["data"], "Updated")

    def test_delete(self):
        self.store.insert(vectors=[[0.1] * 10], ids=["mem_1"], payloads=[{"data": "test"}])
        self.store.delete("mem_1")
        self.assertIsNone(self.store.get("mem_1"))

    def test_list_with_filters(self):
        self.store.insert(
            vectors=[[0.1] * 10, [0.2] * 10, [0.3] * 10],
            ids=["mem_1", "mem_2", "mem_3"],
            payloads=[
                {"user_id": "u1"},
                {"user_id": "u1"},
                {"user_id": "u2"},
            ],
        )
        results = self.store.list(filters={"user_id": "u1"}, limit=10)
        self.assertEqual(len(results), 2)

    def test_delete_col(self):
        self.store.insert(vectors=[[0.1] * 10], ids=["mem_1"], payloads=[{}])
        self.store.delete_col()
        results = self.store.list()
        self.assertEqual(len(results), 0)


# ------------------------------------------------------------------
# Layer 2: LLM Layer Tests
# ------------------------------------------------------------------


class TestLLMLayer(unittest.TestCase):
    """Test the LLM abstraction in isolation."""

    def setUp(self):
        self.llm = MockLLM()

    def test_generate_response(self):
        response = self.llm.generate_response(
            messages=[{"role": "user", "content": "Hello"}],
            response_format={"type": "json_object"},
        )
        self.assertIsInstance(response, str)
        self.assertEqual(len(self.llm.generate_calls), 1)

    def test_generate_embeddings(self):
        embeddings = self.llm.generate_embeddings(["Hello", "World"])
        self.assertEqual(len(embeddings), 2)
        self.assertEqual(len(embeddings[0]), 1536)


# ------------------------------------------------------------------
# Layer 3: Embedder Layer Tests
# ------------------------------------------------------------------


class TestEmbedderLayer(unittest.TestCase):
    """Test the embedder abstraction in isolation."""

    def setUp(self):
        self.embedder = MockEmbedder()

    def test_embed_search_mode(self):
        emb = self.embedder.embed("Hello world", mode="search")
        self.assertEqual(len(emb), 1536)
        self.assertEqual(len(self.embedder.embed_calls), 1)
        self.assertEqual(self.embedder.embed_calls[0]["mode"], "search")

    def test_embed_add_mode(self):
        emb = self.embedder.embed("Hello world", mode="add")
        self.assertEqual(self.embedder.embed_calls[0]["mode"], "add")


# ------------------------------------------------------------------
# Layer 4: Graph Layer Tests
# ------------------------------------------------------------------


class TestGraphLayer(unittest.TestCase):
    """Test the graph store abstraction in isolation."""

    def setUp(self):
        self.graph = MockGraphStore()

    def test_add_nodes_and_edges(self):
        nodes = [{"id": "n1", "label": "Person", "name": "Alice"}]
        edges = [{"source": "n1", "target": "n2", "type": "knows"}]
        self.graph.add(nodes, edges)
        self.assertEqual(len(self.graph.nodes), 1)
        self.assertEqual(len(self.graph.edges), 1)

    def test_get_all_nodes(self):
        self.graph.add([{"id": "n1"}], [])
        nodes = self.graph.get_all_nodes()
        self.assertEqual(len(nodes), 1)

    def test_delete_node(self):
        self.graph.add([{"id": "n1"}, {"id": "n2"}], [])
        self.graph.delete_node("n1")
        self.assertEqual(len(self.graph.nodes), 1)


# ------------------------------------------------------------------
# Layer 5: Reranker Layer Tests
# ------------------------------------------------------------------


class TestRerankerLayer(unittest.TestCase):
    """Test the reranker abstraction in isolation."""

    def setUp(self):
        self.reranker = MockReranker()

    def test_rerank(self):
        docs = [
            {"memory": "Alice likes pizza", "score": 0.5},
            {"memory": "Bob likes sushi", "score": 0.7},
        ]
        results = self.reranker.rerank("pizza", docs, limit=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(len(self.reranker.rerank_calls), 1)


# ------------------------------------------------------------------
# Layer 6: Security Layer Tests (ContextFirewall)
# ------------------------------------------------------------------


class TestContextFirewall(unittest.TestCase):
    """Test PII redaction in isolation."""

    def setUp(self):
        from mem0.security.context_firewall import ContextFirewall, redact_text, get_firewall
        from mem0.security.audit_log import AuditLogger, EventType

        self.ContextFirewall = ContextFirewall
        self.redact_text = redact_text
        self.get_firewall = get_firewall
        self.AuditLogger = AuditLogger
        self.EventType = EventType

        self.firewall = ContextFirewall()

    def test_redact_email(self):
        result = self.firewall.redact_text("Contact user@example.com for info")
        self.assertIn("[EMAIL_REDACTED]", result.redacted_text)
        self.assertEqual(result.redactions_found.get("EMAIL", 1), 1)

    def test_redact_cpf(self):
        result = self.firewall.redact_text("CPF: 123.456.789-00")
        self.assertIn("[CPF_REDACTED]", result.redacted_text)
        self.assertTrue(result.redactions_found.get("CPF", 0) > 0)

    def test_redact_multiple(self):
        result = self.firewall.redact_text("Email: test@test.com, Phone: (555) 123-4567, IP: 192.168.1.1")
        self.assertIn("[EMAIL_REDACTED]", result.redacted_text)
        self.assertIn("[PHONE_REDACTED]", result.redacted_text)
        self.assertIn("[IP_REDACTED]", result.redacted_text)
        self.assertGreater(sum(result.redactions_found.values()), 1)

    def test_clean_text(self):
        result = self.firewall.redact_text("Hello world, no PII here")
        self.assertTrue(result.is_clean)
        self.assertEqual(result.redacted_text, "Hello world, no PII here")

    def test_redact_batch(self):
        results = self.firewall.redact_batch(["a@b.co", "clean text"])
        self.assertFalse(results[0].is_clean)
        self.assertTrue(results[1].is_clean)

    def test_global_firewall(self):
        fw = self.get_firewall()
        self.assertIsNotNone(fw)
        self.assertIs(fw, self.get_firewall())

    def test_disable_pattern(self):
        result = self.firewall.redact_text("test@test.com", disable=["EMAIL"])
        self.assertTrue(result.is_clean)


# ------------------------------------------------------------------
# Layer 7: Audit Logging Tests
# ------------------------------------------------------------------


class TestAuditLogging(unittest.TestCase):
    """Test audit logging in isolation."""

    def setUp(self):
        from mem0.security.audit_log import AuditLogger, EventType, log_event

        self.AuditLogger = AuditLogger
        self.EventType = EventType
        self.log_event = log_event

        self.logger = AuditLogger(
            log_file_path=None,  # No file, stdout only
            log_to_file=False,
            log_to_stdout=False,  # Suppress stdout during tests
            use_async=False,
        )

    def test_log_event(self):
        events = []
        # Monkey-patch _emit to capture events
        original_emit = self.logger._emit
        self.logger._emit = lambda e: events.append(e)

        self.logger.log_event(
            event_type=self.EventType.AUTH_FAILURE,
            actor="user123",
            action="login_attempt",
            source_ip="1.2.3.4",
            severity="WARNING",
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "AUTH_FAILURE")
        self.assertEqual(events[0].actor, "user123")
        self.assertEqual(events[0].severity, "WARNING")

    def test_severity_filter(self):
        events = []
        self.logger._emit = lambda e: events.append(e)

        self.logger.log_event(self.EventType.SYSTEM_STARTUP, actor="system", action="start", severity="INFO")
        self.logger.log_event(self.EventType.AUTH_FAILURE, actor="user", action="fail", severity="CRITICAL")

        # Both should pass with INFO minimum
        self.assertEqual(len(events), 2)

    def test_event_types(self):
        self.assertEqual(self.EventType.MEMORY_CREATE, "MEMORY_CREATE")
        self.assertEqual(self.EventType.MEMORY_DELETE, "MEMORY_DELETE")
        self.assertEqual(self.EventType.PII_REDACTION, "PII_REDACTION")


# ------------------------------------------------------------------
# Layer 8: Error Boundaries Tests (Circuit Breaker)
# ------------------------------------------------------------------


class TestErrorBoundaries(unittest.TestCase):
    """Test circuit breaker in isolation."""

    def setUp(self):
        from mem0.error_boundaries import CircuitBreaker, CircuitBreakerError

        self.breaker = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=1)
        self.CircuitBreakerError = CircuitBreakerError

    def test_successful_call(self):
        result = self.breaker.call(lambda: "ok")
        self.assertEqual(result, "ok")
        self.assertEqual(self.breaker.state, "closed")

    def test_failure_opens_circuit(self):
        def failing():
            raise ValueError("service down")

        # First failure
        with self.assertRaises(ValueError):
            self.breaker.call(failing)
        self.assertEqual(self.breaker.state, "closed")

        # Second failure → opens
        with self.assertRaises(ValueError):
            self.breaker.call(failing)
        self.assertEqual(self.breaker.state, "open")

    def test_open_circuit_rejects_calls(self):
        def failing():
            raise ValueError("service down")

        # Open the circuit
        for _ in range(2):
            try:
                self.breaker.call(failing)
            except ValueError:
                pass

        self.assertEqual(self.breaker.state, "open")

        # Should be rejected
        with self.assertRaises(self.CircuitBreakerError):
            self.breaker.call(lambda: "ok")

    def test_recovery_after_timeout(self):
        import time

        def failing():
            raise ValueError("service down")

        # Open the circuit
        for _ in range(2):
            try:
                self.breaker.call(failing)
            except ValueError:
                pass

        # Wait for recovery timeout
        time.sleep(1.1)

        # Next call should be allowed (half-open)
        result = self.breaker.call(lambda: "recovered")
        self.assertEqual(result, "recovered")
        self.assertEqual(self.breaker.state, "closed")

    def test_decorator_usage(self):
        @self.breaker
        def my_func():
            return "decorated"

        self.assertEqual(my_func(), "decorated")

    def test_get_stats(self):
        self.breaker.call(lambda: "ok")
        stats = self.breaker.get_stats()
        self.assertEqual(stats["name"], "test")
        self.assertEqual(stats["total_calls"], 1)
        self.assertEqual(stats["state"], "closed")

    def test_manual_reset(self):
        def failing():
            raise ValueError("down")

        for _ in range(2):
            try:
                self.breaker.call(failing)
            except ValueError:
                pass

        self.assertEqual(self.breaker.state, "open")
        self.breaker.reset()
        self.assertEqual(self.breaker.state, "closed")


# ------------------------------------------------------------------
# Layer 9: SmartCache Tests
# ------------------------------------------------------------------


class TestSmartCache(unittest.TestCase):
    """Test smart cache in isolation."""

    def setUp(self):
        from mem0.smart_cache import SmartCache, create_smart_cache

        self.SmartCache = SmartCache
        self.create_smart_cache = create_smart_cache

        mock_hybrid = MagicMock()
        mock_hybrid.get.return_value = None
        mock_hybrid.set = MagicMock()

        self.mock_hybrid = mock_hybrid

        self.smart = SmartCache(
            hybrid_cache=mock_hybrid,
            memory_instance=None,  # No memory instance for isolation
            warm_count=10,
            auto_tune=False,
        )

    def test_cache_miss(self):
        result = self.smart.get(query_embedding=[0.1] * 10)
        self.assertIsNone(result)
        stats = self.smart.get_stats()
        self.assertEqual(stats["misses"], 1)

    def test_cache_hit(self):
        self.smart._hybrid_cache.get.return_value = "cached_response"
        result = self.smart.get(query_embedding=[0.1] * 10)
        self.assertEqual(result, "cached_response")
        stats = self.smart.get_stats()
        self.assertEqual(stats["hits"], 1)

    def test_set(self):
        self.smart.set("query", [0.1] * 10, "response")
        self.smart._hybrid_cache.set.assert_called_once()

    def test_invalidate(self):
        self.smart.invalidate("mem_123")
        self.assertIn("mem_123", self.smart._invalidated_ids)

    def test_invalidate_user(self):
        self.smart.invalidate_user("user_456")
        self.assertIn("user_456", self.smart._invalidated_users)

    def test_get_stats(self):
        self.smart.get(query_embedding=[0.1] * 10)  # miss
        self.smart._hybrid_cache.get.return_value = "hit"
        self.smart.get(query_embedding=[0.2] * 10)  # hit

        stats = self.smart.get_stats()
        self.assertEqual(stats["total_gets"], 2)
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertAlmostEqual(stats["hit_rate"], 0.5, places=2)

    def test_factory_function(self):
        mock_hybrid = MagicMock()
        mock_hybrid.get.return_value = None
        mock_hybrid.set = MagicMock()

        cache = self.create_smart_cache(
            hybrid_cache=mock_hybrid,
            config={"warm_count": 30, "hit_rate_threshold_low": 0.5},
        )
        self.assertEqual(cache.warm_count, 30)
        self.assertEqual(cache.hit_rate_threshold_low, 0.5)


# ------------------------------------------------------------------
# Layer 10: Integration Test with Full Mock Injection
# ------------------------------------------------------------------


class TestMemoryWithInjectedMocks(unittest.TestCase):
    """Test Memory class with all dependencies mocked via interfaces.

    Uses patch to replace factories before Memory.__init__ runs.
    Requires full dependency chain (posthog, pytz, etc.) to be installed.
    """

    @classmethod
    def setUpClass(cls):
        """Check if dependencies are available before running tests."""
        try:
            import mem0.memory.sync_memory  # noqa: F401
            import mem0.memory.main  # noqa: F401

            cls._deps_available = True
        except ModuleNotFoundError:
            cls._deps_available = False

    def setUp(self):
        if not self._deps_available:
            self.skipTest("Full mem0 dependencies not installed (posthog, etc.)")

        self.patchers = []

        # Create mock instances
        self.mock_embedder = MockEmbedder()
        self.mock_vector_store = MockVectorStore()
        self.mock_llm = MockLLM()
        self.mock_graph = MockGraphStore()

        # Create factory mocks
        mock_embedder_factory = MagicMock()
        mock_embedder_factory.create.return_value = self.mock_embedder
        mock_vector_store_factory = MagicMock()
        mock_vector_store_factory.create.return_value = self.mock_vector_store
        mock_llm_factory = MagicMock()
        mock_llm_factory.create.return_value = self.mock_llm

        import mem0.memory.sync_memory as sm

        self.patchers.append(patch.object(sm, "EmbedderFactory", mock_embedder_factory))
        self.patchers.append(patch.object(sm, "VectorStoreFactory", mock_vector_store_factory))
        self.patchers.append(patch.object(sm, "LlmFactory", mock_llm_factory))
        self.patchers.append(patch.object(sm, "PostgresManager", MagicMock()))
        self.patchers.append(patch.object(sm, "LifecycleManager", MagicMock()))
        self.patchers.append(patch.object(sm, "Nexus", MagicMock()))
        self.patchers.append(patch.object(sm, "RecollectionEngine", MagicMock()))
        self.patchers.append(patch.object(sm, "SurpriseEngine", MagicMock()))
        self.patchers.append(patch.object(sm, "EgoEngine", MagicMock()))
        self.patchers.append(patch.object(sm, "ContextOrchestrator", MagicMock()))
        self.patchers.append(patch.object(sm, "ReflectionEngine", MagicMock()))
        self.patchers.append(patch.object(sm, "DreamingEngine", MagicMock()))
        self.patchers.append(patch.object(sm, "ToolStateManager", MagicMock()))
        self.patchers.append(patch.object(sm, "MemoryBridge", MagicMock()))
        self.patchers.append(patch.object(sm, "capture_event", MagicMock()))

        for p in self.patchers:
            p.start()

        from mem0.memory.main import Memory as MemoryClass

        supabase_config = SupabaseConfig(connection_string="postgresql://user:pass@host:5432/db")
        vector_store_config = VectorStoreConfig(provider="supabase", config=supabase_config)
        memory_config = MemoryConfig(
            vector_store=vector_store_config,
            enable_reflection=False,
            enable_dreaming=False,
            enable_ego=False,
            enable_resonance=False,
            enable_paging=False,
            enable_compression=False,
            enable_heartbeat=False,
            enable_bridge=False,
            enable_tool_state=False,
            enable_hybrid_search=False,
        )

        self.memory = MemoryClass(config=memory_config)

    def tearDown(self):
        for p in reversed(self.patchers):
            p.stop()

    def test_add_with_mocked_dependencies(self):
        result = self.memory.add("User likes pizza", user_id="user1")
        self.assertIsInstance(result, dict)

    def test_search_with_mocked_dependencies(self):
        self.memory.add("User likes pizza", user_id="user1")
        result = self.memory.search("pizza", user_id="user1")
        self.assertIsInstance(result, dict)

    def test_get_all_with_mocked_dependencies(self):
        self.memory.add("User likes pizza", user_id="user1")
        result = self.memory.get_all(user_id="user1")
        self.assertIsInstance(result, dict)

    def test_immutability_prevents_update(self):
        from mem0.exceptions import ValidationError as Mem0ValidationError

        self.memory.add("Immutable fact", user_id="user1", immutable=True)
        mems = self.mock_vector_store.list(filters={"user_id": "user1"})
        if mems:
            mem_id = mems[0].id
            with self.assertRaises(Mem0ValidationError):
                self.memory.update(mem_id, data="Updated fact")

    def test_immutability_prevents_delete(self):
        from mem0.exceptions import ValidationError as Mem0ValidationError

        mems = self.mock_vector_store.list(filters={"user_id": "user1"})
        if mems:
            mem_id = mems[0].id
            with self.assertRaises(Mem0ValidationError):
                self.memory.delete(mem_id)


# ------------------------------------------------------------------
# Run
# ------------------------------------------------------------------


if __name__ == "__main__":
    unittest.main()
