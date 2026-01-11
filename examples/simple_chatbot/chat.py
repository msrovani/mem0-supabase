import os
import sys

# Ensure we can import mem0 from the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from mem0 import Memory

def simulate_llm_response(query, context):
    """
    Simulates an LLM generating a response based on the provided context.
    In a real app, this would be a call to full_prompt = ...; llm.generate(full_prompt)
    """
    print("\n" + "="*40)
    print("🤖 AI BRAIN (Context for Generation)")
    print("="*40)
    
    # 1. Persona
    print(f"🎭 PERSONA: {context.get('persona', 'Standard Assistant')}")
    
    # 2. Memories
    memories = context.get('memories', [])
    print(f"📚 RELEVANT MEMORIES ({len(memories)}):")
    for m in memories:
        print(f"   - {m.get('memory', 'Unknown')}")
        
    # 3. Graph
    associations = context.get('associations', [])
    if associations:
        print(f"🕸️ KNOWLEDGE GRAPH ({len(associations)}):")
        for a in associations:
            print(f"   - {a.get('source')} --{a.get('relation')}--> {a.get('target')}")
            
    # 4. History
    history = context.get('history', [])
    print(f"📜 SHORT-TERM HISTORY ({len(history)}):")
    for h in history[-3:]: # Show last 3
        role = h.get('role', 'unknown')
        content = h.get('content', '')[:50] + "..."
        print(f"   - {role}: {content}")
        
    print("="*40)
    
    return f"I have processed your input regarding '{query}'. I have recalled {len(memories)} relevant facts and found {len(associations)} related concepts to answer you."

def main():
    print("🧠 Mem0 Chatbot Example")
    print("Type 'exit' to quit.\n")
    
    # Initialize Memory
    # Ensure you have your configs set up (e.g. environment vars for Supabase/OpenAI)
    try:
        memory = Memory()
    except Exception as e:
        print(f"❌ Failed to initialize Mem0. Check your configuration.\nError: {e}")
        return

    user_id = "demo_user_001"
    run_id = "session_alpha"

    while True:
        try:
            user_input = input("\n👤 You: ").strip()
            if user_input.lower() in ['exit', 'quit']:
                print("👋 Goodbye!")
                break
                
            if not user_input:
                continue

            print("... Thinking (Retrieving Context & Learning) ...")
            
            # THE CORE INTEGRATION: ONE LINE
            # ---------------------------------------------------------
            context = memory.process_interaction(
                user_input, 
                user_id=user_id, 
                run_id=run_id
            )
            # ---------------------------------------------------------
            
            # Generate Response using the rich context
            response = simulate_llm_response(user_input, context)
            
            print(f"\n🤖 AI: {response}")
            
            # Note: In a real 'process_interaction', the 'learning' (add) happens automatically
            # inside the method, so we don't need to manually call add() for the user input.
            
            # Optimization: If we wanted to store the *assistant's* response, we could do:
            # memory.add(response, user_id=user_id, agent_id="chatbot", run_id=run_id)

        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"⚠️ Error: {e}")

if __name__ == "__main__":
    main()
