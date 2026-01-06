import os
import sys
import logging
from dotenv import load_dotenv
load_dotenv()
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware


from utils.logging_config import setup_logging
from endpoints.classifier import router as classifier_router
import Tools.compararticket_tool
from endpoints.session_token import router as session_router
from endpoints.logsdownload import router as logs_router
from endpoints.chat_v2 import router as chat_v2_router



# 🔥 Force-import all tool modules to register them with the registry
import Tools.ticket_tool
import Tools.query_tool
import Tools.semantic_tool


# Load env vars
setup_logging()

REQUIRED_KEYS = [
    "OPENAI_API_KEY_Clasificador",
    "OPENAI_API_KEY_Continuada", 
    "OPENAI_API_KEY_ISO",
    "OPENAI_API_KEY_Query",
    "OPENAI_API_KEY_Semantic",
    "ZELL_API_KEY",
    "ZELL_USER",
    "ZELL_PASSWORD"
]

for key in REQUIRED_KEYS:
    if not os.getenv(key):
        logging.warning(f"⚠️ Environment variable missing: {key}")
        if key == "OPENAI_API_KEY_Clasificador":
            print(f"ERROR: {key} environment variable is not set!", file=sys.stderr)
            print("The classifier will not work without a valid API key.", file=sys.stderr)
            print("Please set this in your .env file.", file=sys.stderr)

app = FastAPI(
    title="AI Assistant API",
    description="API for interacting with AI tools for tickets, ISO, and more",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"An unexpected error occurred: {str(exc)}"}
    )

# Routers
app.include_router(classifier_router)
app.include_router(session_router)
app.include_router(logs_router)
app.include_router(chat_v2_router)

from Tools.compararticket_tool import router as compare_router
app.include_router(compare_router)

@app.get("/")
async def root():
    return {"message": "AI Assistant API is running 💡"}

# Initialize FAISS (semantic search)
from Tools.semantic_tool import init_semantic_tool
init_semantic_tool()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False, log_level="info")
