import os
import uuid
import datetime
from dotenv import load_dotenv

from common import utils

from google.adk.agents import Agent
from google.cloud import firestore, aiplatform
from google.cloud import aiplatform
from vertexai.language_models import TextGenerationResponse

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

# -----------------------------------------------------------------------------
# Herramientas expuestas al LLM (solo tipos simples → dict)
# -----------------------------------------------------------------------------

def generate_question(texts: list[str]) -> str:
    """Devuelve la pregunata que mejor reduzca el numero de objetos descrios en *text* como un string"""
    try:
        # Usa Gemini 2.5 Flash para generar la mejor pregunta

        prompt = (
            "Given the next set of description:\n"
            + "\n".join(f"- {t}" for t in texts)
            + "\nWhat would be the best question to discard the maximun number of objects?"
        )

        response = aiplatform.LanguageModel(
            model_name="gemini-2.5-flash"
        ).predict(prompt=prompt)

        return response.text.strip()
    except Exception as e:
        return f"Error al comparar textos: {e}"

# -----------------------------------------------------------------------------
# Definición del agente ADK
# -----------------------------------------------------------------------------

root_agent = Agent(
    name="ReducerAgent",
    model="gemini-2.0-flash",
    description=(
        """Recibe listas de descripciones (tanto del MatcherAgent como del filterAgent) 
            de objertos, compara y elige la mejor pregunta (usando el LLM) para reducir el numero de objetos posibles."""
    ),
    instruction=(
        "Cuando se reciba una lista de descripciones se llama a LLM y se reponde con la mejor  pregunta posible."
    ),
    tools=[generate_question]
)

# ─── Debug/Setup function ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=== ItemRadar Model Check ===")