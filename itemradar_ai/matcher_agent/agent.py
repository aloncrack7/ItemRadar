from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from google.generativeai import GenerativeModel
import os
from dotenv import load_dotenv
from google.cloud import aiplatform, firestore

# ─── bootstrap ──────────────────────────────────────────────────
load_dotenv()

PROJECT_ID = os.getenv("PROJECT_ID")
REGION = os.getenv("REGION", "us-central1")
INDEX_ID = os.getenv("INDEX_ID")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not all([PROJECT_ID, REGION, INDEX_ID, GOOGLE_API_KEY]):
    raise RuntimeError("PROJECT_ID, REGION, INDEX_ID, and GOOGLE_API_KEY must be set")

aiplatform.init(project=PROJECT_ID, location=REGION)

def fetch_items_from_firestore() -> list[dict]:
    db = firestore.Client(project=PROJECT_ID)
    items_ref = db.collection("found_items")  
    docs = items_ref.stream()

    items = []
    for doc in docs:
        data = doc.to_dict()
        if "id" in data and "description" in data:
            items.append({"id": data["id"], "description": data["description"]})
    return items

def get_items(query: str) -> dict:
    """
    Use the LLM to select the similar items from Firestore based on the user query.
    """
    model = GenerativeModel("gemini-2.0-flash")
    items = fetch_items_from_firestore()

    if not items:
        return {"matches": [], "error": "No items found in Firestore."}

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

    import json
    
    response = model.generate_content(prompt)   
    return response.text


tool = FunctionTool(get_items)

# Must be called root_agent
root_agent = LlmAgent(
    name="matcher_agent",
    model="gemini-2.0-flash",
    tools=[tool],
    instruction=(
        "When the user gives a query, call once the tool `get_items` with the query. "
        "Return the function output directly, do not add explanation"
    ),
)

