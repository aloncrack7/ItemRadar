"""
ItemRadar — LensAgent (Enhanced Geocoding + Updated Embedding Model)
──────────────────────────────────────────────────────────────────
SOLUTION: Enhanced geocoding with better fallbacks and location processing
"""

from __future__ import annotations

import datetime as dt
import os
import uuid
import re
import json
import requests
import time
from typing import Dict, List, Optional

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

# Updated embedding model - using the latest stable version
try:
    # Try the latest text embedding model first
    _embed = TextEmbeddingModel.from_pretrained("text-embedding-004")
except Exception:
    try:
        # Fallback to gecko-003 if 004 is not available
        _embed = TextEmbeddingModel.from_pretrained("textembedding-gecko@003")
    except Exception:
        try:
            # Final fallback to gecko-002
            _embed = TextEmbeddingModel.from_pretrained("textembedding-gecko@002")
        except Exception as e:
            print(f"Warning: Could not load any embedding model: {e}")
            _embed = None

_db: firestore.Client | None = None  # lazy client


# ─── Enhanced location preprocessing ────────────────────────────────────

def preprocess_location(location_text: str) -> List[str]:
    """
    Preprocesses location text and generates multiple search variations.
    Returns a list of location strings to try in order of specificity.
    """
    if not location_text or not location_text.strip():
        return []

    location = location_text.strip()
    search_variations = []

    # Original location (always try first)
    search_variations.append(location)

    # Common abbreviations and expansions
    abbreviations = {
        r'\bSt\b': 'Street',
        r'\bAve\b': 'Avenue',
        r'\bBlvd\b': 'Boulevard',
        r'\bRd\b': 'Road',
        r'\bDr\b': 'Drive',
        r'\bPl\b': 'Place',
        r'\bPk\b': 'Park',
        r'\bNY\b': 'New York',
        r'\bLA\b': 'Los Angeles',
        r'\bSF\b': 'San Francisco',
        r'\bNYC\b': 'New York City',
        r'\bUS\b': 'United States',
        r'\bUSA\b': 'United States',
        r'\bUK\b': 'United Kingdom',
    }

    # Try expanded abbreviations
    expanded = location
    for abbr, full in abbreviations.items():
        expanded = re.sub(abbr, full, expanded, flags=re.IGNORECASE)

    if expanded != location:
        search_variations.append(expanded)

    # Try with common location suffixes
    common_suffixes = [', USA', ', United States', ', US']
    for suffix in common_suffixes:
        if not location.lower().endswith(suffix.lower()):
            search_variations.append(location + suffix)

    # Extract and try just the main location parts
    # Remove common prefixes
    clean_location = re.sub(r'^(near|at|in|on|by)\s+', '', location, flags=re.IGNORECASE)
    if clean_location != location:
        search_variations.append(clean_location)

    # Try extracting potential city/landmark names
    # Look for patterns like "Central Park, NYC" or "Times Square New York"
    if ',' in location:
        parts = [part.strip() for part in location.split(',')]
        # Try each part individually (useful for "Building Name, City" format)
        for part in parts:
            if len(part) > 2:  # Avoid single letters
                search_variations.append(part)

    # Remove duplicates while preserving order
    unique_variations = []
    seen = set()
    for variation in search_variations:
        if variation.lower() not in seen:
            unique_variations.append(variation)
            seen.add(variation.lower())

    return unique_variations


# ─── Enhanced geocoding with better error handling ────────────────────────

def geocode_location(location_text: str) -> Dict:
    """
    Enhanced geocoding with multiple services and better preprocessing.
    """
    if not location_text or not location_text.strip():
        return {
            "status": "error",
            "error_message": "Location text cannot be empty"
        }

    # Get multiple search variations
    search_variations = preprocess_location(location_text)
    print(f"Trying geocoding variations: {search_variations}")

    # Try each variation with each service
    for variation in search_variations:
        print(f"Trying variation: '{variation}'")

        # Option 1: Google Maps Geocoding API (most accurate)
        if GEOCODING_API_KEY:
            try:
                url = "https://maps.googleapis.com/maps/api/geocode/json"
                params = {
                    "address": variation,
                    "key": GEOCODING_API_KEY,
                    "language": "en"  # Force English results for consistency
                }
                response = requests.get(url, params=params, timeout=15)
                response.raise_for_status()
                data = response.json()

                if data["status"] == "OK" and data["results"]:
                    result = data["results"][0]
                    return {
                        "status": "success",
                        "address": result["formatted_address"],
                        "latitude": result["geometry"]["location"]["lat"],
                        "longitude": result["geometry"]["location"]["lng"],
                        "source": "Google Maps",
                        "search_term": variation
                    }
                elif data["status"] == "ZERO_RESULTS":
                    print(f"Google Maps: No results for '{variation}'")
                    continue
                else:
                    print(f"Google Maps error: {data.get('status')} - {data.get('error_message', 'Unknown error')}")

            except requests.exceptions.RequestException as e:
                print(f"Google Maps API request failed for '{variation}': {e}")
            except Exception as e:
                print(f"Google Maps API failed for '{variation}': {e}")

        # Option 2: Nominatim (OpenStreetMap) - More detailed search
        try:
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                "q": variation,
                "format": "json",
                "addressdetails": 1,
                "limit": 3,  # Get multiple results to pick the best one
                "dedupe": 1,
                "accept-language": "en"
            }
            headers = {
                "User-Agent": "ItemRadar-LostFound/1.0 (contact@itemradar.com)"
            }

            response = requests.get(url, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()

            if data:
                # Pick the result with highest importance score
                best_result = max(data, key=lambda x: float(x.get('importance', 0)))

                return {
                    "status": "success",
                    "address": best_result["display_name"],
                    "latitude": float(best_result["lat"]),
                    "longitude": float(best_result["lon"]),
                    "source": "OpenStreetMap",
                    "search_term": variation
                }
            else:
                print(f"Nominatim: No results for '{variation}'")

        except requests.exceptions.RequestException as e:
            print(f"Nominatim request failed for '{variation}': {e}")
        except Exception as e:
            print(f"Nominatim failed for '{variation}': {e}")

        # Small delay between attempts to be respectful to free services
        time.sleep(0.5)

    # Final fallback: Use Gemini to extract and simplify location
    try:
        print("Trying Gemini-assisted geocoding...")
        model = genai.GenerativeModel("gemini-pro")
        prompt = f"""
        Analyze this location text and extract the most important geographic information.
        Return up to 3 possible interpretations, each on a new line, in order of likelihood.
        Focus on well-known places, landmarks, cities, or addresses.

        Location text: "{location_text}"

        Format each line as: City, State/Province, Country (if applicable)
        Or: Landmark/Place Name, City, Country

        Examples:
        - "Central Park NYC" → "Central Park, New York City, New York, United States"
        - "near times square" → "Times Square, New York City, New York, United States"
        - "downtown chicago" → "Downtown Chicago, Illinois, United States"
        """

        response = model.generate_content(prompt)
        suggestions = response.text.strip().split('\n')

        # Try geocoding each suggestion
        for suggestion in suggestions[:3]:  # Only try top 3
            suggestion = suggestion.strip()
            if not suggestion:
                continue

            print(f"Trying Gemini suggestion: '{suggestion}'")

            # Try Nominatim with the cleaned suggestion
            try:
                url = "https://nominatim.openstreetmap.org/search"
                params = {
                    "q": suggestion,
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
                        "address": f"Approximate: {result['display_name']}",
                        "latitude": float(result["lat"]),
                        "longitude": float(result["lon"]),
                        "source": "Gemini + OpenStreetMap",
                        "search_term": suggestion
                    }
            except Exception as e:
                print(f"Gemini suggestion geocoding failed: {e}")
                continue

            time.sleep(0.5)

    except Exception as e:
        print(f"Gemini fallback failed: {e}")

    # If all else fails, provide helpful error message
    return {
        "status": "error",
        "error_message": (
            f"Could not find location: '{location_text}'. "
            "Please try:\n"
            "• A specific address (e.g., '123 Main St, New York, NY')\n"
            "• A famous landmark (e.g., 'Eiffel Tower' or 'Central Park NYC')\n"
            "• A city and country (e.g., 'Paris, France' or 'New York, USA')\n"
            "• A neighborhood or district (e.g., 'Manhattan, NYC' or 'Downtown Chicago')"
        ),
        "tried_variations": search_variations
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
        # Generate a unique item ID first (before any operations)
        item_id = f"found_{uuid.uuid4().hex[:8]}"

        # Initialize Firestore client if needed
        if _db is None:
            _db = firestore.Client(project=PROJECT_ID)

        # Save metadata to Firestore FIRST (most important step)
        doc_data = {
            "id": item_id,
            "description": description,
            "email": contact_email,
            "address": address,
            "lat": latitude,
            "lon": longitude,
            "timestamp": dt.datetime.utcnow(),
            "status": "active"
        }

        print(f"Attempting to save to Firestore: {item_id}")
        _db.collection("found_items").document(item_id).set(doc_data)
        print(f"Successfully saved to Firestore: {item_id}")

        # Try to create embedding and save to Vertex AI (secondary step)
        embedding_success = False
        if _embed is not None:
            try:
                embedding_result = _embed.get_embeddings([description])
                if embedding_result and hasattr(embedding_result[0], 'values'):
                    vec = embedding_result[0].values

                    # Save to Vertex AI Matching Engine
                    index = aiplatform.MatchingEngineIndex(INDEX_ID)
                    index.upsert_datapoints([{"datapoint_id": item_id, "feature_vector": vec}])
                    embedding_success = True
                    print(f"Successfully saved embedding to Vertex AI: {item_id}")
            except Exception as e:
                print(f"Warning: Failed to save to Matching Engine: {e}")
                # Don't fail the entire operation if embedding fails

        return {
            "status": "success",
            "item_id": item_id,
            "firestore_saved": True,
            "embedding_saved": embedding_success,
            "message": f"Found item registered successfully with ID: {item_id}"
        }

    except Exception as exc:
        print(f"Error in register_found_item: {exc}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "error_message": f"Failed to register found item: {str(exc)}"
        }


# ─── Helper function to check available models ─────────────────────────────

def check_available_models():
    """
    Debug function to check which embedding models are available.
    """
    models_to_try = [
        "text-embedding-004",
        "text-embedding-preview-0409",
        "textembedding-gecko@003",
        "textembedding-gecko@002",
        "textembedding-gecko@001"
    ]

    available_models = []
    for model_name in models_to_try:
        try:
            test_model = TextEmbeddingModel.from_pretrained(model_name)
            available_models.append(model_name)
            print(f"✓ {model_name} - Available")
        except Exception as e:
            print(f"✗ {model_name} - Not available: {str(e)[:100]}...")

    return available_models


# ─── Updated Agent definition ────────────────────────────────────────────

root_agent = Agent(
    name="lens_agent",
    model="gemini-2.0-flash",
    description=(
        "Processes found item images directly using multimodal capabilities, "
        "geocodes locations using enhanced geocoding with multiple fallbacks, and saves items to "
        "Vertex AI Matching Engine and Firestore."
    ),
    instruction=(
        "You are an AI assistant that helps users register found items for a lost-and-found system.\n\n"

        "IMPORTANT: When you receive a message that starts with 'REGISTER_FOUND_ITEM:', you MUST immediately:\n"
        "1. Extract the Description, Email, and Location from the message\n"
        "2. Call geocode_location with the Location text\n"
        "3. If geocoding succeeds, immediately call register_found_item with all the details\n"
        "4. Respond with 'SUCCESS: Found item registered successfully' if registration works\n\n"

        "NORMAL WORKFLOW (for interactive users):\n"
        "1. When a user sends an **image** (inline or URL), YOU MUST analyze it directly and create a "
        "description of the main object in 25-40 words. Mention visible brand, color, and material.\n\n"

        "2. After analyzing the image, respond with:\n"
        "   - 'I can see [your description of the item]'\n"
        "   - Ask for their **contact email** (required)\n"
        "   - Ask for the **location** where they found it. Tell them: 'Please provide the location "
        "     where you found this item. You can use:\n"
        "     • A specific address (e.g., 123 Main St, New York, NY)\n"
        "     • A landmark or place name (e.g., Central Park, Times Square)\n"
        "     • A business or building name (e.g., Starbucks on 5th Avenue)\n"
        "     • Just a neighborhood or city (e.g., Downtown Chicago, Manhattan)\n"
        "     Even approximate locations work fine!'\n\n"

        "3. When they provide the location, call `geocode_location` with their location text.\n\n"

        "4. If geocoding succeeds, show the result and ask: 'I found this location: **[address]**. "
        "   Is this correct or close enough? The system works well with approximate locations. (yes/no)'\n\n"

        "5. If they say **yes**, call `register_found_item` with all the details.\n\n"

        "6. If they say **no** or geocoding fails, the error message will include helpful suggestions. "
        "   Share these suggestions with the user and ask them to try again with a different format.\n\n"

        "7. Be encouraging about location accuracy - explain that the system is designed to work with "
        "   approximate locations and doesn't need to be perfect. Even 'nearby' or 'close enough' is fine.\n\n"

        "EXAMPLE REGISTRATION MESSAGE:\n"
        "If you receive: 'REGISTER_FOUND_ITEM: Description: Blue iPhone case, Email: john@email.com, Location: Central Park NYC'\n"
        "You should: 1) Call geocode_location('Central Park NYC'), 2) Call register_found_item with all details, 3) Respond 'SUCCESS: Found item registered successfully'\n\n"

        "IMPORTANT: Do NOT use any extract_description function. You have multimodal capabilities - "
        "analyze images directly and create descriptions yourself."
    ),
    tools=[geocode_location, register_found_item],
)

# Export for API usage
lens_agent = root_agent

# ─── Debug/Setup function ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=== ItemRadar Enhanced Model Check ===")
    available = check_available_models()
    if available:
        print(f"\nRecommended model to use: {available[0]}")
    else:
        print("\nNo embedding models available. Check your project permissions.")

    # Test geocoding with some example locations
    print("\n=== Testing Enhanced Geocoding ===")
    test_locations = [
        "Central Park NYC",
        "near times square",
        "downtown LA",
        "St. Paul's Cathedral London",
        "123 Main St"
    ]

    for location in test_locations:
        print(f"\nTesting: '{location}'")
        result = geocode_location(location)
        if result["status"] == "success":
            print(f"✓ Found: {result['address']}")
        else:
            print(f"✗ Failed: {result['error_message']}")