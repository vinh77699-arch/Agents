"""Search & Scraper Agent: fetch content for each sub-question in parallel."""
import asyncio
import logging
from typing import Dict, List

from app.core.config import settings
from app.core.state import ResearchState, SearchResult, ProgressUpdate, AgentStatus
from app.services.search import search_service
from app.services.scraper import scrape_urls_batch

logger = logging.getLogger(__name__)


async def run_searcher(state: ResearchState) -> ResearchState:
    """Search and scrape content for all sub-questions in parallel."""
    logger.info("[Searcher] Starting parallel search")

    progress = list(state.get("progress", []))
    progress.append(ProgressUpdate(
        agent="searcher",
        status=AgentStatus.RUNNING,
        message="Đang tìm kiếm song song cho tất cả câu hỏi..."
    ))

    sub_questions = state.get("sub_questions", [])
    search_queries = state.get("search_queries", {})
    calls_used = state.get("search_calls_used", 0)
    remaining_calls = settings.max_search_calls - calls_used
    calls_per_question = max(1, remaining_calls // max(len(sub_questions), 1))

    # Run all sub-questions in parallel
    tasks = [
        _search_for_question(q, search_queries.get(q, [q]), calls_per_question)
        for q in sub_questions
    ]
    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    raw_results: Dict[str, List[SearchResult]] = {}
    total_calls = 0

    for q, result in zip(sub_questions, results_list):
        if isinstance(result, Exception):
            logger.error(f"[Searcher] Error for '{q[:50]}': {result}")
            raw_results[q] = []
        else:
            results, calls = result
            raw_results[q] = results
            total_calls += calls

    # Scrape missing full content
    all_urls = {r.url: r for q_results in raw_results.values() for r in q_results if not r.content}
    if all_urls:
        scraped = await scrape_urls_batch(list(all_urls.keys())[:20])
        for url, content in scraped.items():
            if content and url in all_urls:
                all_urls[url].content = content

    state["raw_results"] = {q: [_result_to_dict(r) for r in results]
                             for q, results in raw_results.items()}
    state["search_calls_used"] = calls_used + total_calls

    total_results = sum(len(v) for v in raw_results.values())
    progress.append(ProgressUpdate(
        agent="searcher",
        status=AgentStatus.COMPLETED,
        message=f"Tìm thấy {total_results} kết quả từ {total_calls} lần gọi API",
        data={"total_results": total_results, "calls_used": total_calls}
    ))
    state["progress"] = progress
    return state


async def _search_for_question(
    question: str,
    queries: List[str],
    max_calls: int
) -> tuple[List[SearchResult], int]:
    """Search for a single sub-question using multiple queries."""
    all_results: List[SearchResult] = []
    seen_urls: set = set()
    calls = 0

    for query in queries[:max_calls]:
        results = await search_service.search(query, max_results=5)
        calls += 1
        for r in results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                all_results.append(r)

    # Academic search for scholarly topics
    academic = await search_service.search_academic(question, max_results=3)
    for r in academic:
        if r.url not in seen_urls:
            seen_urls.add(r.url)
            all_results.append(r)

    return all_results, calls


def _result_to_dict(r: SearchResult) -> dict:
    return {
        "source_id": r.source_id,
        "url": r.url,
        "title": r.title,
        "snippet": r.snippet,
        "content": r.content,
        "published_date": r.published_date,
    }
