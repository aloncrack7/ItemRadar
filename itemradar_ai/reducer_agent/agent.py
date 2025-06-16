import os
import uuid
import datetime
from dotenv import load_dotenv

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

def check_number_of_text(texts: list[str]) -> bool:
    """Returns True if the number of texts is greater than 1, otherwise False."""
    return len(texts) > 1

# -----------------------------------------------------------------------------
# Definición del agente ADK
# -----------------------------------------------------------------------------

root_agent = Agent(
    name="ReducerAgent",
    model="gemini-2.0-flash",
    description=(
        """
        You are an agent that helps to reduce the number of objects in a list.
        You would reived the description of the objects in a list,
        you woud generate the question that best reduces the number of objects
        as if you were playing who's who.
        You will use the LLM to generate the best question to ask.
        The question should be clear and concise, and should be able to be answered with a yes or no.
        You would return the question as a string.
        """
    ),
    instruction=(
        """
        Whenever you recived a list of objects, you should generate the question that best reduces the 
        number of objects in the list.
        Check if the number of objects in the list is greater than 1 calling the function `check_number_of_text` 
        using the list **texts**.	
        You should use the LLM to generate the question.
        Return the question as a string.
        """
    ),
    tools=[]
)

# ─── Debug/Setup function ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=== ItemRadar Model Check ===")