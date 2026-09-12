"""Vector store service using ChromaDB for RAG."""
import logging
import hashlib
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings

logger = logging.getLogger(__name__)


class VectorStoreService:
    def __init__(self):
        self._client = None
        self._embedding_fn = None

    def _get_client(self):
        if self._client is None:
            self._client = chromadb.PersistentClient(
                path=settings.chroma_persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        return self._client

    def _get_embedding_fn(self):
        if self._embedding_fn is None:
            try:
                from chromadb.utils import embedding_functions
                self._embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name=settings.default_embedding_model
                )
            except Exception:
                try:
                    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
                    self._embedding_fn = DefaultEmbeddingFunction()
                    logger.info("[VectorStore] Using ChromaDB default (ONNX) embedding function")
                except Exception as e:
                    logger.warning(f"[VectorStore] All embedding functions failed: {e}, using None (ChromaDB default)")
                    self._embedding_fn = None
        return self._embedding_fn

    def get_or_create_collection(self, session_id: str):
        client = self._get_client()
        collection_name = f"research_{session_id[:16].replace('-', '_')}"
        try:
            return client.get_or_create_collection(
                name=collection_name,
                embedding_function=self._get_embedding_fn(),
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as e:
            logger.error(f"[VectorStore] Collection error: {e}")
            raise

    def add_sources(self, session_id: str, sources: List[dict]) -> int:
        """Chunk and index source content into ChromaDB."""
        collection = self.get_or_create_collection(session_id)
        documents, metadatas, ids = [], [], []

        for source in sources:
            content = source.get("content", "")
            if not content:
                continue
            chunks = _chunk_text(content, chunk_size=400, overlap=50)
            for i, chunk in enumerate(chunks):
                chunk_id = f"{source['source_id']}_chunk_{i}"
                documents.append(chunk)
                metadatas.append({
                    "source_id": source["source_id"],
                    "url": source["url"],
                    "title": source["title"][:200],
                    "chunk_index": i,
                    "total_score": float(source.get("total_score", 5.0)),
                })
                ids.append(chunk_id)

        if documents:
            try:
                collection.add(documents=documents, metadatas=metadatas, ids=ids)
                logger.info(f"[VectorStore] Indexed {len(documents)} chunks for session {session_id[:8]}")
            except Exception as e:
                logger.error(f"[VectorStore] Add error: {e}")
        return len(documents)

    def retrieve(
        self,
        session_id: str,
        query: str,
        n_results: int = 8,
        source_filter: Optional[List[str]] = None,
    ) -> List[dict]:
        """Retrieve relevant chunks for a query."""
        collection = self.get_or_create_collection(session_id)
        try:
            where = None
            if source_filter:
                where = {"source_id": {"$in": source_filter}}

            count = collection.count()
            if count == 0:
                return []

            results = collection.query(
                query_texts=[query],
                n_results=min(n_results, count),
                where=where,
                include=["documents", "metadatas", "distances"],
            )
            chunks = []
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                chunks.append({
                    "content": doc,
                    "source_id": meta.get("source_id"),
                    "url": meta.get("url"),
                    "title": meta.get("title"),
                    "chunk_index": meta.get("chunk_index"),
                    "relevance_score": 1 - dist,  # cosine similarity
                })
            return chunks
        except Exception as e:
            logger.error(f"[VectorStore] Retrieve error: {e}")
            return []

    def delete_collection(self, session_id: str):
        try:
            client = self._get_client()
            collection_name = f"research_{session_id[:16].replace('-', '_')}"
            client.delete_collection(collection_name)
        except Exception:
            pass


def _chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> List[str]:
    """Split text into overlapping chunks by word count."""
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        if len(chunk.strip()) > 20:
            chunks.append(chunk)
        start = end - overlap
        if start >= len(words):
            break
    return chunks


vector_store = VectorStoreService()
