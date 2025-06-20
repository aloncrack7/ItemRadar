from fastapi import FastAPI, HTTPException, UploadFile, File
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

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Import the multiagent modules
from multiAgent.chatbot_manager.agent import root_agent as chatbot_manager
from multiAgent.lens_agent.agent import lens_agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

app = FastAPI(title="ItemRadar API", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:9002", "http://localhost:3000"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize session service and runners for multi-agent system
session_service = InMemorySessionService()
APP_NAME = "itemradar_api"

# Create runner for chatbot manager
manager_runner = Runner(
    agent=chatbot_manager,
    app_name=APP_NAME,
    session_service=session_service
)

# Pydantic models for request/response
class ChatRequest(BaseModel):
    user_input: str
    item_type: str
    photo_data_uri: Optional[str] = None
    history: Optional[List[dict]] = []

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

class FoundItemRequest(BaseModel):
    itemName: str
    description: str
    foundLocation: str
    pickupInstructions: str
    contactInfo: str
    images: Optional[List[str]] = []

class LostItemResponse(BaseModel):
    success: bool
    message: str
    search_id: Optional[str] = None
    matches: Optional[List[dict]] = []

class FoundItemResponse(BaseModel):
    success: bool
    message: str
    item_id: Optional[str] = None

@app.get("/")
async def root():
    return {"message": "ItemRadar API is running"}

@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_agent(request: ChatRequest):
    """
    Chat with the multi-agent system
    """
    try:
        # Generate a unique user ID for this session (in production, use actual user ID)
        user_id = f"web_user_{hash(request.user_input) % 1000000}"
        session_id = f"{user_id}_session"

        # Create or get session
        try:
            await session_service.create_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
        except Exception:
            # Session might already exist, that's okay
            pass

        # Prepare message parts
        parts = [types.Part(text=request.user_input)]

        # Add image if provided
        if request.photo_data_uri:
            try:
                # Extract base64 data from data URI
                if request.photo_data_uri.startswith('data:image/'):
                    # Remove the data URI prefix
                    image_data = request.photo_data_uri.split(',', 1)[1]
                    image_bytes = base64.b64decode(image_data)
                    
                    # Add image to message parts
                    parts.append(types.Part(
                        inline_data=types.Blob(
                            mime_type="image/jpeg",
                            data=image_data
                        )
                    ))
            except Exception as e:
                print(f"Error processing image: {e}")
                # Continue without image if there's an error

        user_content = types.Content(role='user', parts=parts)

        # Run the agent and collect the final response
        final_response = ""
        response_received = False

        async for event in manager_runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_content
        ):
            if event.is_final_response() and event.content and event.content.parts:
                # Process all parts of the response, not just text
                response_parts = []
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        response_parts.append(part.text)
                    # Handle function calls gracefully - they don't contribute to user-facing text
                    elif hasattr(part, 'function_call'):
                        # Function calls are handled internally by the agent
                        # We don't need to include them in the user response
                        continue
                
                # Combine all text parts
                final_response = " ".join(response_parts)
                response_received = True
                break

        if not response_received or not final_response.strip():
            return ChatResponse(
                success=False,
                response="",
                error="No valid response received from agent"
            )

        return ChatResponse(
            success=True,
            response=final_response.strip()
        )

    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        return ChatResponse(
            success=False,
            response="",
            error=f"Internal server error: {str(e)}"
        )

@app.post("/api/lost-item", response_model=LostItemResponse)
async def report_lost_item(request: LostItemRequest):
    """
    Report a lost item and initiate search using chatbot_manager
    """
    try:
        # Create a search context for the chatbot manager
        search_context = {
            "description": request.description,
            "location": request.lastSeenLocation,
            "contact_info": request.contactInfo,
            "item_name": request.itemName,
            "images": request.images
        }
        
        # Initialize the chatbot manager with the search parameters
        # This will trigger the search workflow
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
async def report_found_item(request: FoundItemRequest):
    """
    Report a found item using lens_agent
    """
    try:
        # Process the found item using lens_agent
        result = await process_found_item(request)
        
        return FoundItemResponse(
            success=True,
            message="Found item registered successfully. We'll match it with any lost item reports.",
            item_id=result.get("item_id")
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing found item: {str(e)}")

@app.get("/api/search-status/{search_id}")
async def get_search_status(search_id: str):
    """
    Get the status of a lost item search
    """
    try:
        # This would typically query a database for search status
        # For now, return a mock response
        return {
            "search_id": search_id,
            "status": "active",
            "matches_found": 0,
            "last_updated": "2024-01-01T00:00:00Z"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving search status: {str(e)}")

async def initiate_lost_item_search(search_context: dict) -> dict:
    """
    Initiate a lost item search using the chatbot_manager
    """
    try:
        # Create a tool context for the chatbot manager
        tool_context = type('ToolContext', (), {
            'state': {
                'search_params': {
                    'description': search_context['description'],
                    'location': search_context['lastSeenLocation']
                },
                'has_search_params': True,
                'contact_info': search_context['contact_info'],
                'item_name': search_context['item_name']
            }
        })()
        
        # Initialize the search using the initiate_search function
        from multiAgent.chatbot_manager.agent import initiate_search
        search_result = initiate_search(
            search_context['description'],
            search_context['lastSeenLocation'],
            tool_context
        )
        
        # Store the search in a database (mock for now)
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
    """
    Process a found item using the lens_agent
    """
    try:
        # Geocode the location
        geocode_result = lens_agent.geocode_location(request.foundLocation)
        
        if geocode_result.get("status") != "success":
            raise Exception(f"Failed to geocode location: {geocode_result.get('error_message')}")
        
        # Register the found item
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