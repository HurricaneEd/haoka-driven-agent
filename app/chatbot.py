from langchain_openai import ChatOpenAI
from langchain_classic.memory import ConversationBufferWindowMemory
from langchain_classic.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.knowledge_base import get_knowledge_base
from config import settings

class CustomerSupportChatbot:
    """Main chatbot class with RAG capabilities."""
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
        # Initialize conversation memory
        self.memory = ConversationBufferWindowMemory(
            k=10,  # Keep last 10 exchanges
            return_messages=True,
            memory_key="chat_history",
            input_key="question",
            output_key="answer"
        )
        # Create system prompt
        self.system_prompt = """You are a helpful customer support assistant for an e-commerce company. 
        Your role is to help customers with their questions about products, orders, returns, shipping, payments, and account issues.
        
        Guidelines:
        1. Always be polite, professional, and helpful
        2. Use the provided knowledge base to give accurate information
        3. If you don't know something, say so and offer to connect them with human support
        4. Keep responses concise but informative
        5. Ask clarifying questions when needed
        6. Provide step-by-step instructions when appropriate
        
        Use the following context to answer the customer's question:"""
        
        # Create prompt template
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt + "\n\nContext:\n{context}\n\n"),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}")
        ])
        self.retrieval_chain = ConversationalRetrievalChain.from_llm(
            llm=self.llm,
            retriever=self.kb_manager.vectorstore.as_retriever(
                search_type="similarity",
                search_kwargs={"k": 3}
            ),
            memory=self.memory,
            return_source_documents=True,
            verbose=settings.debug
        )
        

