"""RAG Pipeline: document ingestion, chunking, embedding, retrieval, context injection."""

import hashlib
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.database import Base
from src.services.chat_service import EmbeddingService


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(256), index=True, nullable=False)
    content = Column(Text, nullable=False)
    source = Column(String(256), nullable=True)
    content_hash = Column(String(64), index=True)
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True))
    metadata_info = Column(JSON, nullable=True)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (Index("ix_chunks_doc_id", "document_id"),)

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, index=True, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=True)
    token_count = Column(Integer, default=0)


class RAGPipeline:
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64, top_k: int = 5):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.top_k = top_k

    def _chunk_text(self, text: str) -> list[str]:
        words = text.split()
        chunks: list[str] = []
        i = 0
        while i < len(words):
            chunk = " ".join(words[i : i + self.chunk_size])
            chunks.append(chunk)
            i += self.chunk_size - self.chunk_overlap
        return chunks

    async def ingest_text(
        self, db: AsyncSession, name: str, content: str, source: str = ""
    ) -> Document:
        import datetime
        from datetime import timezone as tz

        content_hash = hashlib.sha256(content.encode()).hexdigest()

        existing = await db.execute(
            select(Document).where(Document.content_hash == content_hash)
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Document already ingested: {name}")

        doc = Document(
            name=name,
            content=content,
            source=source,
            content_hash=content_hash,
            chunk_count=0,
            created_at=datetime.datetime.now(tz.utc),
        )
        db.add(doc)
        await db.flush()

        chunks = self._chunk_text(content)
        for i, chunk_text in enumerate(chunks):
            emb = EmbeddingService.create_embeddings_sync(chunk_text[:1024])
            chunk = DocumentChunk(
                document_id=doc.id,
                chunk_index=i,
                content=chunk_text,
                embedding=emb,
                token_count=len(chunk_text.split()),
            )
            db.add(chunk)

        doc.chunk_count = len(chunks)
        await db.flush()
        return doc

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = (sum(x * x for x in a)) ** 0.5
        nb = (sum(y * y for y in b)) ** 0.5
        return dot / (na * nb) if na and nb else 0.0

    async def retrieve(
        self, db: AsyncSession, query: str, top_k: int = 0
    ) -> list[dict]:
        k = top_k or self.top_k
        query_emb = EmbeddingService.create_embeddings_sync(query)

        result = await db.execute(select(DocumentChunk))
        chunks = result.scalars().all()

        scored: list[tuple[float, dict]] = []
        for chunk in chunks:
            if chunk.embedding:
                score = self._cosine(query_emb, chunk.embedding)
                if score > 0.2:
                    scored.append(
                        (
                            score,
                            {
                                "chunk_id": chunk.id,
                                "document_id": chunk.document_id,
                                "content": chunk.content,
                                "score": round(score, 4),
                            },
                        )
                    )

        scored.sort(key=lambda x: -x[0])
        return [s[1] for s in scored[:k]]

    async def query(
        self, db: AsyncSession, question: str, top_k: int = 0
    ) -> dict[str, Any]:
        context_chunks = await self.retrieve(db, question, top_k)
        context_text = "\n\n---\n\n".join(
            f"[Source {c['document_id']}] {c['content']}" for c in context_chunks
        )

        prompt = (
            f"Answer the question based on the following context.\n\n"
            f"Context:\n{context_text}\n\n"
            f"Question: {question}\n\n"
            f"Answer:"
        )
        return {"prompt": prompt, "contexts": context_chunks}

    async def list_documents(self, db: AsyncSession) -> list[dict]:
        result = await db.execute(select(Document).order_by(Document.id.desc()))
        docs = result.scalars().all()
        return [
            {
                "id": d.id,
                "name": d.name,
                "source": d.source,
                "chunk_count": d.chunk_count,
            }
            for d in docs
        ]

    async def delete_document(self, db: AsyncSession, doc_id: int) -> int:
        chunks_deleted = await db.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == doc_id)
        )
        for c in chunks_deleted.scalars().all():
            await db.delete(c)

        doc = await db.execute(select(Document).where(Document.id == doc_id))
        doc_obj = doc.scalar_one_or_none()
        if doc_obj:
            await db.delete(doc_obj)

        await db.flush()
        return doc_id


rag_pipeline = RAGPipeline()
