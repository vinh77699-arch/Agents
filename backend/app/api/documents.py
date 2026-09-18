"""Personal document library: upload PDF/TXT, index to ChromaDB, list, delete."""
import io
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core import database as db
from app.core.deps import require_user
from app.services.vectorstore import vector_store

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_TYPES = {
    "application/pdf", "text/plain",
    "text/markdown", "application/octet-stream",
}


def _extract_text(filename: str, data: bytes) -> str:
    if filename.lower().endswith(".pdf"):
        try:
            import pdfplumber, io as _io
            text_parts = []
            with pdfplumber.open(_io.BytesIO(data)) as pdf:
                for page in pdf.pages[:30]:
                    t = page.extract_text()
                    if t:
                        text_parts.append(t)
            return "\n".join(text_parts)[:80_000]
        except Exception as e:
            logger.warning(f"[Documents] PDF extraction error: {e}")
            return ""
    return data.decode("utf-8", errors="replace")[:80_000]


@router.post("/documents/upload", tags=["documents"])
async def upload_document(
    file: UploadFile = File(...),
    user: dict = Depends(require_user),
):
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File quá lớn (tối đa 10MB)")

    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File quá lớn (tối đa 10MB)")

    text_content = _extract_text(file.filename or "", data)
    if not text_content.strip():
        raise HTTPException(status_code=422, detail="Không thể trích xuất nội dung từ file")

    doc_id = str(uuid.uuid4())
    user_id = user["id"]
    collection_name = f"userdoc_{user_id[:16]}_{doc_id[:8]}"
    now = datetime.now(timezone.utc).isoformat()

    # Index into ChromaDB
    source_dict = {
        "source_id": doc_id[:8],
        "url": f"local://{file.filename}",
        "title": file.filename or "Tài liệu",
        "content": text_content,
        "total_score": 8.0,
    }
    try:
        await vector_store.add_sources(collection_name, [source_dict])
    except Exception as e:
        logger.error(f"[Documents] ChromaDB indexing error: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi lập chỉ mục: {e}")

    await db.create_document(
        id_=doc_id,
        user_id=user_id,
        filename=file.filename or "document",
        content_type=file.content_type or "text/plain",
        text_content=text_content[:5000],
        chroma_collection=collection_name,
        file_size=len(data),
        created_at=now,
    )

    logger.info(f"[Documents] Uploaded {file.filename} ({len(data)} bytes) for user {user_id}")
    return {
        "document_id": doc_id,
        "filename": file.filename,
        "file_size": len(data),
        "text_length": len(text_content),
        "chroma_collection": collection_name,
        "created_at": now,
        "message": "Tài liệu đã được lập chỉ mục thành công",
    }


@router.get("/documents", tags=["documents"])
async def list_documents(user: dict = Depends(require_user)):
    docs = await db.list_documents(user["id"])
    return {"documents": docs, "total": len(docs)}


@router.delete("/documents/{doc_id}", tags=["documents"])
async def delete_document(doc_id: str, user: dict = Depends(require_user)):
    # Get collection name first
    import asyncio, functools, sqlite3
    from app.core.config import settings

    def _get_doc():
        conn = sqlite3.connect(settings.sqlite_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM user_documents WHERE id=? AND user_id=?",
                           (doc_id, user["id"])).fetchone()
        conn.close()
        return dict(row) if row else None

    doc = await asyncio.get_event_loop().run_in_executor(None, _get_doc)
    if not doc:
        raise HTTPException(status_code=404, detail="Tài liệu không tồn tại")

    try:
        await vector_store.delete_collection(doc["chroma_collection"])
    except Exception:
        pass

    await db.delete_document(doc_id, user["id"])
    return {"message": "Đã xoá tài liệu"}
