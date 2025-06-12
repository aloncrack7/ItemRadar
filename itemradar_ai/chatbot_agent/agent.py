# chatbot_agent_dir/agent.py

import os
from dotenv import load_dotenv
from google.adk.agents import Agent

# Cargar variables de entorno desde .env o entorno del contenedor
# Important: .env should be in the 'your_project_root' directory, not inside 'chatbot_agent_dir'
load_dotenv()

PROJECT_ID: str | None = os.getenv("PROJECT_ID")
REGION: str | None = os.getenv("REGION")
INDEX_ID: str | None = os.getenv("INDEX_ID")

# ===================================================================
# AGENT 1: The Finder Agent (The "Interviewer")
# This is the agent the user talks to.
# ===================================================================

def initiate_search(description: str, location: str = "") -> str:
    # This print will appear in the terminal where you run adk run
    print(f"\n[TOOL CALL]: Vamos a buscar compa con descripción: '{description}' y ubicación: '{location}'")
    # In a real scenario, this would call your actual search logic (e.g., the matcher_agent)
    return "Okay, I've initiated a search for your item with the provided details. I'll let you know if I find anything similar!"

# This is the agent you wanted to build. Note the detailed instruction.
# Make sure the agent variable name is consistent (e.g., root_agent or main_agent)
# as ADK often looks for a variable named 'root_agent' by default.
# For simplicity, we'll keep it 'chatbot_agent' and specify it if needed.
root_agent  = Agent(
    name="chatbot_agent",
    model="gemini-2.0-flash",
    description="A friendly assistant that helps users find their lost items by asking for details.",
    instruction=(
        "You are a helpful and friendly assistant for a lost-and-found service. "
        "Your goal is to get a detailed description of the item the user has lost. "
        "Ask clarifying questions to get as much detail as possible. For example, ask about color, brand, size, or any unique features. "
        "Also, ask where they last remember having the item. "
        "ONCE you have a good description, and ONLY then, you must call the `initiate_search` tool with the information you have gathered. "
        "Do not invent any details. Relay the search results back to the user in a clear, easy-to-read format."
    ),
    tools=[initiate_search],
)

# Important: If your agent variable is not named 'root_agent' by default
# or if you have multiple agents, you might need to specify which one to run.
# For a single agent in 'agent.py', 'adk run chatbot_agent_dir' usually finds it.