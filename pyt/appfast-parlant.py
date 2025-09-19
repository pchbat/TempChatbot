# uvicorn appfast:app --host 127.0.0.1 --port 5001
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from functions import get_answer
import logging
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import uuid
from typing import Dict, Any, List

logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize FastAPI app
app = FastAPI()

# Allow CORS for all routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DATA MODELS ---
class SessionRequest(BaseModel):
    agent_id: str

class SessionResponse(BaseModel):
    id: str
    agent_id: str
    customer_id: str
    creation_utc: str
    consumption_offsets: Dict

class AgentDetails(BaseModel):
    id: str
    name: str
    description: str
    welcome_message: str

class EventRequest(BaseModel):
    message: str

# This model represents a single event in the chat
class Event(BaseModel):
    id: str
    source: str
    kind: str
    offset: int
    creation_utc: str
    correlation_id: str
    deleted: bool
    data: Dict[str, Any]

# --- ENDPOINTS ---
@app.post("/sessions", response_model=SessionResponse)
async def create_session(request: SessionRequest):
    session_id = str(uuid.uuid4())
    customer_id = str(uuid.uuid4())
    creation_time = datetime.now(timezone.utc).isoformat()
    logging.info(f"New session created: {session_id} for agent {request.agent_id}")
    return {
        "id": session_id,
        "agent_id": request.agent_id,
        "customer_id": customer_id,
        "creation_utc": creation_time,
        "consumption_offsets": {}
    }

@app.get("/agents/{agent_id}", response_model=AgentDetails)
async def get_agent_details(agent_id: str):
    logging.info(f"Fetching details for agent: {agent_id}")
    return {
        "id": agent_id,
        "name": "AI Support Assistant",
        "description": "I am here to help with your questions.",
        "welcome_message": "Hello! How can I assist you today?"
    }

# The response_model is now a List of Event objects
@app.post("/sessions/{session_id}/events", response_model=List[Event])
async def handle_session_events(session_id: str, event: EventRequest, request: Request):
    try:
        user_message = event.message
        if not user_message:
            raise HTTPException(status_code=400, detail="Message cannot be empty")

        logging.info(f"Received message for session {session_id}: {user_message}")
        
        agent_response = get_answer(user_message)
        
        logging.info(f"Sending response for session {session_id}: {agent_response}")
        
        # We now return a list containing the single event object
        return [{
            "id": str(uuid.uuid4()),
            "source": "agent",
            "kind": "message",
            "offset": 1, 
            "creation_utc": datetime.now(timezone.utc).isoformat(),
            "correlation_id": str(uuid.uuid4()),
            "deleted": False,
            "data": {
                "message": agent_response
            }
        }]
    except Exception as e:
        logging.error(f"Error processing event for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def home():
    return {"message": "AISE"}

@app.get("/get_answer")
async def get_answer_api(query: str, request: Request, history: str = ""):
    try:
        response = get_answer(query)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
