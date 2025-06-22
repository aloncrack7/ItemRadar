# chatbot_agent_dir/agent.py - Improved version
import os
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.agent_tool import AgentTool

# Load environment variables
load_dotenv()

# Import sub-agents (assuming they exist in sub-directories)
from .sub_agents.matcher_agent.agent import matcher_agent
from .sub_agents.reducer_agent.agent import reducer_agent
from .sub_agents.filter_agent.agent import filter_agent
from .sub_agents.lens_agent.agent import lens_agent


def initiate_search(description: str, location: str, tool_context: ToolContext) -> dict:
    """
    Tool: kick off the lost-item search workflow.
    """
    tool_context.state["search_params"] = {
        "description": description,
        "location": location
    }
    tool_context.state["has_search_params"] = True

    message = f"🔍 Searching for items matching \"{description}\" in {location}…"
    return {"status": "started", "message": message}


def check_workflow_phase(tool_context: ToolContext) -> dict:
    """
    Tool: Check what phase of the workflow we're in and what data we have.
    """
    state = tool_context.state

    phase_info = {
        "has_search_params": state.get("has_search_params", False),
        "search_params": state.get("search_params"),
        "has_match_results": "match_results" in state,
        "match_count": len(state.get("match_results", [])),
        "iteration_count": state.get("iteration_count", 0),
        "current_question": state.get("current_question"),
        "filtering_complete": state.get("filtering_complete", False),
        "phase": "unknown"
    }

    # Determine current phase
    if not phase_info["has_search_params"]:
        phase_info["phase"] = "collecting_info"
    elif phase_info["has_search_params"] and not phase_info["has_match_results"]:
        phase_info["phase"] = "ready_to_search"
    elif phase_info["match_count"] == 0:
        phase_info["phase"] = "no_matches"
    elif phase_info["match_count"] == 1:
        phase_info["phase"] = "single_match"
    elif phase_info["match_count"] > 1:
        phase_info["phase"] = "multiple_matches"

    return phase_info


def store_match_results(match_results: list[dict], tool_context: ToolContext) -> dict:
    """
    Tool: Store match results from matcher agent in session state.
    """
    tool_context.state["match_results"] = match_results
    tool_context.state["initial_search_done"] = True

    return {
        "status": "stored",
        "match_count": len(match_results),
        "message": f"Stored {len(match_results)} potential matches"
    }


def store_user_answer(question:str, answer: str, tool_context: ToolContext) -> dict:
    """
    Tool: Store user's answer to a clarifying question.
    """
    tool_context.state["user_answer"] = answer
    tool_context.state["current_question"] = question
    tool_context.state["iteration_count"] = tool_context.state.get("iteration_count", 0) + 1

    return {
        "status": "stored",
        "answer": answer,
        "current_question": question,
        "iteration": tool_context.state["iteration_count"]
    }





def format_final_result(item_data: dict, tool_context: ToolContext) -> dict:
    """
    Tool: Format the final result when we have exactly one match.
    """
    tool_context.state["workflow_complete"] = True

    description = item_data.get("description", "Item")
    contact = item_data.get("contact", "Check with front desk")
    location_found = item_data.get("location", "Unknown location")

    message = f"✅ **Found your item!**\n\n📋 **Description**: {description}\n📍 **Found at**: {location_found}\n📞 **Contact**: {contact}"

    return {
        "status": "complete",
        "message": message,
        "item": item_data
    }


# Main chatbot manager agent
root_agent = Agent(
    name="chatbot_manager",
    model="gemini-2.5-flash",
    description=(
        "Lost Items Workflow Manager. Orchestrates the complete lost item search process: "
        "collects user info, coordinates with matcher/reducer/filter agents, manages iterative filtering, "
        "and provides final results or helpful guidance when no matches found."
    ),
    instruction="""
You are the Lost Items Workflow Manager. Your job is to guide users through finding their lost items using a multi-agent workflow.

🔄 **WORKFLOW PHASES:**

**Phase 1: Information Collection**
- Ask user for item description or picture and location where they lost it
    - If the user passes a photo pass the photo to the lens_agent to extract both the description and location of it
- Use `initiate_search(description, location)` when you have both pieces

**Phase 2: Search Execution**  
- Use `check_workflow_phase()` to understand current state
- When phase is "ready_to_search": Call matcher_agent to find potential matches
- Use `store_match_results(results)` to save the results

**Phase 3: Result Processing**
Based on match count:
- 0 matches → Provide "no matches found" guidance
- 1 match → Use `format_final_result(item)` to present the result  
- 2+ matches → Start filtering process

**Phase 4: Iterative Filtering (for multiple matches)**
1. Call reducer_agent with the list of objects to get a discriminating question
2. Present ONLY the question to user (don't show match details)
3. When user answers and the question: use `store_user_answer(answer)`
4. Call filter_agent with the list of objects, the question and the answer to reduce the match list
5. Check new match count and repeat if needed

🔧 **KEY TOOLS:**
- `initiate_search(description, location)` - Start the search
- `check_workflow_phase()` - Check current state  
- `store_match_results(results)` - Save matcher results

- `store_user_answer(answer)` - Save user's response and question
- `format_final_result(item)` - Format successful final result

⚠️ **CRITICAL RULES:**
1. Always check workflow phase before taking action
2. Never show raw match data to users during filtering
3. Present only ONE question at a time during filtering
4. Maximum 10 filtering iterations to prevent infinite loops
5. Handle edge cases gracefully (no matches, too many iterations)
6. **IMPORTANT**: You have access to the full conversation history through the Google ADK session service. Use this context to understand what information has already been provided and avoid asking for the same information twice.

🎯 **CONVERSATION FLOW:**
- User describes lost item → initiate_search()
- Get matches from matcher_agent → store_match_results()
- If multiple matches → Call reducer_agent → ask user
- User answers and question → store_user_answer() → call filter_agent
- Repeat filtering until 0 or 1 matches remain
- Present final result or "not found" message

📝 **STATE TRACKING:**
The system maintains state for:
- search_params: user's description and location
- match_results: current list of potential matches
- iteration_count: number of filtering rounds
- current_question: last question asked
- user_answer: user's last response
- workflow_complete: completion flag

💬 **CONVERSATION CONTEXT:**
- You have access to the full conversation history through the session
- Review previous messages to understand what information has already been provided
- Don't ask for information that was already given in previous messages
- Be conversational and build upon the existing conversation
- If the user provides additional details in a follow-up message, incorporate them into your understanding
- **ENHANCED CONTEXT**: The user input may include a "CONVERSATION HISTORY" section followed by "CURRENT MESSAGE". Always read and consider the full conversation history before responding.

Be conversational and helpful throughout the process! Remember that you're having a continuous conversation with the user, so use the conversation history to provide context-aware responses.
""",
    sub_agents=[
        matcher_agent,
        reducer_agent,
        filter_agent,
        lens_agent
    ],
    tools=[
        initiate_search,
        check_workflow_phase,
        store_match_results,
        #get_clarifying_question,
        store_user_answer,
        #filter_matches_by_answer,
        format_final_result,
        AgentTool(matcher_agent),
        AgentTool(reducer_agent),
        AgentTool(filter_agent),
        AgentTool(lens_agent)
    ],
)