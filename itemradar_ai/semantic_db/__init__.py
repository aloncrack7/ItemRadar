"""
Lost & Found DB with Semantic Matching
--------------------------------------
Public API:

    register_item(...)
    find_potential_matches(...)
"""

from .models import (ItemType, ItemStatus, ItemData,
                     enhance_description_with_ai,
                     create_composite_text_for_embedding,
                     calculate_distance, calculate_match_confidence,
                     calculate_attribute_similarity)

from .core import register_item, find_potential_matches   # noqa: F401  (re-export)
