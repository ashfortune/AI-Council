from langchain_postgres import PGVector
from langchain_ollama import OllamaEmbeddings
from app.core.config import settings
from langchain_core.documents import Document

class VectorService:
    def __init__(self):
        # M1 환경에서 빠른 임베딩을 위해 llama3.2:3b 혹은 전용 임베딩 모델 사용 가능
        self.embeddings = OllamaEmbeddings(
            model="llama3.2:3b",
            base_url=settings.OLLAMA_BASE_URL
        )
        self.connection_string = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        self.collection_name = "decision_criteria"
        
        # PGVector 초기화 (테이블 자동 생성 지원)
        try:
            # 확장 기능 활성화 확인 (psycopg2 사용)
            import psycopg2
            conn = psycopg2.connect(self.connection_string)
            cur = conn.cursor()
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"Vector extension check failed: {e}")

        self.vector_store = PGVector(
            embeddings=self.embeddings,
            collection_name=self.collection_name,
            connection=self.connection_string,
            use_jsonb=True,
        )

    async def save_decision(self, topic: str, content: str, metadata: dict = None):
        """판단 기준 및 결과를 벡터 DB에 저장"""
        doc = Document(
            page_content=f"주제: {topic}\n내용: {content}",
            metadata=metadata or {}
        )
        # 동기 방식으로 변경하여 psycopg2 호환성 확보
        self.vector_store.add_documents([doc])

    async def search_similar_decisions(self, query: str, k: int = 3):
        """유사한 과거 판단 사례 검색"""
        # 동기 방식으로 변경하여 psycopg2 호환성 확보
        docs = self.vector_store.similarity_search(query, k=k)
        return docs

vector_service = VectorService()
