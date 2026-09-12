"""Planner Agent: breaks a research topic into 4-6 independent sub-questions."""
import json
import logging
from typing import List, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import get_llm_client
from app.core.state import ResearchState, ProgressUpdate, AgentStatus

logger = logging.getLogger(__name__)

PLANNER_SYSTEM = """You are a senior research strategist. Your task is to decompose a research topic
into specific, independently searchable sub-questions that together provide comprehensive coverage.

Rules:
- Generate exactly 4-6 sub-questions
- Each sub-question must be independently searchable (no cross-dependencies)
- Cover different facets: background, current state, mechanisms, evidence, implications, critiques
- Be specific enough to yield focused search results
- For each sub-question, also provide 2-3 concrete search query strings (what you'd type in Google)

Respond ONLY with valid JSON in this exact format:
{
  "sub_questions": [
    {
      "question": "...",
      "rationale": "...",
      "search_queries": ["query1", "query2", "query3"]
    }
  ]
}"""


async def run_planner(state: ResearchState) -> ResearchState:
    """Planner agent: topic → sub-questions + search queries."""
    logger.info(f"[Planner] Starting for topic: {state['topic']}")

    progress = list(state.get("progress", []))
    progress.append(ProgressUpdate(
        agent="planner",
        status=AgentStatus.RUNNING,
        message=f"Phân tích chủ đề: '{state['topic']}'"
    ))

    llm = get_llm_client()
    retry_count = state.get("retry_count", 0)

    # If retrying, we need more queries for under-served questions
    if retry_count > 0:
        context = _build_retry_context(state)
        prompt = f"""Topic: {state['topic']}

Previous sub-questions that need more search coverage:
{context}

Generate 2-3 ADDITIONAL search query strings for each under-served question above.
Respond ONLY with valid JSON: {{"additional_queries": {{"<sub_question>": ["q1","q2","q3"]}}}}"""
        messages = [SystemMessage(content=PLANNER_SYSTEM), HumanMessage(content=prompt)]
        response = await llm.ainvoke(messages)
        result = _parse_additional_queries(response.content, state)
        state["search_queries"] = result
    else:
        prompt = f"Research topic: {state['topic']}\n\nDecompose this into research sub-questions."
        messages = [SystemMessage(content=PLANNER_SYSTEM), HumanMessage(content=prompt)]
        response = await llm.ainvoke(messages)
        parsed = _parse_planner_response(response.content)
        state["sub_questions"] = [item["question"] for item in parsed]
        state["search_queries"] = {
            item["question"]: item["search_queries"] for item in parsed
        }

    progress.append(ProgressUpdate(
        agent="planner",
        status=AgentStatus.COMPLETED,
        message=f"Đã tạo {len(state['sub_questions'])} câu hỏi nghiên cứu",
        data={"sub_questions": state["sub_questions"]}
    ))
    state["progress"] = progress
    logger.info(f"[Planner] Generated {len(state['sub_questions'])} sub-questions")
    return state


def _parse_planner_response(content: str) -> List[Dict]:
    """Parse LLM JSON response from planner."""
    try:
        # Strip markdown code blocks if present
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        data = json.loads(content.strip())
        return data["sub_questions"]
    except Exception as e:
        logger.error(f"[Planner] Parse error: {e}, content: {content[:200]}")
        # Fallback: generate generic sub-questions
        return [
            {"question": f"What is {content[:50]}?", "rationale": "Overview", "search_queries": [content[:50]]},
        ]


def _build_retry_context(state: ResearchState) -> str:
    """Build context string for retry planning."""
    credible = state.get("credible_sources", {})
    lines = []
    for q in state.get("sub_questions", []):
        count = len(credible.get(q, []))
        if count < 2:
            lines.append(f"- {q} (only {count} credible source(s) found)")
    return "\n".join(lines) if lines else "All questions"


def _parse_additional_queries(content: str, state: ResearchState) -> Dict[str, List[str]]:
    """Parse additional queries from retry response."""
    current = dict(state.get("search_queries", {}))
    try:
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        data = json.loads(content.strip())
        additional = data.get("additional_queries", {})
        for q, queries in additional.items():
            if q in current:
                current[q] = current[q] + queries
            else:
                # Try fuzzy match
                for existing_q in current:
                    if q[:30] in existing_q or existing_q[:30] in q:
                        current[existing_q] = current[existing_q] + queries
                        break
    except Exception as e:
        logger.error(f"[Planner] Additional query parse error: {e}")
    return current
