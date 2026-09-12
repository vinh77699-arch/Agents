"""FastAPI routes: REST endpoints + SSE streaming."""
import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.pipeline import run_research_pipeline, run_research_pipeline_sync
from app.core.config import get_llm_client

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory session store (use Redis/DB in production)
_sessions: dict = {}


class ResearchRequest(BaseModel):
    topic: str = Field(..., min_length=5, max_length=500, description="Research topic or question")
    session_id: Optional[str] = None


class ResearchResponse(BaseModel):
    session_id: str
    status: str
    report: Optional[str] = None
    message: Optional[str] = None


class TranslateRequest(BaseModel):
    report: str = Field(..., description="Markdown report to translate")
    topic: str = Field(default="", description="Research topic for context")


class TranslateResponse(BaseModel):
    translated_report: str


@router.post("/research/start", response_model=ResearchResponse)
async def start_research(request: ResearchRequest, background_tasks: BackgroundTasks):
    """Start a research session (returns session_id immediately, runs in background)."""
    session_id = request.session_id or str(uuid.uuid4())
    _sessions[session_id] = {"status": "pending", "topic": request.topic}

    async def run_and_store():
        try:
            _sessions[session_id]["status"] = "running"
            final = await run_research_pipeline_sync(request.topic, session_id)
            _sessions[session_id] = {
                "status": "completed",
                "report": final.get("final_report", ""),
                "bibliography": final.get("bibliography", []),
                "all_sources": {k: v for k, v in (final.get("all_sources") or {}).items()},
                "topic": request.topic,
            }
        except Exception as e:
            logger.error(f"[Routes] Research error: {e}")
            _sessions[session_id] = {"status": "error", "error": str(e), "topic": request.topic}

    background_tasks.add_task(run_and_store)
    return ResearchResponse(session_id=session_id, status="started", message="Research started")


@router.get("/research/{session_id}/stream")
async def stream_research(topic: str, session_id: Optional[str] = None):
    """SSE endpoint: stream research progress in real time."""
    sid = session_id or str(uuid.uuid4())

    async def event_generator():
        try:
            async for event in run_research_pipeline(topic, sid):
                data = json.dumps(event, ensure_ascii=False, default=str)
                yield f"data: {data}\n\n"
        except Exception as e:
            error_event = json.dumps({"type": "error", "message": str(e)})
            yield f"data: {error_event}\n\n"
        yield "data: {\"type\": \"done\"}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )


@router.post("/research/stream")
async def stream_research_post(request: ResearchRequest):
    """POST SSE endpoint for streaming research."""
    session_id = request.session_id or str(uuid.uuid4())
    _sessions[session_id] = {"status": "running", "topic": request.topic}

    async def event_generator():
        try:
            async for event in run_research_pipeline(request.topic, session_id):
                serialized = _serialize_event(event)
                data = json.dumps(serialized, ensure_ascii=False, default=str)
                yield f"data: {data}\n\n"
                if event.get("type") == "complete":
                    _sessions[session_id] = {
                        "status": "completed",
                        "topic": request.topic,
                        "report": event.get("report", ""),
                        "bibliography": event.get("bibliography", []),
                        "all_sources": event.get("all_sources", {}),
                    }
        except Exception as e:
            logger.error(f"[SSE] Error: {e}", exc_info=True)
            error_event = json.dumps({"type": "error", "message": str(e)})
            yield f"data: {error_event}\n\n"
            _sessions[session_id] = {"status": "error", "error": str(e)}
        yield "data: {\"type\": \"done\"}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )


@router.get("/research/{session_id}", response_model=ResearchResponse)
async def get_research_status(session_id: str):
    """Get status and results of a research session."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return ResearchResponse(
        session_id=session_id,
        status=session.get("status", "unknown"),
        report=session.get("report"),
        message=session.get("error"),
    )


@router.post("/research/translate", response_model=TranslateResponse)
async def translate_report(request: TranslateRequest):
    """Translate a research report from English to Vietnamese."""
    if not request.report.strip():
        raise HTTPException(status_code=400, detail="Report content is empty")

    llm = get_llm_client()

    from langchain_core.messages import HumanMessage, SystemMessage

    system_prompt = """Bạn là một chuyên gia dịch thuật học thuật Anh-Việt.
Nhiệm vụ: Dịch toàn bộ báo cáo nghiên cứu sang tiếng Việt chuẩn mực, học thuật.

Quy tắc bắt buộc:
- Giữ nguyên toàn bộ cú pháp Markdown (##, **bold**, *italic*, bảng, danh sách, liên kết, khối code)
- Giữ nguyên tất cả URL và liên kết, chỉ dịch phần text hiển thị
- Dịch tất cả tiêu đề, đoạn văn, chú thích sang tiếng Việt học thuật
- Các thuật ngữ kỹ thuật chuyên ngành: dịch + giữ nguyên tiếng Anh trong ngoặc, ví dụ: "học máy (machine learning)"
- Giữ nguyên tên riêng, tên tổ chức, tên sản phẩm
- Không thêm, không bỏ bớt nội dung so với bản gốc
- Chất lượng ngôn ngữ: văn phong học thuật, rõ ràng, mạch lạc"""

    user_prompt = f"""Dịch toàn bộ báo cáo nghiên cứu sau sang tiếng Việt. Chủ đề: {request.topic}

{request.report}"""

    # Split into chunks if report is very long (>6000 chars) to avoid token limits
    report = request.report
    if len(report) > 6000:
        chunks = _split_markdown_chunks(report, max_chars=5500)
        translated_chunks = []
        for i, chunk in enumerate(chunks):
            chunk_prompt = f"""Dịch phần {i+1}/{len(chunks)} của báo cáo sang tiếng Việt. Chủ đề: {request.topic}

{chunk}"""
            response = await llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=chunk_prompt),
            ])
            translated_chunks.append(response.content.strip())
        translated = "\n\n".join(translated_chunks)
    else:
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])
        translated = response.content.strip()

    return TranslateResponse(translated_report=translated)


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "1.0.0"}


def _split_markdown_chunks(text: str, max_chars: int = 5500) -> list[str]:
    """Split markdown by section headers to stay within token limits."""
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
    """Ensure event is JSON-serializable."""
    def serialize_value(v):
        if hasattr(v, '__dict__'):
            return v.__dict__
        if hasattr(v, 'value'):
            return v.value
        return v

    result = {}
    for k, val in event.items():
        if isinstance(val, list):
            result[k] = [serialize_value(item) for item in val]
        elif isinstance(val, dict):
            result[k] = {dk: serialize_value(dv) for dk, dv in val.items()}
        else:
            result[k] = serialize_value(val)
    return result
