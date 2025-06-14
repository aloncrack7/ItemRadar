"""
Lost & Found Database Core Functions
------------------------------------
Main registration and matching logic with semantic search
"""

from __future__ import annotations

import os
import uuid
import datetime as dt
from typing import Dict, List, Optional

from google.cloud import aiplatform, firestore
from vertexai.language_models import TextEmbeddingModel
import pygeohash as pgh

from .models import (
    ItemType, ItemStatus, enhance_description_with_ai,
    create_composite_text_for_embedding, calculate_distance,
    calculate_match_confidence, normalize_email, is_valid_coordinates
)

# Initialize clients (consider lazy loading for better performance)
PROJECT_ID = os.getenv("PROJECT_ID")
INDEX_ID = os.getenv("INDEX_ID")

if not PROJECT_ID or not INDEX_ID:
    raise RuntimeError("PROJECT_ID and INDEX_ID must be set in environment")

_embed = TextEmbeddingModel.from_pretrained("textembedding-gecko@002")
_db = firestore.Client(project=PROJECT_ID)
_index = aiplatform.MatchingEngineIndex(INDEX_ID)


def register_item(
        raw_description: str,
        item_type: ItemType,
        contact_email: str,
        address: str,
        latitude: float,
        longitude: float,
        image_url: Optional[str] = None
) -> Dict:
    """
    Enhanced item registration with AI processing and semantic optimization

    Args:
        raw_description: User's original description of the item
        item_type: ItemType.FOUND or ItemType.LOST
        contact_email: Contact email for the person
        address: Human-readable address
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        image_url: Optional URL to item image

    Returns:
        Dict with status and item_id or error_message
    """
    try:
        # Validate inputs
        if not raw_description.strip():
            return {"status": "error", "error_message": "Description cannot be empty"}

        if not is_valid_coordinates(latitude, longitude):
            return {"status": "error", "error_message": "Invalid coordinates"}

        contact_email = normalize_email(contact_email)
        if "@" not in contact_email:
            return {"status": "error", "error_message": "Invalid email address"}

        print(f"Processing item: {raw_description[:50]}...")

        # 1. Enhance description with AI
        ai_data = enhance_description_with_ai(raw_description)
        print(f"AI categorized as: {ai_data['category']} -> {ai_data['subcategory']}")

        # 2. Create composite text for embedding
        composite_text = create_composite_text_for_embedding(ai_data)
        print(f"Composite text length: {len(composite_text)} chars")

        # 3. Generate embedding
        try:
            embeddings = _embed.get_embeddings([composite_text])
            embedding = embeddings[0].values
            print(f"Generated embedding with {len(embedding)} dimensions")
        except Exception as e:
            print(f"Embedding generation failed: {e}")
            return {"status": "error", "error_message": f"Failed to generate embedding: {str(e)}"}

        # 4. Generate geohash for location-based clustering
        geohash = pgh.encode(latitude, longitude, precision=7)  # ~150m precision

        # 5. Create item record
        item_id = f"{item_type.value}_{uuid.uuid4().hex[:8]}"
        now = dt.datetime.utcnow()

        item_doc = {
            "id": item_id,
            "type": item_type.value,
            "status": ItemStatus.ACTIVE.value,

            # Descriptions
            "raw_description": raw_description,
            "ai_description": ai_data["ai_description"],
            "category": ai_data["category"],
            "subcategory": ai_data["subcategory"],

            # Structured data
            "attributes": ai_data["attributes"],
            "keywords": ai_data["keywords"],
            "synonyms": ai_data.get("synonyms", []),

            # Contact & location
            "contact_email": contact_email,
            "location": {
                "address": address,
                "lat": latitude,
                "lon": longitude,
                "geohash": geohash
            },

            # For matching
            "composite_text": composite_text,
            "embedding_vector": embedding,

            # Metadata
            "timestamp": now,
            "expires_at": now + dt.timedelta(days=30),
            "image_url": image_url,
            "matched_with": None
        }

        # 6. Save to Vertex AI Matching Engine
        try:
            _index.upsert_datapoints([{
                "datapoint_id": item_id,
                "feature_vector": embedding
            }])
            print(f"Saved to Matching Engine: {item_id}")
        except Exception as e:
            print(f"Matching Engine save failed: {e}")
            # Continue anyway - Firestore save is more important

        # 7. Save to Firestore with optimized structure
        try:
            # Main collection
            _db.collection("items").document(item_id).set(item_doc)

            # Secondary index for faster category-based queries
            _db.collection("items_by_category").document(f"{ai_data['category']}_{item_id}").set({
                "item_id": item_id,
                "type": item_type.value,
                "subcategory": ai_data["subcategory"],
                "geohash": geohash,
                "timestamp": now,
                "category": ai_data["category"]
            })

            print(f"Saved to Firestore: {item_id}")

        except Exception as e:
            print(f"Firestore save failed: {e}")
            return {"status": "error", "error_message": f"Failed to save to database: {str(e)}"}

        return {
            "status": "success",
            "item_id": item_id,
            "category": ai_data["category"],
            "ai_description": ai_data["ai_description"]
        }

    except Exception as exc:
        print(f"Registration failed: {exc}")
        return {"status": "error", "error_message": str(exc)}


def find_potential_matches(
        item_id: str,
        max_distance_km: float = 5.0,
        similarity_threshold: float = 0.6,
        max_results: int = 10
) -> List[Dict]:
    """
    Find potential matches using semantic similarity and location filtering

    Args:
        item_id: ID of the item to find matches for
        max_distance_km: Maximum distance in kilometers
        similarity_threshold: Minimum similarity score (0-1)
        max_results: Maximum number of results to return

    Returns:
        List of potential match dictionaries sorted by confidence
    """
    try:
        # Get the source item
        source_doc = _db.collection("items").document(item_id).get()
        if not source_doc.exists:
            print(f"Source item not found: {item_id}")
            return []

        source_item = source_doc.to_dict()
        print(f"Finding matches for {source_item['type']} item: {source_item['ai_description'][:50]}...")

        # Determine opposite type (found items match with lost items and vice versa)
        opposite_type = "lost" if source_item["type"] == "found" else "found"

        # Strategy 1: Vector similarity search using Matching Engine
        candidates = []
        try:
            vector_matches = _index.find_neighbors(
                query_vector=source_item["embedding_vector"],
                num_neighbors=50  # Get more candidates for filtering
            )
            print(f"Found {len(vector_matches)} vector matches")

            # Process each vector match
            for match in vector_matches:
                try:
                    candidate_doc = _db.collection("items").document(match.id).get()
                    if not candidate_doc.exists:
                        continue

                    candidate = candidate_doc.to_dict()

                    # Filter by type, status, and basic criteria
                    if (candidate["type"] != opposite_type or
                            candidate["status"] != ItemStatus.ACTIVE.value):
                        continue

                    # Calculate geographical