"""
Lost & Found Database Models and Utilities
------------------------------------------
Data models, enums, and AI processing utilities for semantic matching
"""

from __future__ import annotations

import json
import re
import datetime as dt
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
from math import radians, cos, sin, asin, sqrt

import google.generativeai as genai


class ItemStatus(Enum):
    ACTIVE = "active"
    MATCHED = "matched"
    EXPIRED = "expired"
    SPAM = "spam"


class ItemType(Enum):
    FOUND = "found"
    LOST = "lost"


@dataclass
class ItemData:
    """Core item data structure"""
    id: str
    type: ItemType
    status: ItemStatus

    # Core description fields
    raw_description: str  # Original user description
    ai_description: str  # AI-enhanced description with standardized terms
    category: str  # e.g., "clothing", "electronics", "accessories"
    subcategory: str  # e.g., "jacket", "phone", "keys"

    # Structured attributes for better matching
    attributes: Dict[str, str]  # color, material, brand, size, etc.
    keywords: List[str]  # extracted keywords for text search
    synonyms: List[str]  # alternative terms for matching

    # Contact & location
    contact_email: str
    location: Dict[str, any]  # address, lat, lon, geohash

    # Embeddings for semantic search
    embedding_vector: List[float]

    # Metadata
    timestamp: dt.datetime
    expires_at: dt.datetime
    matched_with: Optional[str] = None


def enhance_description_with_ai(raw_description: str) -> Dict[str, any]:
    """
    Use AI to extract structured information from the description
    """
    try:
        model = genai.GenerativeModel("gemini-pro")
        prompt = f"""
        Analyze this found/lost item description and extract structured information.
        Return a JSON object with these fields:

        {{
            "ai_description": "Enhanced description with standardized terms (30-50 words)",
            "category": "main category (clothing/electronics/accessories/documents/jewelry/bags/keys/other)",
            "subcategory": "specific type (jacket/phone/wallet/keys/backpack/etc)",
            "attributes": {{
                "color": "primary color if mentioned",
                "material": "material if mentioned (leather/fabric/plastic/metal)",
                "brand": "brand if visible/mentioned",
                "size": "size if mentioned (small/medium/large/XL or specific)",
                "condition": "condition if mentioned (new/used/worn/damaged)"
            }},
            "keywords": ["list", "of", "important", "searchable", "keywords"],
            "synonyms": ["alternative", "terms", "that", "might", "match", "this", "item"]
        }}

        Original description: {raw_description}

        IMPORTANT RULES:
        - Use standardized terms (e.g., "rain jacket" → "waterproof jacket")
        - Include common synonyms that users might search for
        - For jackets: include terms like "coat", "windbreaker", "rain jacket", "waterproof jacket"
        - Extract all visible attributes, but only if clearly mentioned
        - Only return valid JSON, no extra text
        - Be generous with synonyms to help matching

        Examples of good synonyms:
        - jacket → ["coat", "windbreaker", "outerwear", "rain jacket"]
        - phone → ["mobile", "smartphone", "cell phone", "iPhone", "Android"]
        - keys → ["keychain", "car keys", "house keys", "key ring"]
        - wallet → ["purse", "billfold", "card holder"]
        """

        response = model.generate_content(prompt).text.strip()

        # Extract JSON from response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())

            # Ensure all required fields exist with defaults
            return {
                "ai_description": data.get("ai_description", raw_description),
                "category": data.get("category", "other"),
                "subcategory": data.get("subcategory", "unknown"),
                "attributes": data.get("attributes", {}),
                "keywords": data.get("keywords", raw_description.lower().split()),
                "synonyms": data.get("synonyms", [])
            }
        else:
            raise ValueError("No JSON found in AI response")

    except Exception as e:
        print(f"AI enhancement failed: {e}")
        # Fallback to basic parsing
        words = raw_description.lower().split()
        return {
            "ai_description": raw_description,
            "category": "other",
            "subcategory": "unknown",
            "attributes": {},
            "keywords": words,
            "synonyms": []
        }


def create_composite_text_for_embedding(item_data: Dict) -> str:
    """
    Create optimized text for embedding that includes synonyms
    """
    parts = [
        item_data["ai_description"],
        item_data["category"],
        item_data["subcategory"],
        " ".join(item_data["keywords"]),
        " ".join(item_data["synonyms"]),
        " ".join([f"{k} {v}" for k, v in item_data["attributes"].items() if v])
    ]
    return " ".join(filter(None, parts))


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in kilometers using Haversine formula"""
    if lat1 == lat2 and lon1 == lon2:
        return 0.0

    R = 6371  # Earth radius in kilometers

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return R * c


def calculate_attribute_similarity(attrs1: Dict, attrs2: Dict) -> float:
    """Calculate similarity between attribute dictionaries"""
    if not attrs1 or not attrs2:
        return 0.0

    # Only compare attributes that exist in both items
    common_keys = set(attrs1.keys()) & set(attrs2.keys())
    if not common_keys:
        return 0.0

    # Count exact matches
    matches = 0
    for key in common_keys:
        val1 = str(attrs1[key]).lower().strip()
        val2 = str(attrs2[key]).lower().strip()

        if val1 == val2:
            matches += 1
        elif key == "color" and (val1 in val2 or val2 in val1):
            # Partial color matches (e.g., "dark blue" vs "blue")
            matches += 0.7

    return matches / len(common_keys)


def calculate_match_confidence(item1: Dict, item2: Dict, vector_similarity: float = 0.8) -> float:
    """
    Calculate overall match confidence using multiple factors
    """
    confidence = 0.0

    # Vector similarity (40% weight) - higher similarity = higher confidence
    confidence += 0.4 * vector_similarity

    # Category exact match (20% weight)
    if item1["category"] == item2["category"]:
        confidence += 0.2

    # Subcategory match (15% weight)
    if item1["subcategory"] == item2["subcategory"]:
        confidence += 0.15

    # Attribute matching (10% weight)
    attr_score = calculate_attribute_similarity(item1["attributes"], item2["attributes"])
    confidence += 0.1 * attr_score

    # Keyword overlap (5% weight)
    keywords1 = set(item1.get("keywords", []))
    keywords2 = set(item2.get("keywords", []))
    if keywords1 and keywords2:
        overlap = len(keywords1 & keywords2) / len(keywords1 | keywords2)
        confidence += 0.05 * overlap

    # Time proximity (5% weight) - items found/lost closer in time are more likely to match
    time_diff = abs((item1["timestamp"] - item2["timestamp"]).days)
    time_score = max(0, 1 - time_diff / 14)  # Decay over 14 days
    confidence += 0.05 * time_score

    # Location proximity (5% weight)
    distance = calculate_distance(
        item1["location"]["lat"], item1["location"]["lon"],
        item2["location"]["lat"], item2["location"]["lon"]
    )
    location_score = max(0, 1 - distance / 10)  # Decay over 10km
    confidence += 0.05 * location_score

    return min(1.0, confidence)


def normalize_email(email: str) -> str:
    """Normalize email address for consistent storage"""
    return email.lower().strip()


def is_valid_coordinates(latitude: float, longitude: float) -> bool:
    """Validate latitude and longitude ranges"""
    return -90 <= latitude <= 90 and -180 <= longitude <= 180


def generate_search_variations(text: str) -> List[str]:
    """Generate search variations for better matching"""
    variations = [text.lower().strip()]

    # Remove common words
    stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
    words = [w for w in text.lower().split() if w not in stop_words]
    if len(words) != len(text.split()):
        variations.append(" ".join(words))

    # Add individual important words
    important_words = [w for w in words if len(w) > 3]
    variations.extend(important_words)

    return list(set(variations))  # Remove duplicates