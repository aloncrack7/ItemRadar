import os
import re
import json # Import json to help parse the list of dicts
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext
from google.generativeai import GenerativeModel, configure as configure_gemini

load_dotenv()

# Configure Gemini API
configure_gemini(api_key=os.getenv("GEMINI_API_KEY"))


def ai_filter_objects(texts: list[str], question: str, answer: str, tool_context: ToolContext) -> dict:
    """
    Filters the list of item descriptions using AI reasoning based on the user's answer
    to a specific question.
    """
    print(f"--- Tool: ai_filter_objects called with question='{question}', answer='{answer}', texts={texts} ---")

    if not texts:
        return {"filtered": [], "count": 0, "message": "No items to filter"}

    # Prepare the prompt for the Gemini model
    # It's crucial that the prompt aligns with the data you pass here (e.g., using 'description' field)
    item_descriptions = [item_dict.get("description", "") for item_dict in texts] if isinstance(texts[0], dict) else texts

    prompt = f"""
    You are an intelligent item filter. Your task is to filter a given list of item descriptions.
    You will be provided with a question that was asked about an item, and the user's yes/no answer to that question.
    Your goal is to return only the items from the original list that are consistent with the user's answer.

    Original list of item descriptions (each description separated by a semicolon):
    {'; '.join(item_descriptions)}

    The question asked was: "{question}"
    The user's answer to the question was: "{answer}"

    Based on the question and the user's answer, carefully select only the items from the original list that fit the description.
    For example, if the question was "Is your item red?" and the answer was "yes", you should only return items that are described as red.
    If the answer was "no", you should return items that are NOT described as red.

    Return the filtered item descriptions as a semicolon-separated list. Do NOT include any other text, explanations, or formatting.
    If no item descriptions match the criteria, return an empty string.
    """

    try:
        model = GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        filtered_descriptions_str = response.text.strip()

        filtered_descriptions = [desc.strip() for desc in filtered_descriptions_str.split(';') if desc.strip()]

        # Reconstruct the original item dictionaries based on filtered descriptions
        filtered_items = []
        original_item_map = {item_dict.get("description", ""): item_dict for item_dict in texts} if isinstance(texts[0], dict) else {}

        for desc in filtered_descriptions:
            if desc in original_item_map:
                filtered_items.append(original_item_map[desc])
            # Handle cases where description might be slightly rephrased by AI
            else:
                # Fallback: simple text match if exact description isn't found
                for original_item_dict in texts:
                    if desc in original_item_dict.get("description", ""):
                        filtered_items.append(original_item_dict)
                        break

        normalized_answer = answer.strip().lower()
        is_yes_or_no = normalized_answer in ["yes", "y", "true", "1", "no", "n", "false", "0"]

        if not filtered_items and is_yes_or_no and texts:
            print(f"--- Warning: AI filtering removed all items unexpectedly, returning original list as safety. ---")
            filtered_items = texts.copy()

    except Exception as e:
        print(f"Error calling Gemini model for filtering: {e}")
        filtered_items = texts.copy()
        print(f"--- Falling back to returning original list due to AI error. ---")

    tool_context.state["filtered_results"] = filtered_items
    tool_context.state["last_filter_count"] = len(filtered_items)
    tool_context.state["last_question"] = question
    tool_context.state["last_answer"] = answer

    result = {"filtered": filtered_items, "count": len(filtered_items)}
    print(f"--- AI Filter result: {result} ---")
    return result


filter_agent = Agent(
    name="filter_agent",
    model="gemini-2.5-flash",
    description="Filters item descriptions based on user answers to clarifying questions using AI reasoning.",
    instruction="""
    You are an inteligent agent whose sole purpose is to filter a list of item descriptions.
    You will receive a single 'request' parameter which is a string containing all necessary information.

    **Your primary task is to meticulously extract the following pieces of information from the 'request' string:**
    1.  **User's Answer:** Identify the user's 'yes' or 'no' answer to the question. Look for phrases like "The user said yes" or "The user said no".
    2.  **The Question:** Extract the specific question that was asked. It will typically be enclosed in single quotes, e.g., 'Is the bag made of canvas?'.
    3.  **Current Matches (Items):** Parse the list of dictionaries representing the current matches. This will appear after "Current matches:" and will be a string representation of a JSON-like array of objects, e.g., '[{"id": "...", "description": "..."}]'. You must parse this string into an actual Python list of dictionaries.
    
    Based on the question and the user's answer, carefully select only the items from the original list that fit the description.
    For example, if the question was "Is your item red?" and the answer was "yes", you should only return items that are described as red.
    If the answer was "no", you should return items that are NOT described as red.

    Return the filtered item descriptions as a Json list. Do NOT include any other text, explanations, or formatting.
    If no item descriptions match the criteria, return an empty string.

    """,
    #tools=[ai_filter_objects],
)