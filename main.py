from contextlib import asynccontextmanager
import uvicorn
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from config import settings
from app.api import app as api_app, initialize_app

BASE_DIR = Path(__file__).resolve().parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Mounted sub-applications do not reliably receive the root lifespan event.
    initialize_app()
    yield


app=FastAPI(lifespan=lifespan)
app.mount("/api",api_app)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}

@app.get("/")
async def index():
    """Web 界面：客服档案前端。"""
    return FileResponse(BASE_DIR / "index.html")

if __name__ == "__main__":
    print("🚀 Starting Customer Support Chatbot...")
    print(f"📱 Web Interface: http://{settings.host}:{settings.port}")
    print(f"🔌 API Documentation: http://{settings.host}:{settings.port}/api/docs")
    print(f"📊 API Health Check: http://{settings.host}:{settings.port}/api/health")
    print("=" * 50)

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )
