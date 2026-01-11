import unittest
from unittest.mock import MagicMock
from mem0 import Memory

class TestMemoryInteraction(unittest.TestCase):
    def setUp(self):
        # Create Memory with mocked components
        self.memory = Memory()
        self.memory.recollection = MagicMock()
        self.memory.get_all = MagicMock()
        self.memory.add = MagicMock()

    def test_process_interaction(self):
        # Setup mocks
        self.memory.recollection.recollect.return_value = {
            "memories": [{"id": 1, "text": "fact"}],
            "associations": [{"source": "a", "target": "b"}],
            "persona_identity": "Helpful AI"
        }
        self.memory.get_all.return_value = [
            {"created_at": "2023-01-01T10:00:00Z", "id": "msg1", "text": "Hi"}
        ]
        
        # Call method
        user_input = "Hello world"
        user_id = "user123"
        context = self.memory.process_interaction(
            user_input, 
            user_id=user_id,
            learn=True
        )
        
        # Verify Context Structure
        self.assertIn("memories", context)
        self.assertIn("associations", context)
        self.assertIn("history", context)
        self.assertIn("persona", context)
        
        # Verify retrieved data
        self.assertEqual(context["persona"], "Helpful AI")
        self.assertEqual(len(context["memories"]), 1)
        self.assertEqual(len(context["history"]), 1)
        
        # Verify Calls
        self.memory.recollection.recollect.assert_called_with(
            user_input, 
            filters=None, 
            limit=10, 
            enable_graph_jump=True
        )
        
        self.memory.get_all.assert_called()
        
        # Verify "Learn" was triggered
        self.memory.add.assert_called()
        args, kwargs = self.memory.add.call_args
        self.assertEqual(kwargs["user_id"], user_id)
        self.assertEqual(args[0][0]["content"], user_input)

if __name__ == "__main__":
    unittest.main()
