from fastapi import FastAPI, HTTPException, UploadFile, File, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import sys
import os
import json
import asyncio
from pathlib import Path
import argparse
import base64
import io
import logging
import uuid

# Configura logging básico
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("activity.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Import multiagent modules
from multiAgent.chatbot_manager.agent import root_agent as chatbot_manager
from multiAgent.lens_agent.agent import lens_agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

app = FastAPI(title="ItemRadar API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:9002", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session & Runner
session_service = InMemorySessionService()
APP_NAME = "itemradar_api"

manager_runner = Runner(
    agent=chatbot_manager,
    app_name=APP_NAME,
    session_service=session_service
)

# Modelos
class ChatRequest(BaseModel):
    user_input: str
    item_type: str
    photo_data_uri: Optional[str] = None
    history: Optional[List[dict]] = []
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    success: bool
    response: str
    error: Optional[str] = None

class LostItemRequest(BaseModel):
    itemName: str
    description: str
    lastSeenLocation: str
    contactInfo: str
    images: Optional[List[str]] = []
    session_id: Optional[str] = None  # Añadido

class FoundItemRequest(BaseModel):
    itemName: str
    description: str
    foundLocation: str
    pickupInstructions: str
    contactInfo: str
    images: Optional[List[str]] = []
    session_id: Optional[str] = None  # Añadido

class LostItemResponse(BaseModel):
    success: bool
    message: str
    search_id: Optional[str] = None
    matches: Optional[List[dict]] = []

class FoundItemResponse(BaseModel):
    success: bool
    message: str
    item_id: Optional[str] = None

def get_or_create_session_id(req: Request, response: Response, provided_session_id: Optional[str]) -> str:
    # Check if cookie or parameter session exists
    session_id = provided_session_id or req.cookies.get("session_id")

    if session_id:
        # Set it again just in case the client didn't persist it
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            max_age=7 * 24 * 60 * 60,
            secure=False,
            samesite="Lax",
            path="/"
        )
        user_id = session_id.split("_")[0]
        logger.info(f"Re-setting existing session: {session_id} | user_id: {user_id}")
        return session_id

    # Create a new session
    new_session_id = f"{uuid.uuid4().hex}_session"
    user_id = new_session_id.split("_")[0]

    response.set_cookie(
        key="session_id",
        value=new_session_id,
        httponly=True,
        max_age=7 * 24 * 60 * 60,
        secure=False,
        samesite="Lax",
        path="/"
    )
    logger.info(f"Created new session: {new_session_id} | user_id: {user_id}")
    return new_session_id


@app.get("/")
async def root():
    return {"message": "ItemRadar API is running"}

@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_agent(request: ChatRequest, *, response: Response, req: Request):
    try:
        session_id = get_or_create_session_id(req, response, request.session_id)
        user_id = session_id.split("_")[0]

        try:
            await session_service.create_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
        except Exception:
            pass

        parts = [types.Part(text=request.user_input)]
        if request.photo_data_uri and request.photo_data_uri.startswith('data:image/'):
            try:
                image_data = request.photo_data_uri.split(',', 1)[1]
                parts.append(types.Part(
                    inline_data=types.Blob(
                        mime_type="image/jpeg",
                        data=image_data
                    )
                ))
            except Exception as e:
                print(f"Error processing image: {e}")

        user_content = types.Content(role='user', parts=parts)
        final_response = ""
        response_received = False

        async for event in manager_runner.run_async(user_id=user_id, session_id=session_id, new_message=user_content):
            if event.is_final_response() and event.content and event.content.parts:
                final_response = " ".join([
                    part.text for part in event.content.parts if hasattr(part, 'text') and part.text
                ])
                response_received = True
                break

        if not response_received or not final_response.strip():
            return ChatResponse(success=False, response="", error="No valid response received from agent")

        return ChatResponse(success=True, response=final_response.strip())

    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        return ChatResponse(success=False, response="", error=f"Internal server error: {str(e)}")

@app.post("/api/lost-item", response_model=LostItemResponse)
async def report_lost_item(request: LostItemRequest, *, response: Response, req: Request):
    try:
        session_id = get_or_create_session_id(req, response, request.session_id)
        user_id = session_id.split("_")[0]

        search_context = {
            "description": request.description,
            "location": request.lastSeenLocation,
            "contact_info": request.contactInfo,
            "item_name": request.itemName,
            "images": request.images
        }

        search_result = await initiate_lost_item_search(search_context)

        return LostItemResponse(
            success=True,
            message="Lost item search initiated successfully. We'll notify you of any matches.",
            search_id=search_result.get("search_id"),
            matches=search_result.get("initial_matches", [])
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing lost item: {str(e)}")

@app.post("/api/found-item", response_model=FoundItemResponse)
async def report_found_item(request: FoundItemRequest, *, response: Response, req: Request):
    try:
        session_id = get_or_create_session_id(req, response, request.session_id)
        user_id = session_id.split("_")[0]

        result = await process_found_item(request)

        return FoundItemResponse(
            success=True,
            message="Found item registered successfully. We'll match it with any lost item reports.",
            item_id=result.get("item_id")
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing found item: {str(e)}")

@app.get("/api/search-status/{search_id}")
async def get_search_status(search_id: str, *, response: Response, req: Request):
    try:
        session_id = get_or_create_session_id(req, response, None)
        user_id = session_id.split("_")[0]

        return {
            "search_id": search_id,
            "status": "active",
            "matches_found": 0,
            "last_updated": "2024-01-01T00:00:00Z"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving search status: {str(e)}")

async def initiate_lost_item_search(search_context: dict) -> dict:
    try:
        tool_context = type('ToolContext', (), {
            'state': {
                'search_params': {
                    'description': search_context['description'],
                    'location': search_context['location']
                },
                'has_search_params': True,
                'contact_info': search_context['contact_info'],
                'item_name': search_context['item_name']
            }
        })()

        from multiAgent.chatbot_manager.agent import initiate_search
        search_result = initiate_search(
            search_context['description'],
            search_context['location'],
            tool_context
        )

        search_id = f"search_{len(search_context['description'])}"

        return {
            "search_id": search_id,
            "status": "initiated",
            "initial_matches": []
        }

    except Exception as e:
        print(f"Error in lost item search: {e}")
        raise

async def process_found_item(request: FoundItemRequest) -> dict:
    try:
        geocode_result = lens_agent.geocode_location(request.foundLocation)
        if geocode_result.get("status") != "success":
            raise Exception(f"Failed to geocode location: {geocode_result.get('error_message')}")

        registration_result = lens_agent.register_found_item(
            description=request.description,
            contact_email=request.contactInfo,
            address=geocode_result["address"],
            latitude=geocode_result["latitude"],
            longitude=geocode_result["longitude"]
        )

        if registration_result.get("status") != "success":
            raise Exception(f"Failed to register found item: {registration_result.get('error_message')}")

        return {
            "item_id": registration_result.get("item_id"),
            "status": "registered"
        }

    except Exception as e:
        print(f"Error in found item processing: {e}")
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='ItemRadar API Server')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the server on')
    args = parser.parse_args()

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=args.port)

