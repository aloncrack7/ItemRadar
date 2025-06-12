import os, uuid, datetime
from vertexai.language_models import TextEmbeddingModel
from google.cloud import aiplatform, firestore

def get_embedding(text: str) -> list[float]:
    model = TextEmbeddingModel.from_pretrained("textembedding-gecko@latest")
    return model.get_embeddings([text])[0].values

def matching_index():
    aiplatform.init(project=os.getenv("PROJECT_ID"), location=os.getenv("REGION"))
    return aiplatform.MatchingEngineIndex(os.getenv("INDEX_ID"))
