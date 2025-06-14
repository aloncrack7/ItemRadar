"""
ItemRadar — LensAgent (Fixed Geocoding)
──────────────────────────────────────────────────
SOLUTION: Replace unreliable Gemini geocoding with proper geocoding service
"""

from __future__ import annotations

import datetime as dt
import os
import uuid
import re
import json
import requests
from typing import Dict

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.cloud import aiplatform, firestore
from vertexai.language_models import TextEmbeddingModel

import google.generativeai as genai

# ─── bootstrap ──────────────────────────────────────────────────
load_dotenv()

PROJECT_ID = os.getenv("PROJECT_ID")
REGION = os.getenv("REGION", "us-central1")
INDEX_ID = os.getenv("INDEX_ID")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEOCODING_API_KEY = os.getenv("GEOCODING_API_KEY")  # Google Maps API key (optional)

if not all([PROJECT_ID, REGION, INDEX_ID, GOOGLE_API_KEY]):
    raise RuntimeError("PROJECT_ID, REGION, INDEX_ID, and GOOGLE_API_KEY must be set")

aiplatform.init(project=PROJECT_ID, location=REGION)
genai.configure(api_key=GOOGLE_API_KEY)

_embed = TextEmbeddingModel.from_pretrained("textembedding-gecko@002")
_db: firestore.Client | None = None  # lazy client


# ─── TOOL: 1) geocode with proper geocoding service ────────────────────────────

def geocode_location(location_text: str) -> Dict:
    """
    Geocodes a location using a proper geocoding service.
    Falls back to multiple services for better reliability.
    """
    # Option 1: Google Maps Geocoding API (most accurate, requires API key)
    if GEOCODING_API_KEY:
        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                "address": location_text,
                "key": GEOCODING_API_KEY
            }
            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            if data["status"] == "OK" and data["results"]:
                result = data["results"][0]
                return {
                    "status": "success",
                    "address": result["formatted_address"],
                    "latitude": result["geometry"]["location"]["lat"],
                    "longitude": result["geometry"]["location"]["lng"],
                }
        except Exception as e:
            print(f"Google Maps API failed: {e}")

    # Option 2: Nominatim (OpenStreetMap) - Free, no API key required
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": location_text,
            "format": "json",
            "addressdetails": 1,
            "limit": 1
        }
        headers = {
            "User-Agent": "ItemRadar-LostFound/1.0"  # Required by Nominatim
        }

        response = requests.get(url, params=params, headers=headers, timeout=10)
        data = response.json()

        if data:
            result = data[0]
            return {
                "status": "success",
                "address": result["display_name"],
                "latitude": float(result["lat"]),
                "longitude": float(result["lon"]),
            }
    except Exception as e:
        print(f"Nominatim failed: {e}")

    # Option 3: Fallback to approximate location parsing with Gemini
    try:
        model = genai.GenerativeModel("gemini-pro")
        prompt = (
            "Extract the city and country from this location text. "
            "Return ONLY in this exact format: 'City, Country' (nothing else).\n\n"
            f"Location: {location_text}"
        )
        response = model.generate_content(prompt).text.strip()

        # Try geocoding the simplified location
        try:
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                "q": response,
                "format": "json",
                "addressdetails": 1,
                "limit": 1
            }
            headers = {"User-Agent": "ItemRadar-LostFound/1.0"}

            geo_response = requests.get(url, params=params, headers=headers, timeout=10)
            geo_data = geo_response.json()

            if geo_data:
                result = geo_data[0]
                return {
                    "status": "success",
                    "address": f"Approximate location: {result['display_name']}",
                    "latitude": float(result["lat"]),
                    "longitude": float(result["lon"]),
                }
        except:
            pass

    except Exception as e:
        print(f"Gemini fallback failed: {e}")

    return {
        "status": "error",
        "error_message": "Could not geocode location. Please try a more specific address or well-known landmark."
    }


# ─── TOOL: 2) persist result ────────────────────────────────────────────

def register_found_item(
        description: str,
        contact_email: str,
        address: str,
        latitude: float,
        longitude: float,
) -> Dict:
    """
    Embeds the description and saves the found item to Vertex AI + Firestore.
    """
    global _db
    try:
        # Create embedding
        vec = _embed.get_embeddings([description])[0].values

        # Save to Vertex AI Matching Engine
        index = aiplatform.MatchingEngineIndex(INDEX_ID)
        item_id = f"found_{uuid.uuid4().hex[:8]}"
        index.upsert_datapoints([{"datapoint_id": item_id, "feature_vector": vec}])

        # Save metadata to Firestore
        if _db is None:
            _db = firestore.Client(project=PROJECT_ID)

        _db.collection("found_items").document(item_id).set({
            "id": item_id,
            "description": description,
            "email": contact_email,
            "address": address,
            "lat": latitude,
            "lon": longitude,
            "timestamp": dt.datetime.utcnow(),
        })

        return {"status": "success", "item_id": item_id}
    except Exception as exc:
        return {"status": "error", "error_message": str(exc)}


# ─── Updated Agent definition ────────────────────────────────────────────

root_agent = Agent(
    name="lens_agent",
    model="gemini-2.0-flash",
    description=(
        "Processes found item images directly using multimodal capabilities, "
        "geocodes locations using reliable geocoding services, and saves items to "
        "Vertex AI Matching Engine and Firestore."
    ),
    instruction=(
        "You are an AI assistant that helps users register found items for a lost-and-found system.\n\n"

        "WORKFLOW:\n"
        "1. When a user sends an **image** (inline or URL), YOU MUST analyze it directly and create a "
        "description of the main object in 25-40 words. Mention visible brand, color, and material.\n\n"

        "2. After analyzing the image, respond with:\n"
        "   - 'I can see [your description of the item]'\n"
        "   - Ask for their **contact email** (required)\n"
        "   - Ask for the **location** where they found it. Tell them: 'Please provide the location "
        "     where you found this item (e.g., Central Park NYC, or Retiro Park Madrid, or even just "
        "     the city name - approximate location is fine)'\n\n"

        "3. When they provide the location, call `geocode_location` with their location text.\n\n"

        "4. If geocoding succeeds, show the result and ask: 'I found this location: **[address]**. "
        "   Is this correct or close enough? (yes/no)'\n\n"

        "5. If they say **yes**, call `register_found_item` with all the details.\n\n"

        "6. If they say **no** or geocoding fails, ask them to try:\n"
        "   - A nearby landmark or famous place\n"
        "   - Just the city and country\n"
        "   - A more specific address\n"
        "   Then repeat step 3.\n\n"

        "7. Be helpful and encouraging. Since approximate location within 1km is fine, "
        "   accept locations that are 'close enough' rather than being too picky.\n\n"

        "IMPORTANT: Do NOT use any extract_description function. You have multimodal capabilities - "
        "analyze images directly and create descriptions yourself."
    ),
    tools=[geocode_location, register_found_item],
)