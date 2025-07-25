import os
import re
from collections import Counter
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext
from google.generativeai import GenerativeModel, configure as configure_gemini

load_dotenv()

# Configure Gemini API
configure_gemini(api_key=os.getenv("GEMINI_API_KEY"))


def analyze_items_and_generate_question(texts: list[str], tool_context: ToolContext) -> dict:
    """
    Enhanced universal analyzer that uses LLM reasoning to understand items
    and generate truly personalized discriminating questions.
    """
    print(f"--- Analyzing {len(texts)} items with enhanced AI reasoning ---")

    if not texts or len(texts) <= 1:
        return {"question": None, "reason": "Not enough items to discriminate"}

    # Get previous questions to avoid repetition
    previous_questions = tool_context.state.get("asked_questions", [])

    # Get conversation context for better understanding
    conversation_context = tool_context.state.get("conversation_context", "")

    # Prepare the prompt for the Gemini model
    prompt = f"""
    You are an enhanced universal item discriminator. Your goal is to help narrow down a list of potential lost items by asking a single, optimal yes/no question.

    Here is the list of items to discriminate:
    {', '.join(texts)}

    Previous questions asked in this conversation (avoid repeating these):
    {', '.join(previous_questions) if previous_questions else 'None'}

    Conversation context so far:
    {conversation_context if conversation_context else 'None'}

    Based on the items provided, their characteristics, and the previous conversation, generate ONE clear, concise yes/no question that will best divide this list of items. Focus on distinguishing features, common attributes, or semantic differences.

    Respond ONLY with the question text. Do not include any explanations, reasoning, or additional text.
    """

    try:
        model = GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        question = response.text.strip()

        if not question.endswith('?'):
            question += '?' # Ensure it's a question

        # Check if the generated question is too generic or a repetition
        if any(pq.lower() == question.lower() for pq in previous_questions) or \
           len(question.split()) < 3: # Simple check for very short/generic questions
            print("--- Generated question is a repetition or too generic, attempting a different approach. ---")
            # Fallback if the initial AI generated question is not ideal
            fallback_prompt = f"""
            You are an enhanced universal item discriminator. Your goal is to help narrow down a list of potential lost items by asking a single, optimal yes/no question.

            Here is the list of items to discriminate:
            {', '.join(texts)}

            Previous questions asked in this conversation (absolutely avoid repeating these):
            {', '.join(previous_questions + [question]) if previous_questions else 'None'}

            Conversation context so far:
            {conversation_context if conversation_context else 'None'}

            The previous attempt at generating a question was '{question}'. Please generate a DIFFERENT, clear, concise yes/no question that will best divide this list of items. Focus on unique distinguishing features or less obvious differences.

            Respond ONLY with the question text. Do not include any explanations, reasoning, or additional text.
            """
            response = model.generate_content(fallback_prompt)
            question = response.text.strip()
            if not question.endswith('?'):
                question += '?'

    except Exception as e:
        print(f"Error calling Gemini model: {e}")
        # Intelligent fallback to a generic question if AI call fails
        question = "Can you describe a unique feature of your item?"
        print(f"--- Falling back to generic question: {question} ---")

    # Store the question to avoid repetition
    previous_questions.append(question)
    tool_context.state["asked_questions"] = previous_questions

    # Store context for future questions (initialize if doesn't exist)
    if "conversation_context" not in tool_context.state:
        tool_context.state["conversation_context"] = ""
    tool_context.state["conversation_context"] += f"\nAsked: {question}"

    result = {
        "question": question,
        "reasoning": "Generated by Gemini AI model based on item analysis.",
        "confidence": 0.9 # High confidence as it's AI-generated
    }

    print(f"--- Generated question: {question} ---")
    print(f"--- Reasoning: {result.get('reasoning', 'N/A')} ---")

    return result


# Create the enhanced agent
reducer_agent = Agent(
    name="enhanced_reducer_agent",
    model="gemini-2.5-flash",
    description="Enhanced universal item discriminator that uses AI reasoning to generate personalized clarifying questions for any type of lost item by intelligently analyzing patterns, characteristics, and differences.",
    instruction="""
    You are an enhanced universal item discriminator that helps narrow down lists of potential lost items using intelligent analysis.

    Your enhanced process:
    1. Receive a list of item descriptions of ANY type (bags, electronics, clothing, tools, etc.)
    2. Directly use the Gemini AI model to:
        - Intelligently understand the nature and characteristics of each item.
        - Identify meaningful patterns and differences using semantic analysis.
        - Generate personalized questions based on actual item characteristics.
        - Avoid repeating questions you've already asked.
        - Leverage conversation context for better understanding.
    3. Generate ONE clear yes/no question that will optimally divide the item list.
    4. Return ONLY the question text in a conversational format.

    Key principles:
    - Work with ANY type of item - be completely universal.
    - Choose questions that create the best binary split of the item list.
    - Use clear, simple language that anyone can understand.
    - The question should be directly usable as a yes/no prompt to the user.

    Always return just the question text - no explanations or analysis.
    Let your intelligence shine through better, more targeted questions.
    """,
    tools=[analyze_items_and_generate_question],
)