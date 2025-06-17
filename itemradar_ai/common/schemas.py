from pydantic import BaseModel
from typing import List, Optional

class SearchParams(BaseModel):
    description: str
    location: str

class FoundItem(BaseModel):
    id: str
    description: str
    location: str
    metadata: dict

class MatchResult(BaseModel):
    items: List[FoundItem]
    confidence_scores: List[float]
