"""FastAPI routes: REST endpoints + SSE streaming."""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core import database as db
from app.core.config import get_llm_client
from app.core.deps import get_current_user, require_admin
from app.core.pipeline import run_research_pipeline, run_research_pipeline_sync

logger = logging.getLogger(__name__)
router = APIRouter()


class ResearchRequest(BaseModel):
    topic: str = Field(..., min_length=5, max_length=500)
    session_id: Optional[str] = None


class ResearchResponse(BaseModel):
    session_id: str
    status: str
    report: Optional[str] = None
    message: Optional[str] = None


class TranslateRequest(BaseModel):
    report: str = Field(..., description="Markdown report to translate")
    topic: str = Field(default="")


class TranslateResponse(BaseModel):
    translated_report: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ─── SSE pipeline endpoint ────────────────────────────────────────────────────

@router.post("/research/stream")
async def stream_research_post(
    request: ResearchRequest,
    current_user: Optional[dict] = Depends(get_current_user),
):
    """POST SSE endpoint: run pipeline and stream progress."""
    session_id = request.session_id or str(uuid.uuid4())
    user_id = current_user["id"] if current_user else None
    created_at = _now_iso()

    # Quota check for authenticated users
    if user_id:
        allowed = await db.check_and_increment_quota(user_id, _today_str())
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Đã đạt hạn mức {current_user['daily_quota']} báo cáo/ngày. Thử lại vào ngày mai.",
            )

    # Create pending session record
    await db.upsert_session(
        id_=session_id, user_id=user_id, topic=request.topic,
        status="running", created_at=created_at,
    )

    async def event_generator():
        try:
            async for event in run_research_pipeline(request.topic, session_id):
                serialized = _serialize_event(event)
                data = json.dumps(serialized, ensure_ascii=False, default=str)
                yield f"data: {data}\n\n"

                if event.get("type") == "complete":
                    report = event.get("report", "")
                    bib = event.get("bibliography", [])
                    sources = event.get("all_sources", {})
                    word_count = len(report.split())
                    await db.upsert_session(
                        id_=session_id, user_id=user_id, topic=request.topic,
                        status="completed", report=report, bibliography=bib,
                        all_sources=sources, word_count=word_count,
                        sources_count=len(sources), created_at=created_at,
                        completed_at=_now_iso(),
                    )

        except Exception as e:
            logger.error(f"[SSE] Error: {e}", exc_info=True)
            error_event = json.dumps({"type": "error", "message": str(e)})
            yield f"data: {error_event}\n\n"
            await db.upsert_session(
                id_=session_id, user_id=user_id, topic=request.topic,
                status="error", created_at=created_at, completed_at=_now_iso(),
            )
        yield 'data: {"type": "done"}\n\n'

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# ─── Session endpoints ────────────────────────────────────────────────────────

@router.get("/research/sessions", tags=["sessions"])
async def get_sessions(
    limit: int = 20,
    offset: int = 0,
    current_user: Optional[dict] = Depends(get_current_user),
):
    """List sessions: own sessions for users, all sessions for admins."""
    if current_user and current_user.get("role") == "admin":
        sessions = await db.list_sessions(user_id=None, limit=limit, offset=offset)
    elif current_user:
        sessions = await db.list_sessions(user_id=current_user["id"], limit=limit, offset=offset)
    else:
        sessions = await db.list_sessions(user_id=None, limit=limit, offset=offset)
    return {"sessions": sessions, "total": len(sessions)}


@router.get("/research/{session_id}", response_model=ResearchResponse, tags=["sessions"])
async def get_research_status(
    session_id: str,
    current_user: Optional[dict] = Depends(get_current_user),
):
    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session không tồn tại")
    return ResearchResponse(
        session_id=session_id,
        status=session.get("status", "unknown"),
        report=session.get("report"),
        message=None,
    )


@router.get("/research/{session_id}/report", tags=["sessions"])
async def get_report(session_id: str, current_user: Optional[dict] = Depends(get_current_user)):
    session = await db.get_session(session_id)
    if not session or session.get("status") != "completed":
        raise HTTPException(status_code=404, detail="Báo cáo chưa sẵn sàng")
    return {
        "session_id": session_id,
        "topic": session["topic"],
        "report": session["report"],
        "bibliography": session["bibliography"],
        "all_sources": session["all_sources"],
        "word_count": session["word_count"],
        "sources_count": session["sources_count"],
        "created_at": session["created_at"],
        "completed_at": session["completed_at"],
    }


@router.delete("/research/{session_id}", tags=["sessions"])
async def delete_session(
    session_id: str,
    current_user: dict = Depends(require_admin),
):
    import asyncio, functools, sqlite3
    from app.core.config import settings

    def _del():
        conn = sqlite3.connect(settings.sqlite_path)
        conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        conn.commit()
        conn.close()

    await asyncio.get_event_loop().run_in_executor(None, _del)
    return {"message": "Đã xoá session"}


# ─── Translation ──────────────────────────────────────────────────────────────

@router.post("/research/translate", response_model=TranslateResponse)
async def translate_report(request: TranslateRequest):
    if not request.report.strip():
        raise HTTPException(status_code=400, detail="Nội dung báo cáo trống")

    llm = get_llm_client()
    from langchain_core.messages import HumanMessage, SystemMessage

    system_prompt = """Bạn là chuyên gia dịch thuật học thuật Anh-Việt.
Dịch toàn bộ báo cáo nghiên cứu sang tiếng Việt chuẩn mực, học thuật.

Quy tắc:
- Giữ nguyên toàn bộ cú pháp Markdown (##, **bold**, bảng, danh sách, liên kết)
- Giữ nguyên URL, chỉ dịch text hiển thị
- Thuật ngữ kỹ thuật: dịch + giữ tiếng Anh trong ngoặc, vd: "học máy (machine learning)"
- Giữ nguyên tên riêng, tên tổ chức, tên sản phẩm
- Không thêm, không bỏ bớt nội dung"""

    report = request.report
    if len(report) > 6000:
        chunks = _split_markdown_chunks(report, max_chars=5500)
        translated_chunks = []
        for i, chunk in enumerate(chunks):
            resp = await llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Dịch phần {i+1}/{len(chunks)} sang tiếng Việt. Chủ đề: {request.topic}\n\n{chunk}"),
            ])
            translated_chunks.append(resp.content.strip())
        translated = "\n\n".join(translated_chunks)
    else:
        resp = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Dịch sang tiếng Việt. Chủ đề: {request.topic}\n\n{report}"),
        ])
        translated = resp.content.strip()

    return TranslateResponse(translated_report=translated)


# ─── Admin stats ──────────────────────────────────────────────────────────────

@router.get("/admin/stats", tags=["admin"])
async def admin_stats(admin: dict = Depends(require_admin)):
    import asyncio, sqlite3, functools
    from app.core.config import settings

    def _stats():
        conn = sqlite3.connect(settings.sqlite_path)
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        completed = conn.execute("SELECT COUNT(*) FROM sessions WHERE status='completed'").fetchone()[0]
        today = _today_str()
        today_sessions = conn.execute("SELECT COUNT(*) FROM sessions WHERE created_at LIKE ?", (f"{today}%",)).fetchone()[0]
        conn.close()
        return {
            "total_users": total_users,
            "total_sessions": total_sessions,
            "completed_sessions": completed,
            "today_sessions": today_sessions,
        }

    return await asyncio.get_event_loop().run_in_executor(None, _stats)


# ─── Health ───────────────────────────────────────────────────────────────────

@router.get("/health")
async def health_check():
    return {"status": "ok", "version": "2.0.0"}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _split_markdown_chunks(text: str, max_chars: int = 5500) -> list[str]:
    import re
    sections = re.split(r'(?=^## )', text, flags=re.MULTILINE)
    chunks, current = [], ""
    for section in sections:
        if len(current) + len(section) > max_chars and current:
            chunks.append(current.strip())
            current = section
        else:
            current += section
    if current.strip():
        chunks.append(current.strip())
    return chunks if chunks else [text]


def _serialize_event(event: dict) -> dict:
    def _val(v):
        if hasattr(v, '__dict__'):
            return v.__dict__
        if hasattr(v, 'value'):
            return v.value
        return v

    result = {}
    for k, val in event.items():
        if isinstance(val, list):
            result[k] = [_val(i) for i in val]
        elif isinstance(val, dict):
            result[k] = {dk: _val(dv) for dk, dv in val.items()}
        else:
            result[k] = _val(val)
    return result
