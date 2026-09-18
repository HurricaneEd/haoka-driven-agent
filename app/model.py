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


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    response: str = Field(..., description="Assistant response")
    session_id: str = Field(..., description="Session ID")
    conversation_id: str = Field(..., description="Conversation ID")
    sources: Optional[List[Dict[str, Any]]] = Field(None, description="Sources used for response")


class AuthCredentials(BaseModel):
    """Credentials used to register or sign in."""
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=8, max_length=128)


class AuthUser(BaseModel):
    """Public user information."""
    id: str
    email: str


class AuthResponse(BaseModel):
    """Successful authentication response."""
    token: str
    user: AuthUser


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


class KnowledgeDocumentItem(BaseModel):
    """Document-level knowledge base status returned to the management UI."""
    doc_id: str
    title: str
    filename: str
    category: str
    tags: List[str] = Field(default_factory=list)
    status: str
    chunk_count: int
    file_size: int
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class KnowledgeChunkItem(BaseModel):
    id: str
    section: str
    chunk_index: int
    content: str
