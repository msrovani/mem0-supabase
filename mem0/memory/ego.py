import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

EGO_PROMPT = """
Analyze the following memories and interaction logs associated with an AI Agent.
Your goal is to synthesize a "Meta-Cognitive Identity" (The Ego) for this agent.

Tasks:
1. Identify Core Behavioral Traits (e.g., helpful, concise, analytical, aggressive).
2. Determine Communication Style (e.g., formal, casual, technical).
3. Extract Evolving Values (what the agent seems to prioritize based on reinforcement).

Return the identity as a concise, high-density narrative or a set of executive directives. 
The agent will use this "Ego" to maintain behavioral consistency.

Input Memories:
{memories}
"""

class EgoEngine:
    """
    Layer 12: Meta-Cognitive Identity Engine.
    Synthesizes the agent's 'Ego' (Persona) based on its memory history.
    """

    def __init__(self, llm=None):
        self.llm = llm

    def synthesize(self, memories: List[Dict[str, Any]]) -> str:
        """
        Synthesizes a persona description from a list of memories.
        """
        if not self.llm:
            logger.warning("No LLM provided to EgoEngine. Returning default persona.")
            return "A helpful and persistent AI agent."

        if not memories:
            return "A new AI agent with no established identity yet."

        # Format memories for the prompt
        memory_text = "\n".join([f"- {m.get('memory', m.get('content', ''))}" for m in memories])
        
        full_prompt = EGO_PROMPT.format(memories=memory_text)
        
        logger.info("Synthesizing agent identity (Layer 12)...")
        messages = [
            {"role": "system", "content": "You are a Meta-Cognitive Identity Synthesizer."},
            {"role": "user", "content": full_prompt}
        ]
        
        try:
            response = self.llm.generate_response(messages)
            return response if isinstance(response, str) else str(response)
        except Exception as e:
            logger.error(f"Failed to synthesize identity: {e}")
            return "An AI agent in a state of cognitive flux."
