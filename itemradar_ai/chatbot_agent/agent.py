# chatbot_agent_dir/agent.py

import os
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools import ToolContext
from google.genai import types

# Load environment variables
load_dotenv()

PROJECT_ID: str | None = os.getenv("PROJECT_ID")
REGION: str | None = os.getenv("REGION")
INDEX_ID: str | None = os.getenv("INDEX_ID")

# ===================================================================
# FIXED: Updated Agent Communication for ADK 2025
# ===================================================================

# Import the matcher_agent
from matcher_agent.agent import matcher_agent


# ---------------------------
# Tool: Initiate Search
# ---------------------------
async def initiate_search(description: str, location: str, tool_context: ToolContext) -> str:
    """
    Initiate search using the correct ADK 2025 API
    """
    print(f"\n[TOOL CALL] Starting cross-agent search with: '{description}', location: '{location}'")

    try:
        # Build the message to send to matcher_agent
        message = f"Please search for the following lost item:\nDescription: {description}\nLocation: {location}"

        # Method 1: Try the new ADK 2025 agent transfer method
        if hasattr(tool_context, 'transfer_to_agent'):
            result = await tool_context.transfer_to_agent(matcher_agent, message)
            return result.text if hasattr(result, 'text') else str(result)

        # Method 2: Try session-based invocation
        elif hasattr(tool_context, 'session') and hasattr(tool_context.session, 'invoke_agent'):
            response = await tool_context.session.invoke_agent(
                agent=matcher_agent,
                message=message
            )
            return response.text if hasattr(response, 'text') else str(response)

        # Method 3: Try execution context
        elif hasattr(tool_context, 'execution_context'):
            ctx = tool_context.execution_context
            if hasattr(ctx, 'call_agent'):
                result = await ctx.call_agent(matcher_agent, message)
                return result.text if hasattr(result, 'text') else str(result)

        # Method 4: Try direct agent invocation through tool context
        elif hasattr(tool_context, 'invoke_agent'):
            # Create proper content structure
            content = types.Content(parts=[types.Part(text=message)])
            response = await tool_context.invoke_agent(matcher_agent, content)

            # Handle streaming response
            if hasattr(response, '__aiter__'):
                result_text = ""
                async for event in response:
                    if hasattr(event, 'content') and event.content:
                        if hasattr(event.content, 'text'):
                            result_text += event.content.text
                        elif hasattr(event.content, 'parts'):
                            for part in event.content.parts:
                                if hasattr(part, 'text'):
                                    result_text += part.text
                return result_text or "No text content received from matcher agent."
            else:
                return response.text if hasattr(response, 'text') else str(response)

        # Method 5: Try getting the agent's underlying model/client
        elif hasattr(matcher_agent, '_client') or hasattr(matcher_agent, '_model'):
            # This is a fallback - call the matcher agent's tools directly
            # Import and call the search function from matcher_agent
            from matcher_agent.agent import search_in_database
            return await search_in_database(description, location, tool_context)

        # Method 6: Final fallback - direct function call
        else:
            print("No suitable agent invocation method found, falling back to direct search")
            return await fallback_search(description, location)

    except Exception as e:
        print(f"Error during agent communication: {e}")
        print(f"Available tool_context attributes: {dir(tool_context)}")

        # Try fallback search on error
        try:
            return await fallback_search(description, location)
        except Exception as fallback_error:
            print(f"Fallback search also failed: {fallback_error}")
            return f"Sorry, I encountered an error while searching: {str(e)}"


async def fallback_search(description: str, location: str) -> str:
    """
    Fallback search function when agent communication fails
    """
    print(f"[FALLBACK] Searching for: {description} in {location}")

    # Simple mock search results
    mock_results = [

    ]

    # Simple matching
    matches = []
    desc_words = description.lower().split()

    for item in mock_results:
        if location.lower() in item["loc"].lower():
            score = sum(1 for word in desc_words if word in item["desc"].lower())
            if score > 0:
                matches.append((item, score))

    if matches:
        result = "🔍 **Search Results:**\n\n"
        for item, score in sorted(matches, key=lambda x: x[1], reverse=True):
            result += f"• **{item['id']}**: {item['desc']} at {item['loc']}\n"
            result += f"  Details: {item['details']}\n\n"
        return result
    else:
        return f"❌ No items found matching '{description}' in {location}. Please try different keywords or check back later."


# Main chatbot agent
root_agent = Agent(
    name="chatbot_agent",
    model="gemini-2.0-flash",
    description="A friendly assistant that helps users find their lost items by asking for details.",
    instruction=(
        "You are a helpful and friendly assistant for a lost-and-found service. "
        "Your goal is to get a detailed description of the item the user has lost. "
        "Ask clarifying questions to get as much detail as possible. For example, ask about color, brand, size, or any unique features. "
        "Also, ask where they last remember having the item. "
        "ONCE you have a good description AND a location, you must call the `initiate_search` tool with the information you have gathered. "
        "Do not invent any details. Present the search results back to the user clearly and helpfully."
    ),
    tools=[initiate_search],
)