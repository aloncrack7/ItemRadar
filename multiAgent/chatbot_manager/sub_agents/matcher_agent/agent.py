from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from google.generativeai import GenerativeModel
from google.cloud import firestore
import os
import json
import logging

# Load environment variables
PROJECT_ID = os.getenv("PROJECT_ID")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not PROJECT_ID or not GOOGLE_API_KEY:
    raise RuntimeError("PROJECT_ID and GOOGLE_API_KEY must be set")

# Initialize Firestore client
db = firestore.Client(project=PROJECT_ID)


def fetch_items_from_firestore() -> list[dict]:
    """Fetch all items from Firestore with complete details"""
    items_ref = db.collection("found_items")
    docs = items_ref.stream()

    items = []
    for doc in docs:
        item = doc.to_dict()
        # More flexible field checking - only require id and description
        if "id" in item and "description" in item:
            items.append({
                "id": item["id"],
                "description": item["description"],
                "location": item.get("location", ""),  # Optional field
                "contact": item.get("contact", ""),
                "date_found": item.get("date_found", ""),
                "additional_details": item.get("additional_details", "")
            })
    return items


def get_items(query: str) -> str:  # Changed function name to match FILE1
    """
    Use the LLM to select the similar items from Firestore based on the user query.
    This function mirrors the working FILE1 implementation.
    """
    try:
        model = GenerativeModel("gemini-2.0-flash")
        items = fetch_items_from_firestore()

        if not items:
            return json.dumps({"matches": [], "error": "No items found in Firestore."})

        # Use the exact same prompt structure as FILE1
        prompt = f"""
You are an expert at matching item descriptions.

Here is a user's query for a lost item:
"{query}"

Below is a list of items that people have found:
{chr(10).join([f"{item['id']}: {item['description']}" for item in items])}

Your task is to return **only the items from the list** that are semantically similar to the user's query.
The descriptions do not need to match exactly — even partial or vague similarities are acceptable.
Do not generate new items. Do not explain. Do not say anything outside the response format.

Respond strictly in this exact JSON format:
{{
  "matches": [
    {{"id": "item_id", "description": "item description"}},
    ...
  ]
}}

If nothing matches, return:
{{
  "matches": []
}}
"""

        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        logging.error(f"Error in get_items: {str(e)}")
        return json.dumps({
            "matches": [],
            "error": str(e)
        })


# Create the tool with the same function name as FILE1
tool = FunctionTool(get_items)

# Define the matcher agent exactly like FILE1
root_agent = LlmAgent(  # Changed back to root_agent to match FILE1
    name="matcher_agent",
    model="gemini-2.0-flash",
    tools=[tool],
    instruction=(
        "When the user gives a query, call once the tool `get_items` with the query. "
        "Return the function output directly, do not add explanation"
    ),
)

# Alternative agent name for compatibility
matcher_agent = root_agent

if __name__ == "__main__":
    # Test both direct function call and agent
    query = "green helmet madrid"
    print(f"Testing with query: {query}")

    # Direct function test
    result = get_items(query)
    print(f"Direct function result: {result}")

    # Test data fetch
    items = fetch_items_from_firestore()
    print(f"Found {len(items)} items in Firestore")
    if items:
        print("Sample items:")
        for item in items[:3]:  # Show first 3 items
            print(f"  {item['id']}: {item['description']}")