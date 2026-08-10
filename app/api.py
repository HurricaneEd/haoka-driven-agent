from contextlib import asynccontextmanager
from fastapi import FastAPI
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from config import settings
from app.database import init_db
from app.knowledge_base import initialize_knowledge_base

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动逻辑
    print("Initializing application...")
    init_db()
    initialize_knowledge_base()
    print("Application initialized successfully!")
    yield
    # 关闭逻辑
app=FastAPI(lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.api:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )