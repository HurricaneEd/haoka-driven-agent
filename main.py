import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from config import settings
from app.api import app as api_app

app=FastAPI()
app.mount("/api",api_app)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}

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