from contextlib import asynccontextmanager
from fastapi import BackgroundTasks, FastAPI, File, Form, Header, UploadFile
from typing import List, Optional
from fastapi import Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pathlib import Path
import uuid

from config import settings
from app.auth import (
    create_access_token,
    hash_password,
    hash_token,
    is_valid_email,
    normalize_email,
    session_expiry,
    verify_password,
)
from app.database import init_db, DatabaseManager, get_db, UserAccount
from app.knowledge_base import initialize_knowledge_base
from app.knowledge_documents import (
    KnowledgeUploadError,
    delete_knowledge_document,
    process_knowledge_document,
    resolve_source,
    save_upload,
)
from app.rag.schemas import normalize_tags
from app.chatbot import chatbot
from app.model import (
    AuthCredentials,
    AuthResponse,
    AuthUser,
    ChatRequest,
    ChatResponse,
    ConversationHistory,
    KnowledgeBaseItem,
    KnowledgeChunkItem,
    KnowledgeDocumentItem,
)



def initialize_app() -> None:
    # 启动逻辑
    print("Initializing application...")
    init_db()
    initialize_knowledge_base()
    print("Application initialized successfully!")


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_app()
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


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> UserAccount:
    """Resolve and validate the current bearer session."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录状态无效，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = DatabaseManager(db).get_user_by_token_hash(hash_token(token))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录状态已失效，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def build_auth_response(user: UserAccount, db_manager: DatabaseManager) -> AuthResponse:
    token, token_hash = create_access_token()
    db_manager.create_auth_session(token_hash, user.id, session_expiry())
    return AuthResponse(
        token=token,
        user=AuthUser(id=user.id, email=user.email),
    )


def knowledge_document_response(document) -> KnowledgeDocumentItem:
    return KnowledgeDocumentItem(
        doc_id=document.doc_id,
        title=document.title,
        filename=document.filename,
        category=document.category,
        tags=list(normalize_tags(document.tags)),
        status=document.status,
        chunk_count=document.chunk_count,
        file_size=document.file_size,
        error_message=document.error_message,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@app.post("/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(credentials: AuthCredentials, db: Session = Depends(get_db)):
    """Create a user account and start an authenticated session."""
    email = normalize_email(credentials.email)
    if not is_valid_email(email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请输入有效的邮箱地址")
    if len(credentials.password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密码至少需要 8 位")

    db_manager = DatabaseManager(db)
    if db_manager.get_user_by_email(email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该邮箱已注册")

    try:
        user = db_manager.create_user(email, hash_password(credentials.password))
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该邮箱已注册")
    return build_auth_response(user, db_manager)


@app.post("/auth/login", response_model=AuthResponse)
async def login(credentials: AuthCredentials, db: Session = Depends(get_db)):
    """Verify credentials and start an authenticated session."""
    email = normalize_email(credentials.email)
    user = DatabaseManager(db).get_user_by_email(email)
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return build_auth_response(user, DatabaseManager(db))


@app.get("/auth/me", response_model=AuthUser)
async def get_me(current_user: UserAccount = Depends(get_current_user)):
    return AuthUser(id=current_user.id, email=current_user.email)


@app.post("/auth/logout")
async def logout(
    authorization: Optional[str] = Header(default=None),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke the current server-side session."""
    token = authorization.split(" ", 1)[1].strip()
    DatabaseManager(db).delete_auth_session(hash_token(token))
    return {"message": "已退出登录"}


@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    """Main chat endpoint."""
    try:
        session_id = request.session_id or str(uuid.uuid4())

        # Create database manager
        db_manager = DatabaseManager(db)

        # Get response from chatbot
        result = chatbot.get_responses(
            user_message=request.message,
            session_id=session_id,
            db_manager=db_manager,
            user_id=current_user.id,
        )

        return ChatResponse(
            response=result["response"],
            session_id=result["session_id"],
            conversation_id=result["conversation_id"],
            sources=result["sources"],
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing chat request: {str(e)}"
        )


@app.get("/conversation/{session_id}", response_model=ConversationHistory)
async def get_conversation_history(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    """Get conversation history for a session."""
    try:
        db_manager = DatabaseManager(db)
        conversation = db_manager.get_conversation(session_id, current_user.id)

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )

        messages = db_manager.get_conversation_messages(conversation.id)

        # Convert to ChatMessage format
        chat_messages = []
        for message in messages:
            chat_messages.append({
                "role": message.role,
                "content": message.content,
                "timestamp": message.timestamp
            })

        return ConversationHistory(
            conversation_id=conversation.id,
            session_id=conversation.session_id,
            user_id=conversation.user_id,
            messages=chat_messages,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving conversation: {str(e)}"
        )


@app.delete("/conversation/{session_id}")
async def clear_conversation(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    """Clear conversation messages for a session."""
    try:
        db_manager = DatabaseManager(db)
        removed = db_manager.clear_conversation_messages(session_id, current_user.id)
        return {"message": "Conversation cleared successfully", "removed_messages": removed}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error clearing conversation: {str(e)}"
        )


@app.post(
    "/knowledge/documents",
    response_model=KnowledgeDocumentItem,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_knowledge_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    category: str = Form("knowledge"),
    tags: str = Form(""),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    """保存知识文件，并在后台完成解析、切分和向量化。"""
    saved = None
    try:
        saved = await save_upload(file)
        clean_title = (title or Path(saved.filename).stem).strip()
        clean_category = category.strip() or "knowledge"
        if not clean_title:
            raise KnowledgeUploadError("文档标题不能为空")
        if len(clean_title) > 256 or len(clean_category) > 64:
            raise KnowledgeUploadError("标题或分类过长")
        document = DatabaseManager(db).create_knowledge_document(
            doc_id=saved.doc_id,
            title=clean_title,
            filename=saved.filename,
            source=saved.source,
            category=clean_category,
            tags=",".join(normalize_tags(tags)),
            file_size=saved.size,
            created_by=current_user.id,
        )
        background_tasks.add_task(process_knowledge_document, saved.doc_id)
        return knowledge_document_response(document)
    except KnowledgeUploadError as exc:
        if saved:
            resolve_source(saved.source).unlink(missing_ok=True)
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    except Exception as exc:
        if saved:
            resolve_source(saved.source).unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"保存知识文档失败：{exc}",
        )


@app.get("/knowledge/documents", response_model=List[KnowledgeDocumentItem])
async def list_knowledge_documents(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    documents = DatabaseManager(db).get_knowledge_documents()
    return [knowledge_document_response(document) for document in documents]


@app.get(
    "/knowledge/documents/{doc_id}/chunks",
    response_model=List[KnowledgeChunkItem],
)
async def list_knowledge_document_chunks(
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    manager = DatabaseManager(db)
    if not manager.get_knowledge_document(doc_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识文档不存在")
    return [
        KnowledgeChunkItem(
            id=chunk.id,
            section=chunk.section,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
        )
        for chunk in manager.get_document_chunks(doc_id)
    ]


@app.post("/knowledge/documents/{doc_id}/retry", response_model=KnowledgeDocumentItem)
async def retry_knowledge_document(
    doc_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    manager = DatabaseManager(db)
    document = manager.get_knowledge_document(doc_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识文档不存在")
    if not resolve_source(document.source).is_file():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="源文件已不存在，无法重试")
    document = manager.set_knowledge_document_status(doc_id, "pending", error_message=None)
    background_tasks.add_task(process_knowledge_document, doc_id)
    return knowledge_document_response(document)


@app.delete("/knowledge/documents/{doc_id}")
async def remove_knowledge_document(
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    if not DatabaseManager(db).get_knowledge_document(doc_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识文档不存在")
    try:
        delete_knowledge_document(doc_id)
        return {"message": "知识文档已删除", "doc_id": doc_id}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除知识文档失败：{exc}",
        )


@app.post("/knowledge", response_model=KnowledgeBaseItem)
async def add_knowledge_item(
    title: str,
    content: str,
    category: str,
    tags: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    """Add a new item to the knowledge base."""
    try:
        chunks = chatbot.add_knowledge_item(title, content, category, tags or [])

        db_manager = DatabaseManager(db)
        kb_items = db_manager.replace_knowledge_document(chunks)
        kb_item = kb_items[0]
        db_manager.upsert_knowledge_document(
            doc_id=chunks[0].doc_id,
            title=title,
            filename="手工录入",
            source="api",
            category=category,
            tags=",".join(normalize_tags(tags)),
            chunk_count=len(chunks),
            file_size=len(content.encode("utf-8")),
            content_hash=chunks[0].document_hash,
            status="ready",
            created_by=current_user.id,
        )

        return KnowledgeBaseItem(
            id=kb_item.id,
            title=kb_item.title,
            content=kb_item.content,
            category=kb_item.category,
            tags=kb_item.tags.split(",") if kb_item.tags else [],
            created_at=kb_item.created_at,
            updated_at=kb_item.updated_at
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding knowledge item: {str(e)}"
        )


@app.get("/knowledge", response_model=List[KnowledgeBaseItem])
async def get_knowledge_items(
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    """Get knowledge base items."""
    try:
        db_manager = DatabaseManager(db)
        items = db_manager.get_knowledge_items(category)

        result = []
        for item in items:
            result.append(KnowledgeBaseItem(
                id=item.id,
                title=item.title,
                content=item.content,
                category=item.category,
                tags=item.tags.split(",") if item.tags else [],
                created_at=item.created_at,
                updated_at=item.updated_at
            ))

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving knowledge items: {str(e)}"
        )


@app.get("/search")
async def search_knowledge_base(
    query: str,
    k: int = 5,
    category: Optional[str] = None,
    current_user: UserAccount = Depends(get_current_user),
):
    """Search the knowledge base."""
    try:
        results = chatbot.search_knowledge_base(query, k, category)
        return {
            "query": query,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching knowledge base: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.api:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
