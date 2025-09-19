# uvicorn appfast:app --host 127.0.0.1 --port 5001
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from functions import get_answer
import logging
from datetime import datetime

logging.basicConfig(filename='app.log', level = logging.INFO, format= '%(asctime)s - %(levelname)s - %(message)s')

# Initialize FastAPI app
app = FastAPI()

# Allow CORS for all routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins, you can restrict this for security
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

@app.get("/")
async def home():
    return {"message": "AISE"}

@app.get("/get_answer")
async def get_answer_api(query: str,request: Request,history: str = ""):
    try:
        request_time = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        client_ip = request.client.host
        server_port = request.url.hostname
        full_query = f"{history}\nUser: {query}" if history else f"User: {query}"
        
        response = get_answer(full_query)
        logging.info(f"Client: {client_ip} - Server: {server_port} - Request Time: {request_time} - Generated Answer: {response} - For Query: {query}")
        return response
    
    except Exception as e:
        logging.error(f"Failed to Generate Answer: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Run the FastAPI app with uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
