import os
import uuid
import datetime
from dotenv import load_dotenv

from google.adk.agents import Agent
from google.cloud import firestore, aiplatform
from vertexai.language_models import TextEmbeddingModel

# Cargar variables de entorno desde .env o entorno del contenedor
load_dotenv()

PROJECT_ID: str | None = os.getenv("PROJECT_ID")
REGION: str | None = os.getenv("REGION")
INDEX_ID: str | None = os.getenv("INDEX_ID")

# ------------------------------------------------------------------
# Helpers internos
# ------------------------------------------------------------------

def _ensure_config() -> None:
    if not all([PROJECT_ID, REGION, INDEX_ID]):
        raise RuntimeError(
            "Faltan PROJECT_ID, REGION o INDEX_ID en variables de entorno o .env"
        )

# ------------------------------------------------------------------
# Herramientas expuestas al LLM (deben usar tipos simples)
# ------------------------------------------------------------------

def generate_embedding(text: str) -> dict:  # noqa: D401
    """Devuelve el embedding de *text* como lista de floats."""
    try:
        model = TextEmbeddingModel.from_pretrained("textembedding-gecko@latest")
        vec = model.get_embeddings([text])[0].values
        return {"status": "success", "embedding": vec}
    except Exception as exc:  # pragma: no cover
        return {"status": "error", "error_message": str(exc)}


def register_found_item(
    description: str,
    location: str = "",
    photo_url: str = "",
) -> dict:  # noqa: D401
    """Registra un objeto encontrado.

    Args:
        description: Descripción textual del objeto.
        location: Ubicación donde se encontró (cadena vacía si no se especifica).
        photo_url: URL pública de la foto (cadena vacía si no se especifica).
    """
    try:
        _ensure_config()

        # 1) Generar embedding
        model = TextEmbeddingModel.from_pretrained("textembedding-gecko@latest")
        embedding = model.get_embeddings([description])[0].values

        # 2) Upsert en Matching Engine
        aiplatform.init(project=PROJECT_ID, location=REGION)
        index = aiplatform.MatchingEngineIndex(INDEX_ID)
        item_id = f"found_{uuid.uuid4().hex[:8]}"
        index.upsert_datapoints([
            {"datapoint_id": item_id, "feature_vector": embedding}
        ])

        # 3) Guardar metadatos en Firestore
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

        return {"status": "success", "item_id": item_id}

    except Exception as exc:  # pragma: no cover
        return {"status": "error", "error_message": str(exc)}


# ------------------------------------------------------------------
# Definición del agente ADK
# ------------------------------------------------------------------

root_agent = Agent(
    name="lens_agent",
    model="gemini-2.0-flash",
    description=
        "Ingesta de objetos encontrados: genera embedding, lo indexa en Vertex AI "
        "Matching Engine y guarda metadatos en Firestore.",
    instruction=(
        "Cuando el usuario describa un nuevo objeto encontrado, llama a "
        "register_found_item con la descripción, ubicación y URL de foto."
    ),
    tools=[generate_embedding, register_found_item],
)
