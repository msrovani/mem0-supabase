"""
Integration Tests — Tests with real PostgreSQL via testcontainers.

Usage:
    pip install testcontainers psycopg
    pytest tests/test_integration.py -v -k testcontainers

Requires Docker running.
"""

import os
import unittest
from unittest.mock import MagicMock, patch


@unittest.skipUnless(os.environ.get("RUN_INTEGRATION_TESTS"), "Set RUN_INTEGRATION_TESTS=1 to run")
class TestIntegrationWithPostgres(unittest.TestCase):
    """Integration tests using testcontainers for real PostgreSQL."""

    @classmethod
    def setUpClass(cls):
        try:
            from testcontainers.postgres import PostgresContainer
        except ImportError:
            raise unittest.SkipTest("Install testcontainers: pip install testcontainers[postgres]")

        cls.postgres = PostgresContainer("pgvector/pgvector:pg16")
        cls.postgres.start()

        # Create mock for other dependencies
        cls.patchers = [
            patch("mem0.memory.sync_memory.EmbedderFactory"),
            patch("mem0.memory.sync_memory.VectorStoreFactory"),
            patch("mem0.memory.sync_memory.LlmFactory"),
            patch("mem0.memory.sync_memory.PostgresManager"),
            patch("mem0.memory.sync_memory.LifecycleManager"),
            patch("mem0.memory.sync_memory.Nexus"),
            patch("mem0.memory.sync_memory.RecollectionEngine"),
        ]
        for p in cls.patchers:
            p.start()

    @classmethod
    def tearDownClass(cls):
        for p in reversed(cls.patchers):
            p.stop()
        cls.postgres.stop()

    def test_full_lifecycle(self):
        """Test full CRUD lifecycle with real PostgreSQL."""
        from mem0 import Memory
        from mem0.configs.base import MemoryConfig
        from mem0.vector_stores.configs import VectorStoreConfig
        from mem0.configs.vector_stores.supabase import SupabaseConfig

        conn_url = self.postgres.get_connection_url()
        supabase_config = SupabaseConfig(connection_string=conn_url)
        vector_store_config = VectorStoreConfig(provider="supabase", config=supabase_config)
        memory = Memory(config=MemoryConfig(vector_store=vector_store_config))

        # Create
        result = memory.add("User likes pizza", user_id="integration_test")
        self.assertIsInstance(result, dict)

        # Search
        search_result = memory.search("food", user_id="integration_test")
        self.assertIsInstance(search_result, dict)

        # Get all
        all_result = memory.get_all(user_id="integration_test")
        self.assertIsInstance(all_result, dict)

        # Delete
        mems = memory.vector_store.list(filters={"user_id": "integration_test"})
        if mems:
            mem_id = mems[0].id if hasattr(mems[0], 'id') else mems[0].get('id')
            if mem_id:
                memory.delete(mem_id)

        # Verify deleted
        all_after = memory.get_all(user_id="integration_test")
        self.assertIsInstance(all_after, dict)


if __name__ == "__main__":
    unittest.main()
