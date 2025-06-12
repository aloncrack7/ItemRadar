import os
import uuid
import datetime
from dotenv import load_dotenv

from google.adk.agents import Agent
from google.cloud import firestore, aiplatform
from vertexai.language_models import TextEmbeddingModel
from vertexai.vision_models import Image, ImageToTextModel

# -----------------------------------------------------------------------------
# Configuración y bootstrap
# -----------------------------------------------------------------------------

load_dotenv()

PROJECT_ID: str | None = os.getenv("PROJECT_ID")
REGION: str | None = os.getenv("REGION", "us-central1")
INDEX_ID: str | None = os.getenv("INDEX_ID")

if not all([PROJECT_ID, REGION, INDEX_ID]):
    raise RuntimeError(
        "Faltan PROJECT_ID, REGION o INDEX_ID en variables de entorno o .env"
    )

# Iniciar Vertex AI **una sola vez** para que todos los métodos hereden contexto
# (esto evita el 404 por usar el proyecto anónimo "32555940559").
aiplatform.init(project=PROJECT_ID, location=REGION)

# Fijamos versión estable del modelo de embedding
EMBED_MODEL_ID = "textembedding-gecko@002"
_embedding_model = TextEmbeddingModel.from_pretrained(EMBED_MODEL_ID)

# -----------------------------------------------------------------------------
# Herramientas expuestas al LLM (solo tipos simples → dict)
# -----------------------------------------------------------------------------

def generate_embedding(text: str) -> dict:
    """Devuelve el embedding de *text* como lista de floats."""
    try:
        vec = _embedding_model.get_embeddings([text])[0].values
        return {"status": "success", "embedding": vec}
    except Exception as exc:  # pragma: no cover
        return {"status": "error", "error_message": str(exc)}


def extract_description_from_image(photo_url: str) -> str:
    """Uses Gemini Vision to extract a description from an image URL."""
    try:
        image = Image.from_uri(photo_url)
        model = ImageToTextModel.from_pretrained("gemini-1.0-pro-vision")
        prompt = "Describe the main object in this image as if for a lost-and-found notice."
        response = model.predict(image, prompt=prompt, max_output_tokens=128)
        return response.text.strip()
    except Exception as exc:
        raise RuntimeError(f"Gemini Vision error: {exc}")


def register_found_item(
    location: str,
    photo_url: str,
) -> dict:
    """Registra un objeto encontrado usando Gemini Vision para extraer la descripción."""
    try:
        # 1) Extraer descripción con Gemini Vision
        description = extract_description_from_image(photo_url)
        if not description:
            return {"status": "error", "error_message": "No description extracted from image."}
        # 2) Generar embedding
        embedding = _embedding_model.get_embeddings([description])[0].values
        # 3) Upsert en Matching Engine
        index = aiplatform.MatchingEngineIndex(INDEX_ID)
        item_id = f"found_{uuid.uuid4().hex[:8]}"
        index.upsert_datapoints(
            [{"datapoint_id": item_id, "feature_vector": embedding}]
        )
        # 4) Guardar metadatos en Firestore
        db = firestore.Client(project=PROJECT_ID)
        db.collection("found_items").document(item_id).set(
            {
                "id": item_id,
                "description": description,
                "location": location or None,
                "photo_url": photo_url or None,
                "timestamp": datetime.datetime.utcnow(),
            }
        )
        return {"status": "success", "item_id": item_id, "description": description}
    except Exception as exc:  # pragma: no cover
        return {"status": "error", "error_message": str(exc)}


# -----------------------------------------------------------------------------
# Definición del agente ADK
# -----------------------------------------------------------------------------

root_agent = Agent(
    name="lens_agent",
    model="gemini-2.0-flash",
    description=(
        "Ingesta de objetos encontrados: extrae descripción con Gemini Vision, genera embedding, lo indexa en Vertex AI Matching Engine y guarda metadatos en Firestore."
    ),
    instruction=(
        "Cuando el usuario suba la foto de un objeto encontrado, llama a register_found_item con la ubicación y URL de foto."
    ),
    tools=[generate_embedding, register_found_item],
)
