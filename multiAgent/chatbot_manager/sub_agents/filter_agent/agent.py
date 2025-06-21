# Fixed filter_agent/agent.py
import os
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext

load_dotenv()


def filter_objects(texts: list[str], question: str, answer: str, tool_context: ToolContext) -> dict:
    """
    Filters the list of item descriptions based on the user's answer to a specific question.
    """
    print(f"--- Tool: filter_objects called with question='{question}', answer='{answer}', texts={texts} ---")

    if not texts:
        return {"filtered": [], "count": 0, "message": "No items to filter"}

    normalized_answer = answer.strip().lower()
    question_lower = question.lower()

    filtered = []

    # Normalize yes/no answers
    is_yes = normalized_answer in ["yes", "y", "true", "1"]
    is_no = normalized_answer in ["no", "n", "false", "0"]

    # Context-aware filtering based on question type and answer
    if "stickers" in question_lower or "decals" in question_lower:
        if is_yes:
            # User has stickers/decals - look for items that mention logos, stickers, or markings
            for item in texts:
                item_lower = item.lower()
                if any(word in item_lower for word in ["logo", "sticker", "decal", "marking", "brand", "company"]):
                    filtered.append(item)
        else:
            # User doesn't have stickers/decals - exclude items with logos, stickers, etc.
            for item in texts:
                item_lower = item.lower()
                if not any(word in item_lower for word in ["logo", "sticker", "decal", "marking", "brand", "company"]):
                    filtered.append(item)

    elif "bicycle helmet" in question_lower and "motorcycle" in question_lower:
        if is_yes:
            # User confirms bicycle helmet - keep only bicycle helmets
            for item in texts:
                item_lower = item.lower()
                if "bicycle" in item_lower and "motorcycle" not in item_lower and "construction" not in item_lower:
                    filtered.append(item)
        else:
            # User says no to bicycle helmet - exclude bicycle helmets
            for item in texts:
                item_lower = item.lower()
                if "bicycle" not in item_lower:
                    filtered.append(item)

    elif "ventilation holes" in question_lower or "vents" in question_lower:
        if is_yes:
            # User has ventilation holes - typically bicycle helmets have these
            for item in texts:
                item_lower = item.lower()
                if "bicycle" in item_lower or "bike" in item_lower:
                    filtered.append(item)
        else:
            # User doesn't have ventilation holes - typically construction or motorcycle helmets
            for item in texts:
                item_lower = item.lower()
                if "construction" in item_lower or "motorcycle" in item_lower:
                    filtered.append(item)

    elif "scratch" in question_lower or "damaged" in question_lower:
        if is_yes:
            # User has scratches/damage
            for item in texts:
                item_lower = item.lower()
                if any(word in item_lower for word in ["scratch", "damage", "dent", "crack", "worn"]):
                    filtered.append(item)
        else:
            # User doesn't have scratches/damage
            for item in texts:
                item_lower = item.lower()
                if not any(word in item_lower for word in ["scratch", "damage", "dent", "crack", "worn"]):
                    filtered.append(item)

    elif "size" in question_lower:
        # Size-related questions
        if "small" in question_lower or "medium" in question_lower or "large" in question_lower:
            size_mentioned = None
            if "small" in question_lower:
                size_mentioned = "small"
            elif "medium" in question_lower:
                size_mentioned = "medium"
            elif "large" in question_lower:
                size_mentioned = "large"

            if is_yes:
                # User confirms the size
                for item in texts:
                    item_lower = item.lower()
                    if size_mentioned in item_lower:
                        filtered.append(item)
            else:
                # User denies the size
                for item in texts:
                    item_lower = item.lower()
                    if size_mentioned not in item_lower:
                        filtered.append(item)

    elif "color" in question_lower:
        # Color-related questions - extract the color from the question
        colors = ["green", "red", "blue", "yellow", "black", "white", "orange", "purple", "pink"]
        question_color = None
        for color in colors:
            if color in question_lower:
                question_color = color
                break

        if question_color:
            if is_yes:
                # User confirms the color
                for item in texts:
                    if question_color in item.lower():
                        filtered.append(item)
            else:
                # User denies the color
                for item in texts:
                    if question_color not in item.lower():
                        filtered.append(item)

    else:
        # Fallback: keyword-based filtering
        # Extract meaningful keywords from question (excluding common words)
        common_words = {"is", "your", "a", "an", "the", "does", "have", "has", "are", "it", "this", "that", "with",
                        "or", "and"}
        question_words = [word for word in question_lower.split() if len(word) > 2 and word not in common_words]

        if is_yes:
            # Look for items that match question keywords
            for item in texts:
                item_lower = item.lower()
                if any(word in item_lower for word in question_words):
                    filtered.append(item)
        elif is_no:
            # Look for items that don't match question keywords
            for item in texts:
                item_lower = item.lower()
                if not any(word in item_lower for word in question_words):
                    filtered.append(item)
        else:
            # If answer is unclear, return original list
            filtered = texts.copy()

    # If filtering resulted in no items and we had a clear yes/no answer,
    # something might be wrong - return original list to avoid losing all items
    if not filtered and (is_yes or is_no) and texts:
        print(f"--- Warning: Filtering removed all items, returning original list ---")
        filtered = texts.copy()

    # Store results in tool context state
    tool_context.state["filtered_results"] = filtered
    tool_context.state["last_filter_count"] = len(filtered)
    tool_context.state["last_question"] = question
    tool_context.state["last_answer"] = answer

    result = {"filtered": filtered, "count": len(filtered)}
    print(f"--- Filter result: {result} ---")
    return result


filter_agent = Agent(
    name="filter_agent",
    model="gemini-2.5-flash",
    description="Filters item descriptions based on user answers to clarifying questions.",
    instruction="""
    You filter a list of item descriptions based on the user's answer to a specific question.

    When given:
    - texts: list of item descriptions 
    - question: the clarifying question that was asked
    - answer: user's response to the question

    Call filter_objects with all three parameters to intelligently narrow down the list.

    The filtering should be context-aware and logical:
    - For helmet type questions: distinguish between bicycle, motorcycle, and construction helmets
    - For feature questions (ventilation, stickers, etc.): match based on presence/absence of features
    - For physical attribute questions: match based on size, color, condition, etc.

    Always return the filtered results showing how many items remain after filtering.
    If filtering removes all items unexpectedly, the function will return the original list as a safety measure.
    """,
    tools=[filter_objects],
)