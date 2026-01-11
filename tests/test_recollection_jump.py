import unittest
from unittest.mock import MagicMock
from datetime import datetime
import pytz
from mem0.recollection import RecollectionEngine

class TestRecollectionEngine(unittest.TestCase):
    def setUp(self):
        # Mock Memory Instance
        self.mock_memory = MagicMock()
        self.mock_memory.enable_graph = True
        self.mock_memory.graph = MagicMock()
        
        # Initialize Engine
        self.engine = RecollectionEngine(self.mock_memory)

    def test_recollect_with_graph_jump(self):
        # Setup Mock search results
        mock_memories = [
            {
                "id": "1", 
                "memory": "Alice likes tennis.", 
                "score": 0.9, 
                "importance_score": 1.0, 
                "created_at": datetime.now(pytz.utc).isoformat()
            },
            {
                "id": "2", 
                "memory": "Bob likes soccer.", 
                "score": 0.8, 
                "importance_score": 0.5,
                "created_at": datetime.now(pytz.utc).isoformat()
            }
        ]
        
        # Initial relations returned by Memory.search (simulating what the search query found)
        initial_relations = [
            {"source": "QueryUser", "relation": "searched", "target": "Sports"}
        ]
        
        self.mock_memory.search.return_value = {
            "results": mock_memories,
            "relations": initial_relations
        }
        
        # Setup Graph Store Jump results
        # When searching for "Alice likes tennis.", return relation about Alice
        def graph_search_side_effect(query):
            if "Alice" in query:
                return [{"source": "Alice", "relation": "member_of", "target": "TennisClub"}]
            if "Bob" in query:
                return [{"source": "Bob", "relation": "brother_of", "target": "Charlie"}]
            return []
            
        self.mock_memory.graph.search.side_effect = graph_search_side_effect

        # Execute Recollection
        result = self.engine.recollect("What do they like?", enable_graph_jump=True)
        
        # Verify Memories
        self.assertEqual(len(result["memories"]), 2)
        self.assertEqual(result["memories"][0]["id"], "1")
        
        # Verify Associations
        associations = result["associations"]
        
        # Expecting: 
        # 1. Initial relation (QueryUser -> Sports)
        # 2. Jump from Alice (Alice -> TennisClub)
        # 3. Jump from Bob (Bob -> Charlie) - assuming Bob is in top 2 (since limit is 10)
        
        expected_sources = [a["source"] for a in associations]
        self.assertIn("QueryUser", expected_sources)
        self.assertIn("Alice", expected_sources)
        self.assertIn("Bob", expected_sources)
        
        print("Associations found:", associations)

    def test_recollect_no_graph(self):
        self.mock_memory.enable_graph = False
        self.mock_memory.search.return_value = {"results": []}
        
        result = self.engine.recollect("test")
        self.assertEqual(result["associations"], [])

if __name__ == "__main__":
    unittest.main()
