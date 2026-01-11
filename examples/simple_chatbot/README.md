# Simple Mem0 Chatbot Example

This example demonstrates how to build a text-based chatbot that uses **Mem0** as its cognitive layer.

It utilizes the unified `process_interaction` API ("Smart Pipe") to handle:
1.  **Recall**: Retrieving relevant past memories.
2.  **Association**: Finding related concepts in the Knowledge Graph.
3.  **History**: Managing short-term conversation context.
4.  **Learning**: Automatically storing useful facts from user input.

## Features
- **Unified Interaction**: A single call `memory.process_interaction(...)` handles the entire cognitive pipeline.
- **Context Viz**: The script prints the "Brain" state (what the AI retrieved) before answering, so you can see Mem0 working.

## How to Run

1.  Ensure you have `mem0` installed and your environment configured (Supabase/OpenAI keys).
2.  Run the script:

```bash
python chat.py
```

3.  Chat with the agent! Try telling it facts about yourself, changing topics, and then asking about those facts later.

## Code Highlight

```python
# The only line you need to make your AI smart:
context = memory.process_interaction(
    user_input, 
    user_id="user_123", 
    run_id="session_001"
)
```
