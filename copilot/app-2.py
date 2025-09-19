# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
# uvicorn app-2:app --host 127.0.0.1 --port 5000
# --- Imports ---
from fastapi import FastAPI
from fastapi.responses import FileResponse
import asyncio
import logging
import sys
from app import create_client  # Assuming 'app.py' contains create_client
from microsoft.agents.activity import ActivityTypes
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware  # <-- IMPORT THIS

# --- App Initialization ---
app = FastAPI()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# --- CORS MIDDLEWARE CONFIGURATION ---
# This block is added to handle requests from different origins (e.g., your Node.js frontend)
origins = ["*"]  # Allows all origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)
# --- END OF CORS CONFIGURATION ---

# Store conversation IDs for sessions
conversations = {}

@app.on_event("startup")
async def startup_event():
    global copilot_client
    logger.info("Starting copilot client...")
    copilot_client = create_client()

@app.post("/start")
async def start_conversation():
    act = copilot_client.start_conversation(True)
    actions = []
    # Initialize conversation_id with a default value
    conversation_id = None
    async for action in act:
        if action.text:
            actions.append(action.text)
            # Ensure conversation object and id exist before assigning
            if action.conversation and action.conversation.id:
                conversation_id = action.conversation.id
                conversations["default"] = conversation_id
    if conversation_id is None:
        # Handle case where no message with a conversation ID was received
        # This part might need adjustment based on how start_conversation behaves
        # For now, we'll raise an error or return a specific message.
        return {"error": "Could not initialize conversation ID."}
        
    return {"conversation_id": conversation_id, "suggested_actions": actions}

@app.post("/ask")
async def ask_question(query: str, conversation_id: str):
    replies_list = []
    try:
        replies = copilot_client.ask_question(query, conversation_id)
        async for reply in replies:
            if reply.type == ActivityTypes.message:
                replies_list.append({"type": "message", "text": reply.text})
            elif reply.type == ActivityTypes.end_of_conversation:
                replies_list.append({"type": "end", "text": "Conversation ended."})
    except Exception as e:
        logger.error(f"Error during ask_question: {e}")
        return {"error": "An error occurred while communicating with the copilot."}
        
    return {"replies": replies_list}