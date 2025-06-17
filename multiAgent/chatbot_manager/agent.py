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


def get_clarifying_question(tool_context: ToolContext) -> dict:
    """
    Tool: Get a clarifying question from the reducer agent based on current matches.
    """
    match_results = tool_context.state.get("match_results", [])

    if len(match_results) <= 1:
        return {"question": None, "reason": "Not enough matches to generate question"}

    # Extract descriptions from match results
    item_descriptions = []
    for match in match_results:
        if isinstance(match, dict):
            description = match.get("description", str(match))
        else:
            description = str(match)
        item_descriptions.append(description)

    # Call the reducer agent with the item descriptions
    try:
        # This simulates calling the reducer agent's analyze function
        # In practice, you'd call the reducer agent properly
        from .sub_agents.reducer_agent.agent import analyze_items_and_generate_question
        result = analyze_items_and_generate_question(item_descriptions, tool_context)

        if result.get("question"):
            tool_context.state["current_question"] = result["question"]
            return {"question": result["question"], "status": "success"}
        else:
            return {"question": None, "reason": "Could not generate discriminating question"}

    except Exception as e:
        print(f"Error generating question: {e}")
        return {"question": None, "reason": f"Error: {str(e)}"}


def store_user_answer(answer: str, tool_context: ToolContext) -> dict:
    """
    Tool: Store user's answer to a clarifying question.
    """
    tool_context.state["user_answer"] = answer
    tool_context.state["iteration_count"] = tool_context.state.get("iteration_count", 0) + 1

    return {
        "status": "stored",
        "answer": answer,
        "iteration": tool_context.state["iteration_count"]
    }


def filter_matches_by_answer(tool_context: ToolContext) -> dict:
    """
    Tool: Filter current matches based on user's answer to the question.
    """
    match_results = tool_context.state.get("match_results", [])
    current_question = tool_context.state.get("current_question")
    user_answer = tool_context.state.get("user_answer", "").lower().strip()

    if not current_question or not user_answer:
        return {"status": "error", "message": "Missing question or answer"}

    # Simple filtering logic - in practice, this would be more sophisticated
    # and might involve calling the filter_agent
    filtered_matches = []

    # Normalize the answer
    is_yes = user_answer in ["yes", "y", "true", "1", "yeah", "yep", "si", "sí"]

    for match in match_results:
        description = match.get("description", str(match)).lower()
        should_include = apply_filter_logic(description, current_question, is_yes)

        if should_include:
            filtered_matches.append(match)

    # Update the matches
    tool_context.state["match_results"] = filtered_matches

    return {
        "status": "filtered",
        "original_count": len(match_results),
        "filtered_count": len(filtered_matches),
        "remaining_matches": filtered_matches
    }


def apply_filter_logic(description: str, question: str, is_yes: bool) -> bool:
    """
    Universal filtering logic that works for any type of item and question.
    Extracts keywords from the question and searches for them in the description.
    """
    question_lower = question.lower()
    description_lower = description.lower()

    # Extract the key attribute being asked about
    attribute = extract_question_attribute(question_lower)

    if not attribute:
        # Fallback: conservative approach - include the item
        return True

    # Check if the description contains the attribute
    has_attribute = check_attribute_in_description(description_lower, attribute, question_lower)

    # Return based on user's yes/no answer
    return has_attribute if is_yes else not has_attribute


def extract_question_attribute(question_lower: str) -> str:
    """
    Extract the main attribute being asked about from the question.
    """
    # Color patterns
    colors = [
        "black", "white", "red", "blue", "green", "yellow", "orange", "purple", "pink",
        "brown", "gray", "grey", "silver", "gold", "beige", "tan", "navy", "maroon",
        "lime", "teal", "cyan", "magenta", "violet", "indigo", "turquoise", "coral",
        "cream", "ivory", "khaki", "olive", "burgundy", "crimson", "emerald", "sapphire"
    ]

    for color in colors:
        if color in question_lower:
            return color

    # Material patterns
    materials = [
        "leather", "plastic", "metal", "wood", "glass", "fabric", "cotton", "silk",
        "canvas", "rubber", "vinyl", "synthetic", "nylon", "polyester", "denim",
        "suede", "velvet", "wool", "cashmere", "linen", "bamboo", "ceramic", "stone",
        "paper", "cardboard", "foam", "mesh", "fleece", "jersey", "satin", "lace"
    ]

    for material in materials:
        if material in question_lower:
            return material

    # Size patterns
    size_keywords = ["small", "large", "big", "mini", "tiny", "huge", "oversized", "compact",
                     "medium", "long", "short", "wide", "narrow", "thick", "thin"]

    for size in size_keywords:
        if size in question_lower:
            return size

    # Feature patterns
    features = ["zipper", "zip", "pocket", "strap", "handle", "button", "buckle",
                "velcro", "elastic", "padded", "cushioned", "waterproof", "wireless",
                "bluetooth", "rechargeable", "battery", "adjustable", "removable",
                "detachable", "foldable", "collapsible", "transparent", "clear",
                "reflective", "reflector"]

    for feature in features:
        if feature in question_lower:
            return feature

    # Brand patterns (extract brand names from questions like "Is your item made by Nike?")
    brands = ["nike", "adidas", "apple", "samsung", "sony", "canon", "nikon", "coach",
              "gucci", "prada", "louis vuitton", "chanel", "rolex", "casio", "timex"]

    for brand in brands:
        if brand in question_lower:
            return brand

    # Condition patterns
    conditions = ["new", "used", "damaged", "broken", "old", "vintage", "dirty", "clean"]

    for condition in conditions:
        if condition in question_lower:
            return condition

    # Style patterns
    styles = ["round", "square", "rectangular", "oval", "circular", "triangular",
              "curved", "straight", "flat", "smooth", "textured", "patterned",
              "plain", "striped", "dotted", "floral", "geometric", "solid"]

    for style in styles:
        if style in question_lower:
            return style

    return None


def check_attribute_in_description(description_lower: str, attribute: str, question_lower: str) -> bool:
    """
    Check if the attribute exists in the item description.
    Uses smart matching that considers context and synonyms.
    """
    # Direct match
    if attribute in description_lower:
        return True

    # Handle synonyms and related terms
    synonyms = {
        "large": ["big", "huge", "oversized", "xl", "xxl", "jumbo", "giant", "tote"],
        "small": ["mini", "tiny", "compact", "little", "pocket", "miniature"],
        "metal": ["metallic", "steel", "aluminum", "brass", "copper", "iron", "chrome"],
        "plastic": ["polymer", "acrylic", "vinyl", "pvc"],
        "waterproof": ["water resistant", "weatherproof", "water-resistant"],
        "wireless": ["bluetooth", "wi-fi", "wifi", "cordless"],
        "zipper": ["zip", "zipped"],
        "strap": ["handle", "belt", "cord"],
        "new": ["brand new", "unused", "mint", "fresh"],
        "old": ["vintage", "antique", "aged", "worn"],
        "damaged": ["broken", "cracked", "torn", "scratched", "chipped"],
        "round": ["circular", "spherical"],
        "square": ["rectangular", "box-shaped"],
        "transparent": ["clear", "see-through", "translucent"],
        "soft": ["flexible", "bendable", "pliable"],
        "hard": ["rigid", "solid", "firm", "sturdy"]
    }

    # Check synonyms
    if attribute in synonyms:
        for synonym in synonyms[attribute]:
            if synonym in description_lower:
                return True

    # Check if any synonym lists contain our attribute
    for main_word, synonym_list in synonyms.items():
        if attribute in synonym_list and main_word in description_lower:
            return True

    # Special handling for certain question types

    # For electronic/battery questions
    if attribute == "electronic" or attribute == "battery":
        electronic_indicators = ["battery", "rechargeable", "usb", "charger", "digital",
                                 "lcd", "led", "screen", "display", "electronic", "powered"]
        return any(indicator in description_lower for indicator in electronic_indicators)

    # For text/writing questions
    if "text" in question_lower or "writing" in question_lower:
        text_indicators = ["text", "writing", "words", "letters", "logo", "brand",
                           "label", "printed", "embossed", "engraved"]
        return any(indicator in description_lower for indicator in text_indicators)

    # For moving parts questions
    if "moving parts" in question_lower:
        moving_indicators = ["button", "switch", "dial", "lever", "hinge", "sliding",
                             "rotating", "adjustable", "extendable", "telescopic"]
        return any(indicator in description_lower for indicator in moving_indicators)

    return False


def format_final_result(item_data: dict, tool_context: ToolContext) -> dict:
    """
    Tool: Format the final result when we have exactly one match.
    """
    tool_context.state["workflow_complete"] = True

    description = item_data.get("description", "Item")
    contact = item_data.get("contact_info", "Check with front desk")
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
    model="gemini-2.0-flash",
    description=(
        "Lost Items Workflow Manager. Orchestrates the complete lost item search process: "
        "collects user info, coordinates with matcher/reducer/filter agents, manages iterative filtering, "
        "and provides final results or helpful guidance when no matches found."
    ),
    instruction="""
You are the Lost Items Workflow Manager. Your job is to guide users through finding their lost items using a multi-agent workflow.

🔄 **WORKFLOW PHASES:**

**Phase 1: Information Collection**
- Ask user for item description and location where they lost it
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
1. Use `get_clarifying_question()` to get a discriminating question
2. Present ONLY the question to user (don't show match details)
3. When user answers: use `store_user_answer(answer)`
4. Use `filter_matches_by_answer()` to reduce the match list
5. Check new match count and repeat if needed

🔧 **KEY TOOLS:**
- `initiate_search(description, location)` - Start the search
- `check_workflow_phase()` - Check current state  
- `store_match_results(results)` - Save matcher results
- `get_clarifying_question()` - Get discriminating question from reducer agent
- `store_user_answer(answer)` - Save user's response
- `filter_matches_by_answer()` - Apply filtering based on answer
- `format_final_result(item)` - Format successful final result

⚠️ **CRITICAL RULES:**
1. Always check workflow phase before taking action
2. Never show raw match data to users during filtering
3. Present only ONE question at a time during filtering
4. Maximum 10 filtering iterations to prevent infinite loops
5. Handle edge cases gracefully (no matches, too many iterations)

🎯 **CONVERSATION FLOW:**
- User describes lost item → initiate_search()
- Get matches from matcher_agent → store_match_results()
- If multiple matches → get_clarifying_question() → ask user
- User answers → store_user_answer() → filter_matches_by_answer()
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

Be conversational and helpful throughout the process!
""",
    sub_agents=[
        matcher_agent,
        reducer_agent,
        filter_agent
    ],
    tools=[
        initiate_search,
        check_workflow_phase,
        store_match_results,
        get_clarifying_question,
        store_user_answer,
        filter_matches_by_answer,
        format_final_result,
        AgentTool(matcher_agent),
        AgentTool(reducer_agent),
        AgentTool(filter_agent)
    ],
)