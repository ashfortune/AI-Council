from langchain_postgres import PGVector
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.core.config import settings
from langchain_core.documents import Document

class VectorService:
    def __init__(self):
        # 로컬 Ollama 미설치 환경에서도 안정적으로 동작하도록 Google GenAI 공식 임베딩 모델 사용
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004"
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
        
        try:
            self.vector_store.create_tables_if_not_exists()
        except Exception as e:
            print(f"PGVector create_tables check: {e}")

    async def save_decision(self, topic: str, content: str, metadata: dict = None):
        """판단 기준 및 결과를 벡터 DB에 저장"""
        try:
            doc = Document(
                page_content=f"주제: {topic}\n내용: {content}",
                metadata=metadata or {}
            )
            # 동기 방식으로 변경하여 psycopg2 호환성 확보
            self.vector_store.add_documents([doc])
            print(f"Successfully saved decision to PGVector DB for topic: {topic}")
        except Exception as e:
            print(f"ERROR saving decision to PGVector DB: {e}")

    async def search_similar_decisions(self, query: str, k: int = 3):
        """유사한 과거 판단 사례 검색"""
        try:
            docs = self.vector_store.similarity_search(query, k=k)
            return docs
        except Exception as e:
            print(f"Similarity search failed (table may not exist yet): {e}")
            return []

vector_service = VectorService()
