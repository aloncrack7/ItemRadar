from fastapi import FastAPI, Response, Request
from fastapi.middleware.cors import CORSMiddleware
import uuid
import logging

app = FastAPI()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("activity.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:9002", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/test-cookie")
async def test_cookie(response: Response):
    test_session_id = f"test_{uuid.uuid4().hex}_session"
    logger.info(f"Setting test cookie: {test_session_id}")
    response.set_cookie(
        key="test_session_id",
        value=test_session_id,
        httponly=True,
        max_age=60, # Short expiry for testing
        secure=False,
        samesite="Lax",
        path="/"
    )
    return {"message": "Test cookie set, check network tab!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)