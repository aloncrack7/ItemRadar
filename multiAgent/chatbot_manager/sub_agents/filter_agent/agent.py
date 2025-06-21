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
    
)