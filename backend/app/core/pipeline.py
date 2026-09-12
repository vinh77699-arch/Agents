"""LangGraph pipeline: orchestrates all agents with retry loop."""
import logging
import uuid
from typing import AsyncGenerator

from langgraph.graph import StateGraph, END

from app.core.state import ResearchState, AgentStatus, ProgressUpdate
from app.core.config import settings
from app.agents.planner import run_planner
from app.agents.searcher import run_searcher
from app.agents.credibility import run_credibility_evaluator
from app.agents.synthesizer import run_synthesizer
from app.agents.report_writer import run_report_writer

logger = logging.getLogger(__name__)


def _check_credibility_threshold(state: ResearchState) -> str:
    """Router: if too few credible sources, retry planning (up to max_retry_loops)."""
    retry_count = state.get("retry_count", 0)
    credible = state.get("credible_sources", {})
    sub_questions = state.get("sub_questions", [])

    # Count questions with insufficient sources
    under_threshold = sum(
        1 for q in sub_questions
        if len(credible.get(q, [])) < settings.min_credible_sources_per_question
    )

    if under_threshold > 0 and retry_count < settings.max_retry_loops:
        logger.info(f"[Pipeline] {under_threshold} questions under threshold, retrying (attempt {retry_count + 1})")
        return "retry"
    return "synthesize"


async def _increment_retry(state: ResearchState) -> ResearchState:
    """Increment retry counter before re-planning."""
    state["retry_count"] = state.get("retry_count", 0) + 1
    progress = list(state.get("progress", []))
    progress.append(ProgressUpdate(
        agent="pipeline",
        status=AgentStatus.RETRYING,
        message=f"Tìm kiếm thêm nguồn (lần thử {state['retry_count']}/{settings.max_retry_loops})..."
    ))
    state["progress"] = progress
    return state


def build_pipeline() -> StateGraph:
    """Build the LangGraph state machine."""
    graph = StateGraph(ResearchState)

    # Add nodes
    graph.add_node("planner", run_planner)
    graph.add_node("searcher", run_searcher)
    graph.add_node("credibility", run_credibility_evaluator)
    graph.add_node("increment_retry", _increment_retry)
    graph.add_node("synthesizer", run_synthesizer)
    graph.add_node("report_writer", run_report_writer)

    # Define edges
    graph.set_entry_point("planner")
    graph.add_edge("planner", "searcher")
    graph.add_edge("searcher", "credibility")

    # Conditional edge: retry or proceed
    graph.add_conditional_edges(
        "credibility",
        _check_credibility_threshold,
        {"retry": "increment_retry", "synthesize": "synthesizer"}
    )

    # Retry loop: increment → planner (re-plan with extra queries) → search → credibility
    graph.add_edge("increment_retry", "planner")

    # Main path
    graph.add_edge("synthesizer", "report_writer")
    graph.add_edge("report_writer", END)

    return graph.compile()


async def run_research_pipeline(
    topic: str,
    session_id: str = None,
) -> AsyncGenerator[dict, None]:
    """Run the full research pipeline, yielding progress events via SSE."""
    if not session_id:
        session_id = str(uuid.uuid4())

    initial_state: ResearchState = {
        "topic": topic,
        "session_id": session_id,
        "sub_questions": [],
        "search_queries": {},
        "raw_results": {},
        "search_calls_used": 0,
        "credible_sources": {},
        "discarded_sources": {},
        "retry_count": 0,
        "synthesized_sections": [],
        "all_sources": {},
        "final_report": "",
        "bibliography": [],
        "progress": [],
        "errors": [],
        "status": "running",
    }

    pipeline = build_pipeline()

    final_state = None

    try:
        # Stream via astream — yields state snapshots after each node
        async for chunk in pipeline.astream(initial_state, stream_mode="updates"):
            for node_name, node_output in chunk.items():
                if node_name not in ["planner", "searcher", "credibility",
                                     "synthesizer", "report_writer", "increment_retry"]:
                    continue

                # Extract latest progress update from output
                progress_list = node_output.get("progress", [])
                if progress_list:
                    latest = progress_list[-1]
                    if hasattr(latest, '__dict__'):
                        latest = latest.__dict__
                    status = latest.get("status", "")
                    status_val = status.value if hasattr(status, "value") else str(status)

                    if status_val == "running":
                        yield {
                            "type": "agent_start",
                            "agent": node_name,
                            "message": latest.get("message", ""),
                        }
                    elif status_val in ("completed", "retrying"):
                        yield {
                            "type": "agent_complete",
                            "agent": node_name,
                            "message": latest.get("message", ""),
                            "data": latest.get("data") or {},
                        }

                # Track final state
                final_state = node_output

        # Emit completion event
        if final_state:
            yield {
                "type": "complete",
                "session_id": session_id,
                "report": final_state.get("final_report", ""),
                "bibliography": final_state.get("bibliography", []),
                "all_sources": final_state.get("all_sources", {}),
            }

    except Exception as e:
        logger.error(f"[Pipeline] Fatal error: {e}", exc_info=True)
        yield {
            "type": "error",
            "message": str(e),
        }


async def run_research_pipeline_sync(
    topic: str,
    session_id: str = None,
) -> dict:
    """Run pipeline and return final merged state (non-streaming)."""
    if not session_id:
        session_id = str(uuid.uuid4())

    initial_state: ResearchState = {
        "topic": topic,
        "session_id": session_id,
        "sub_questions": [],
        "search_queries": {},
        "raw_results": {},
        "search_calls_used": 0,
        "credible_sources": {},
        "discarded_sources": {},
        "retry_count": 0,
        "synthesized_sections": [],
        "all_sources": {},
        "final_report": "",
        "bibliography": [],
        "progress": [],
        "errors": [],
        "status": "running",
    }

    pipeline = build_pipeline()
    # Merge all state updates into one final dict
    merged: dict = dict(initial_state)
    async for chunk in pipeline.astream(initial_state, stream_mode="updates"):
        for node_output in chunk.values():
            merged.update(node_output)
    return merged
