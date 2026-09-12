"""Synthesis Agent: RAG-based content generation with citation tracking."""
import asyncio
import json
import logging
from typing import List, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import get_llm_client
from app.core.state import ResearchState, ProgressUpdate, AgentStatus
from app.services.vectorstore import vector_store

logger = logging.getLogger(__name__)

SYNTHESIS_SYSTEM = """You are a meticulous academic writer. Write a well-structured section for a research report.

RULES:
1. Only use information from the provided source chunks — do NOT invent facts
2. Every factual claim MUST include a citation in format [src_id]
3. Use multiple sources per paragraph when available
4. Write in clear, academic prose (not bullet points)
5. If sources disagree, note the disagreement explicitly
6. If evidence is insufficient, state that clearly

CITATION FORMAT: After each sentence with a fact, append [source_id] in brackets.
Example: "The global temperature has risen by 1.1°C since pre-industrial times [a3f2b1]."

Respond with valid JSON only:
{
  "content": "<the written section with [source_id] citations>",
  "key_claims": ["<claim 1> [source_id]", "<claim 2> [source_id]"],
  "sources_used": ["source_id_1", "source_id_2"]
}"""


async def run_synthesizer(state: ResearchState) -> ResearchState:
    """RAG-based synthesis for each sub-question."""
    logger.info("[Synthesizer] Starting RAG synthesis")

    progress = list(state.get("progress", []))
    progress.append(ProgressUpdate(
        agent="synthesizer",
        status=AgentStatus.RUNNING,
        message="Đang tổng hợp nội dung với trích dẫn..."
    ))

    session_id = state.get("session_id", "default")
    credible_sources = state.get("credible_sources", {})
    all_sources = state.get("all_sources", {})

    # Index all credible sources into ChromaDB
    all_credible = []
    for sources in credible_sources.values():
        for s in sources:
            if s not in all_credible:
                all_credible.append(s)

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, vector_store.add_sources, session_id, all_credible)

    # Phase 1: Retrieve chunks sequentially (ONNX embedding is NOT thread-safe)
    sub_questions = state.get("sub_questions", [])
    loop = asyncio.get_event_loop()
    all_chunks: dict = {}
    for q in sub_questions:
        sources_for_q = credible_sources.get(q, [])
        source_ids = [s["source_id"] for s in sources_for_q]
        q_chunks = await loop.run_in_executor(
            None,
            lambda _q=q, _ids=source_ids: vector_store.retrieve(
                session_id=session_id,
                query=_q,
                n_results=10,
                source_filter=_ids if _ids else None,
            )
        )
        all_chunks[q] = q_chunks

    # Phase 2: Synthesize with LLM in parallel (LLM calls are async / network IO)
    semaphore = asyncio.Semaphore(3)

    async def synthesize_with_sem(q: str) -> dict:
        async with semaphore:
            return await _synthesize_with_chunks(q, all_chunks.get(q, []), all_sources)

    tasks = [synthesize_with_sem(q) for q in sub_questions]
    section_results = await asyncio.gather(*tasks, return_exceptions=True)

    synthesized_sections = []
    for q, result in zip(sub_questions, section_results):
        if isinstance(result, Exception):
            logger.error(f"[Synthesizer] Error for '{q[:50]}': {result}")
            synthesized_sections.append({
                "sub_question": q,
                "content": f"*Không thể tổng hợp nội dung cho câu hỏi này do lỗi hệ thống.*",
                "citations": [],
            })
        else:
            synthesized_sections.append(result)

    progress.append(ProgressUpdate(
        agent="synthesizer",
        status=AgentStatus.COMPLETED,
        message=f"Đã tổng hợp {len(synthesized_sections)} phần nội dung"
    ))

    state["synthesized_sections"] = synthesized_sections
    state["progress"] = progress
    return state


async def _synthesize_with_chunks(
    question: str,
    chunks: List[dict],
    all_sources: Dict[str, dict],
) -> dict:
    """Generate one section using pre-fetched RAG chunks."""
    if not chunks:
        return {
            "sub_question": question,
            "content": "*Không tìm thấy nguồn đáng tin cậy nào cho câu hỏi này.*",
            "citations": [],
        }

    # Build context from chunks
    context_parts = []
    for chunk in chunks:
        sid = chunk["source_id"]
        title = chunk.get("title", "")
        content = chunk["content"]
        context_parts.append(f"[{sid}] {title}\n{content}")

    context = "\n\n---\n\n".join(context_parts)

    # Include source metadata for reference
    source_meta = {}
    for chunk in chunks:
        sid = chunk["source_id"]
        if sid and sid not in source_meta:
            source_info = all_sources.get(sid, {})
            source_meta[sid] = {
                "url": chunk.get("url", source_info.get("url", "")),
                "title": chunk.get("title", source_info.get("title", "")),
                "score": source_info.get("total_score", 5.0),
            }

    llm = get_llm_client()
    prompt = f"""Research sub-question: {question}

Source chunks (each prefixed with [source_id]):
{context}

Write a comprehensive section answering this sub-question. Cite every fact with the relevant [source_id]."""

    response = await llm.ainvoke([
        SystemMessage(content=SYNTHESIS_SYSTEM),
        HumanMessage(content=prompt)
    ])

    parsed = _parse_synthesis_response(response.content)

    # Extract citations from content
    citations = _extract_citations(parsed.get("content", ""), source_meta)

    return {
        "sub_question": question,
        "content": parsed.get("content", ""),
        "key_claims": parsed.get("key_claims", []),
        "sources_used": parsed.get("sources_used", []),
        "citations": citations,
        "source_meta": source_meta,
    }


def _parse_synthesis_response(content: str) -> dict:
    import re
    text = content.strip()

    # Build list of candidates to try, best-first
    candidates = []

    # 1. Content inside ```json ... ``` or ``` ... ``` fences
    for m in re.finditer(r'```(?:json)?\s*(.*?)```', text, re.DOTALL):
        candidates.append(m.group(1).strip())

    # 2. First JSON object found anywhere in the text (greedy { ... })
    m = re.search(r'\{.*\}', text, re.DOTALL)
    if m:
        candidates.append(m.group(0))

    # 3. Full text as-is
    candidates.append(text)

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict) and "content" in parsed:
                # Unwrap double-nested: content field itself looks like JSON
                inner_text = parsed["content"]
                if isinstance(inner_text, str) and inner_text.strip().startswith("{"):
                    try:
                        inner = json.loads(inner_text)
                        if isinstance(inner, dict) and "content" in inner:
                            return inner
                    except Exception:
                        pass
                return parsed
        except Exception:
            pass

    # 4. Regex: pull "content" value even if surrounding JSON is broken
    m = re.search(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
    if m:
        try:
            extracted = json.loads('"' + m.group(1) + '"')  # proper unescape
            return {"content": extracted, "key_claims": [], "sources_used": []}
        except Exception:
            pass

    # 5. Absolute fallback: raw text
    return {"content": content, "key_claims": [], "sources_used": []}


def _extract_citations(content: str, source_meta: Dict[str, dict]) -> List[dict]:
    """Extract all [source_id] mentions from content."""
    import re
    citations = []
    seen = set()
    for match in re.finditer(r'\[([a-f0-9]{6,8})\]', content):
        sid = match.group(1)
        if sid not in seen and sid in source_meta:
            seen.add(sid)
            meta = source_meta[sid]
            citations.append({
                "source_id": sid,
                "url": meta.get("url", ""),
                "title": meta.get("title", ""),
                "score": meta.get("score", 5.0),
            })
    return citations
