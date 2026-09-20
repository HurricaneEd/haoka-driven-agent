import uuid
from typing import List, Dict, Any, Optional

from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.tools import Tool, create_schema_from_function

from app.database import DatabaseManager
from app.knowledge_base import get_knowledge_base
from app.rag.schemas import RagChunk
from config import settings

# Agent 系统提示词（第 9 课：Agent 统一入口，自己决定调用哪个工具）
AGENT_SYSTEM_PROMPT = """你是电商客服助手，负责根据知识库回答套餐、激活、退卡和资费等问题。

根据用户请求判断调用哪个工具：
- 套餐内容、流量、激活流程、退卡政策、资费说明等知识类问题 → search_knowledge（查客服知识库）
规则：
1. 以工具返回的信息为事实依据，组织简洁、友好、准确的中文回答，不编造工具未提供的信息
2. search_knowledge 未命中时，如实告知用户知识库暂无相关内容
3. 不要重复调用同一工具；必要时可连续调用多个工具
4. 若无法确定用户需求，主动追问澄清
5. search_knowledge 返回“需要确认商品”时，只询问用户具体是哪款商品，不要猜测，也不要混合多个商品作答
6. 用户要求修改密码时，引导其前往“个人信息”页面，不要声称已代为修改或发送链接"""


class CustomerSupportChatbot:
    """客服机器人：Agent 统一入口（第 9 课实践5）。

    知识库检索是 Agent 的事实来源；会话上下文按 session_id 从数据库注入。
    """
    def __init__(self):
        # Initialize LLM
        self.llm = ChatOpenAI(
            model=settings.model_name,
            api_key=settings.deepseek_api_key,
            base_url=settings.openai_api_base,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens
        )
        # Initialize knowledge base (shared singleton)
        self.kb_manager = get_knowledge_base()

        # 每次请求的来源缓冲（Agent 统一入口下，search_knowledge 工具回写此处）
        self._last_sources: List[Dict[str, str]] = []

        # 知识库工具：绑定实例方法（检索策略由 RetrievalService 统一管理）。
        # 1.x 的 Tool() 不会自动推断函数签名，需用 create_schema_from_function
        # 显式生成参数 schema（跳过 self，只留 query）。
        knowledge_tool = Tool(
            name="search_knowledge",
            func=self._search_knowledge,
            description="当用户询问套餐内容、流量、激活流程、退卡政策、资费说明等知识类问题时使用。参数为要查询的问题。",
            args_schema=create_schema_from_function("SearchKnowledgeArgs", self._search_knowledge),
        )

        # ★ Agent 统一入口（第 9 课实践5）：知识库也是工具，LLM 自己决定路由
        self.agent = create_agent(
            model=self.llm,
            tools=[knowledge_tool],
            system_prompt=AGENT_SYSTEM_PROMPT,
            debug=settings.debug,
        )

    # ── Agent 工具 ────────────────────────────────────────────────

    def _search_knowledge(self, query: str) -> str:
        """查询客服知识库。参数为要查询的问题。返回自包含的检索片段。

        Observation 会被原样喂回给 LLM 组织回答，所以文本要自包含；
        同时把结构化来源写入 self._last_sources，供 get_responses 返回前端。
        """
        docs = self.kb_manager.retrieve(query, k=6)
        if docs and docs[0].metadata.get("clarification_required"):
            self._last_sources = []
            return docs[0].page_content
        sources: List[Dict[str, str]] = []
        parts: List[str] = []
        for doc in docs:
            title = doc.metadata.get("title", "未知")
            category = doc.metadata.get("category", "未知")
            content = doc.page_content
            preview = content[:300] + ("..." if len(content) > 300 else "")
            sources.append({"title": title, "category": category, "content": preview})
            parts.append(f"[{title}]\n{content[:6000]}")
        self._last_sources = sources
        if not parts:
            return "知识库中没有找到相关内容。"
        return "\n\n".join(parts)

    # ── 主入口 ────────────────────────────────────────────────────

    def get_responses(
        self,
        user_message: str,
        session_id: str,
        db_manager: DatabaseManager,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Agent 统一入口：每个请求都进 Agent，由 LLM 决定查知识库还是执行动作。"""
        try:
            # Get or create conversation
            conversation = db_manager.get_conversation(session_id, user_id)
            if not conversation:
                conversation = db_manager.create_conversation(session_id, user_id)
            # Add user message to database
            db_manager.add_message(conversation.id, "user", user_message)

            # 每次请求重置来源缓冲
            self._last_sources = []

            # 第 8 课成果：数据库即真相，按 session 隔离。
            # Agent 也带上最近对话作为上下文（末尾即本条用户消息）。
            messages = db_manager.get_conversation_messages(conversation.id)
            recent = messages[-20:]  # 最近 10 轮，避免撑爆上下文
            history = [{"role": m.role, "content": m.content} for m in recent]

            # ★ Agent 执行；recursion_limit 是循环保险丝（对应 0.1.0 的 max_iterations）
            result = self.agent.invoke(
                {"messages": history},
                config={"recursion_limit": 15},
            )
            response_text = result["messages"][-1].content

            # Add assistant response to database
            db_manager.add_message(conversation.id, "assistant", response_text)

            # 工具调用审计（等价 0.1.0 的 intermediate_steps）
            for m in result["messages"]:
                if getattr(m, "tool_calls", None):
                    for tc in m.tool_calls:
                        print(f"  → Agent 调用了 {tc['name']}({tc.get('args')})")

            return {
                "response": response_text,
                "session_id": session_id,
                "conversation_id": conversation.id,
                "sources": self._last_sources,
            }
        except Exception as e:
            print(f"Error in chatbot response: {e}")
            return {
                "response": "抱歉，我遇到技术问题，请稍后再试或联系人工。",
                "session_id": session_id,
                "conversation_id": "",
                "sources": [],
            }

    def get_conversation_history(self, session_id: str, db_manager: DatabaseManager) -> List[Dict[str, Any]]:
        """Get conversation history for a session."""
        conversation = db_manager.get_conversation(session_id)
        if not conversation:
            return []
        messages = db_manager.get_conversation_messages(conversation.id)

        history = []
        for message in messages:
            history.append({
                "role": message.role,
                "content": message.content,
                "timestamp": message.timestamp.isoformat()
            })

        return history

    def clear_conversation(self, session_id: str, db_manager: DatabaseManager) -> int:
        """清空某会话的对话记录（数据库即真相，按 session 隔离）。返回删除条数。"""
        return db_manager.clear_conversation_messages(session_id)

    def add_knowledge_item(self, title: str, content: str, category: str = "product",
                           tags: List[str] = None) -> List[RagChunk]:
        """通过统一摄入管线添加一份手工知识文档。"""
        doc_id = f"manual-{uuid.uuid4().hex[:8]}"
        prepared = self.kb_manager.prepare_text(
            doc_id=doc_id,
            title=title,
            content=content,
            category=category,
            tags=tags or (),
            source="api",
        )
        self.kb_manager.ingest(prepared)
        return list(prepared.chunks)

    def search_knowledge_base(self, query: str, k: int = 5, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search the knowledge base."""
        return self.kb_manager.search(query, k, category)


# Global chatbot instance
chatbot = CustomerSupportChatbot()
