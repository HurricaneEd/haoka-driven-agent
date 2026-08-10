from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Individual chat message model."""
    role: str = Field(..., description="Role of the message sender (user/assistant)")
    content: str = Field(..., description="Content of the message")
    timestamp: datetime = Field(default_factory=datetime.now(timezone.utc))


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str = Field(..., description="User message")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    user_id: Optional[str] = Field(None, description="User identifier")


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    response: str = Field(..., description="Assistant response")
    session_id: str = Field(..., description="Session ID")
    conversation_id: str = Field(..., description="Conversation ID")
    sources: Optional[List[Dict[str, Any]]] = Field(None, description="Sources used for response")
    confidence: float = Field(..., description="Confidence score of the response")


class ConversationHistory(BaseModel):
    """Model for conversation history."""
    conversation_id: str
    session_id: str
    user_id: Optional[str]
    messages: List[ChatMessage]
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseItem(BaseModel):
    """Model for knowledge base items."""
    id: str
    title: str
    content: str
    category: str
    tags: List[str] = []
    created_at: datetime
    updated_at: datetime