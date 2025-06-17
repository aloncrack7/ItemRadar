# chatbot_agent_dir/agent.py
import os
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext

# Load environment variables
load_dotenv()


def initiate_search(description: str, location: str, tool_context: ToolContext) -> dict:
    """
    Tool: kick off the lost-item search workflow.

    1. Save the user's description & location in session state.
    2. Return a confirmation that search has started.
    """
    # 1) Persist search parameters - FIXED: Use tool_context.state directly
    tool_context.state["search_params"] = {
        "description": description,
        "location": location
    }

    # 2) Confirm
    message = f"🔍 Searching for items matching \"{description}\" in {location}…"
    return {"status": "started", "message": message}


# Main chatbot agent
chatbot_agent = Agent(
    name="chatbot_agent",
    model="gemini-2.0-flash",
    description=(
        "A friendly assistant that helps users find their lost items. "
        "Gathers a description and location, then initiates a search."
    ),
    instruction="""
When the user gives you a lost-item description and location:
1) Call the `initiate_search` tool with `description` and `location`.
2) Return the tool's `message` verbatim to the user.

If the user hasn't yet provided both pieces, ask for whichever is missing.
""",
    tools=[initiate_search],
)

if __name__ == "__main__":
    # Quick local test
    from types import SimpleNamespace


    async def run_test():
        # Create a mock context with proper state structure
        ctx = SimpleNamespace()
        ctx.state = {}  # This mimics the ToolContext.state structure

        # User says: "I lost my red wallet at the cafe"
        result = await chatbot_agent.run(
            ctx,
            # ADK will wrap the text in a types.Content; simplified here:
            SimpleNamespace(content=SimpleNamespace(parts=[SimpleNamespace(text="I lost my red wallet at the cafe")]))
        )
        print(result)


    import asyncio

    asyncio.run(run_test())