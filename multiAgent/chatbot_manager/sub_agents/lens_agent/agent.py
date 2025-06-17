# lens_agent/agent.py

import os
import uuid
import datetime as dt
import re
import json
import time
import requests

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools import ToolContext
from google.cloud import aiplatform, firestore
from vertexai.language_models import TextEmbeddingModel
import google.generativeai as genai

# ─── Bootstrap ────────────────────────────────────────────────────
load_dotenv()
PROJECT_ID      = os.getenv("PROJECT_ID")
REGION          = os.getenv("REGION", "us-central1")
INDEX_ID        = os.getenv("INDEX_ID")
GOOGLE_API_KEY  = os.getenv("GOOGLE_API_KEY")
GEOCODING_API_KEY = os.getenv("GEOCODING_API_KEY")

if not all([PROJECT_ID, REGION, INDEX_ID, GOOGLE_API_KEY]):
    raise RuntimeError("PROJECT_ID, REGION, INDEX_ID, and GOOGLE_API_KEY must be set")

aiplatform.init(project=PROJECT_ID, location=REGION)
genai.configure(api_key=GOOGLE_API_KEY)

# Try embedding models in order
_embed = None
for model_name in ("text-embedding-004", "textembedding-gecko@003", "textembedding-gecko@002"):
    try:
        _embed = TextEmbeddingModel.from_pretrained(model_name)
        break
    except Exception:
        continue

_db: firestore.Client | None = None


# ─── Tool: Geocode location with fallbacks ─────────────────────────
def geocode_location(location_text: str, tool_context: ToolContext) -> dict:
    """
    Enhanced geocoding with multiple variations and services.
    """
    if not location_text or not location_text.strip():
        return {"status": "error", "error_message": "Location text cannot be empty"}

    # Generate search variations
    variations = []
    base = location_text.strip()
    variations.append(base)
    # Expand common abbreviations
    for abbr, full in {
        r"\bSt\b":"Street", r"\bAve\b":"Avenue", r"\bRd\b":"Road",
        r"\bNYC\b":"New York City"
    }.items():
        base = re.sub(abbr, full, base, flags=re.IGNORECASE)
    variations.append(base)
    # Try suffixes
    for suf in (", USA", ", United States"):
        if not variations[0].lower().endswith(suf.lower()):
            variations.append(variations[0] + suf)

    # Try each variation with Google Maps
    for term in variations:
        if GEOCODING_API_KEY:
            try:
                resp = requests.get(
                    "https://maps.googleapis.com/maps/api/geocode/json",
                    {"address": term, "key": GEOCODING_API_KEY, "language": "en"},
                    timeout=10
                )
                data = resp.json()
                if data.get("status") == "OK" and data.get("results"):
                    r = data["results"][0]
                    return {
                        "status": "success",
                        "address": r["formatted_address"],
                        "latitude": r["geometry"]["location"]["lat"],
                        "longitude": r["geometry"]["location"]["lng"],
                        "source": "Google Maps",
                        "search_term": term
                    }
            except Exception:
                pass

        # Fallback to Nominatim
        try:
            resp = requests.get(
                "https://nominatim.openstreetmap.org/search",
                {
                    "q": term, "format": "json",
                    "addressdetails": 1, "limit": 1
                },
                headers={"User-Agent":"ItemRadar/1.0"},
                timeout=10
            )
            data = resp.json()
            if data:
                r = data[0]
                return {
                    "status": "success",
                    "address": r["display_name"],
                    "latitude": float(r["lat"]),
                    "longitude": float(r["lon"]),
                    "source": "OpenStreetMap",
                    "search_term": term
                }
        except Exception:
            pass

    # Final fallback: ask Gemini
    try:
        model = genai.GenerativeModel("gemini-pro")
        prompt = f"Extract a clear place name from: \"{location_text}\""
        suggestions = model.generate_content(prompt).text.splitlines()
        for s in suggestions[:3]:
            s = s.strip()
            if not s:
                continue
            # Try Nominatim on suggestion
            try:
                resp = requests.get(
                    "https://nominatim.openstreetmap.org/search",
                    {"q": s, "format": "json", "limit":1},
                    headers={"User-Agent":"ItemRadar/1.0"},
                    timeout=8
                )
                data = resp.json()
                if data:
                    r = data[0]
                    return {
                        "status": "success",
                        "address": r["display_name"],
                        "latitude": float(r["lat"]),
                        "longitude": float(r["lon"]),
                        "source": "Gemini+OSM",
                        "search_term": s
                    }
            except Exception:
                continue
    except Exception:
        pass

    return {
        "status": "error",
        "error_message": f"Could not geocode '{location_text}'",
        "tried_variations": variations
    }


# ─── Tool: Register found item ───────────────────────────────────────
def register_found_item(
    description: str,
    contact_email: str,
    address: str,
    latitude: float,
    longitude: float,
    tool_context: ToolContext
) -> dict:
    """
    Save a found-item record to Firestore and optional Vertex Matching Engine.
    """
    global _db
    try:
        item_id = f"found_{uuid.uuid4().hex[:8]}"
        if _db is None:
            _db = firestore.Client(project=PROJECT_ID)

        doc = {
            "id":          item_id,
            "description": description,
            "email":       contact_email,
            "address":     address,
            "lat":         latitude,
            "lon":         longitude,
            "timestamp":   dt.datetime.utcnow(),
            "status":      "active"
        }
        _db.collection("found_items").document(item_id).set(doc)

        embedding_saved = False
        if _embed is not None:
            try:
                vec = _embed.get_embeddings([description])[0].values
                index = aiplatform.MatchingEngineIndex(INDEX_ID)
                index.upsert_datapoints([{"datapoint_id": item_id, "feature_vector": vec}])
                embedding_saved = True
            except Exception:
                pass

        return {
            "status":          "success",
            "item_id":         item_id,
            "firestore_saved": True,
            "embedding_saved": embedding_saved
        }

    except Exception as e:
        return {"status":"error", "error_message": str(e)}


# ─── Lens Agent Definition ───────────────────────────────────────────
lens_agent = Agent(
    name="lens_agent",
    model="gemini-2.0-flash",
    description=(
        "Analyzes found-item images, geocodes locations with fallbacks, "
        "and registers found items in Firestore/Vertex AI."
    ),
    instruction=(
        "When you receive an image, describe the item and ask for contact email "
        "and location. Then:\n"
        "1. Call geocode_location(location_text).\n"
        "2. If success, call register_found_item(description, email, address, latitude, longitude).\n"
        "3. Respond 'SUCCESS: Found item registered successfully'.\n\n"
        "Also support a batch registration command:\n"
        "'REGISTER_FOUND_ITEM: Description:..., Email:..., Location:...'\n"
        "You must parse it, geocode, register, and respond with SUCCESS or error."
    ),
    tools=[geocode_location, register_found_item],
)
