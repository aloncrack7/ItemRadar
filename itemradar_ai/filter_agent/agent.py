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
    name="FilterAgent",
    model="gemini-2.0-flash",
    description=(
        """
        You are an agent that helps to filter the objects in a list
        You would receive the description of the objects in a list, together with a question and the answers
        you would take said question and filter which objects of the list fullfill the requirements posted by
        the question and response
        you will use an LLM to filter 
        You must return the objects that fullfil the question using a another reduced list
        Each element of the list is a string.
        """
    ),
    instruction=(
        """
        Whenever you recived a list of objects, a question and the answer you should filter the given to obtain 
        the list that fullfils the question and the answer.
        Check if the number of objects in the list is greater than 1 calling the function `check_number_of_text` 
        using the list **texts**.	
        You should use the LLM to generate the second list.
        Return the ONLY the list containing strings.
        """
    ),
    tools=[check_number_of_text]
)

# ─── Debug/Setup function ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=== ItemRadar Model Check ===")