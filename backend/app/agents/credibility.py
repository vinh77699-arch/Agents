"""Credibility Evaluator Agent: score and filter sources by trustworthiness."""
import asyncio
import logging
import re
from datetime import datetime
from typing import List, Dict, Optional
from collections import defaultdict

import tldextract
from dateutil import parser as dateparser

from app.core.config import settings, get_llm_client
from app.core.state import ResearchState, CredibilityScore, ProgressUpdate, AgentStatus

logger = logging.getLogger(__name__)

# Domain authority whitelist
DOMAIN_SCORES = {
    # High authority (8-10)
    ".gov": 9.0, ".edu": 8.5, ".ac.": 8.5,
    "nature.com": 9.5, "science.org": 9.5, "nejm.org": 9.5,
    "thelancet.com": 9.0, "bmj.com": 9.0, "pubmed.ncbi.nlm.nih.gov": 9.5,
    "scholar.google.com": 9.0, "arxiv.org": 8.0, "ssrn.com": 8.0,
    "jstor.org": 8.5, "springer.com": 8.5, "wiley.com": 8.5,
    "ieee.org": 8.5, "acm.org": 8.5,
    # Medium-high (6-8)
    "wikipedia.org": 6.5, "reuters.com": 7.5, "apnews.com": 7.5,
    "bbc.com": 7.0, "bbc.co.uk": 7.0, "nytimes.com": 7.0,
    "washingtonpost.com": 7.0, "theguardian.com": 7.0, "economist.com": 7.5,
    "ft.com": 7.5, "wsj.com": 7.0, "bloomberg.com": 7.0,
    "who.int": 9.0, "cdc.gov": 9.0, "nih.gov": 9.0,
    # Medium (4-6)
    ".org": 5.5,
    # Low (1-3) - covered by default
}

LLM_JUDGE_PROMPT = """You are a research quality assessor. Evaluate this source for a research report.

URL: {url}
Title: {title}
Content excerpt: {excerpt}

Rate this source on a scale 1-10 based on:
1. Author expertise and credentials (if visible)
2. Evidence-based claims with citations/data
3. Absence of bias, clickbait, or sensationalism
4. Clarity and structure of argument
5. Relevance and depth of content

Respond ONLY with valid JSON:
{{
  "score": <number 1-10>,
  "reasoning": "<2-3 sentence explanation>",
  "red_flags": ["<flag1>", "<flag2>"] // empty list if none
}}"""


async def run_credibility_evaluator(state: ResearchState) -> ResearchState:
    """Evaluate and score all sources, filter below threshold."""
    logger.info("[Credibility] Starting evaluation")

    progress = list(state.get("progress", []))
    progress.append(ProgressUpdate(
        agent="credibility",
        status=AgentStatus.RUNNING,
        message="Đang đánh giá độ tin cậy của các nguồn..."
    ))

    raw_results = state.get("raw_results", {})
    topic = state.get("topic", "")
    is_time_sensitive = _is_time_sensitive_topic(topic)

    # Collect all unique sources across questions for cross-reference scoring
    all_sources_by_url: Dict[str, dict] = {}
    question_to_urls: Dict[str, List[str]] = {}
    for q, results in raw_results.items():
        question_to_urls[q] = []
        for r in results:
            url = r["url"]
            question_to_urls[q].append(url)
            if url not in all_sources_by_url:
                all_sources_by_url[url] = r

    # Count cross-references (same URL appears for multiple questions)
    url_cross_ref_count: Dict[str, int] = defaultdict(int)
    for urls in question_to_urls.values():
        for url in urls:
            url_cross_ref_count[url] += 1

    # Score all unique sources with LLM in parallel (batch to control costs)
    unique_sources = list(all_sources_by_url.values())
    logger.info(f"[Credibility] Scoring {len(unique_sources)} unique sources")

    llm_scores = await _batch_llm_judge(unique_sources[:30])  # limit LLM calls

    # Build scored sources
    scored: Dict[str, CredibilityScore] = {}
    for source in unique_sources:
        url = source["url"]
        score = _compute_credibility_score(
            source=source,
            cross_ref_count=url_cross_ref_count[url],
            total_questions=len(raw_results),
            llm_result=llm_scores.get(url, {}),
            is_time_sensitive=is_time_sensitive,
        )
        scored[url] = score

    # Assign back per question
    credible: Dict[str, List[dict]] = {}
    discarded: Dict[str, List[dict]] = {}
    all_sources: Dict[str, dict] = {}

    for q, urls in question_to_urls.items():
        credible[q] = []
        discarded[q] = []
        for url in urls:
            s = scored.get(url)
            if not s:
                continue
            s_dict = _score_to_dict(s)
            all_sources[s.source_id] = s_dict
            if s.is_credible:
                credible[q].append(s_dict)
            else:
                discarded[q].append(s_dict)

    total_credible = sum(len(v) for v in credible.values())
    total_discarded = sum(len(v) for v in discarded.values())

    progress.append(ProgressUpdate(
        agent="credibility",
        status=AgentStatus.COMPLETED,
        message=f"Kết quả: {total_credible} nguồn đáng tin cậy, {total_discarded} bị loại",
        data={"credible": total_credible, "discarded": total_discarded}
    ))

    state["credible_sources"] = credible
    state["discarded_sources"] = discarded
    state["all_sources"] = all_sources
    state["progress"] = progress
    return state


def _compute_credibility_score(
    source: dict,
    cross_ref_count: int,
    total_questions: int,
    llm_result: dict,
    is_time_sensitive: bool,
) -> CredibilityScore:
    url = source.get("url", "")
    title = source.get("title", "")
    content = source.get("content", "")
    published_date = source.get("published_date")
    source_id = source.get("source_id", "")

    # 1. Domain authority score (0-10)
    domain_score = _score_domain(url)

    # 2. Recency score (0-10)
    recency_score = _score_recency(published_date, is_time_sensitive)

    # 3. Cross-reference score (0-10)
    if total_questions <= 1:
        cross_ref_score = 5.0
    else:
        # Score 10 if appears across all questions, 0 if only one
        cross_ref_score = min(10.0, (cross_ref_count - 1) / (total_questions - 1) * 10)
        cross_ref_score = max(2.0, cross_ref_score)  # minimum 2 for being found at all

    # 4. LLM judge score (0-10)
    llm_score = float(llm_result.get("score", 5.0))
    llm_reasoning = llm_result.get("reasoning", "No LLM evaluation available")
    red_flags = llm_result.get("red_flags", [])

    # Weighted total: domain 30%, recency 20%, cross-ref 15%, llm 35%
    total = (domain_score * 0.30 + recency_score * 0.20 +
             cross_ref_score * 0.15 + llm_score * 0.35)

    is_credible = total >= settings.credibility_threshold

    explanation = (
        f"Domain: {domain_score:.1f}/10 | "
        f"Recency: {recency_score:.1f}/10 | "
        f"Cross-ref: {cross_ref_score:.1f}/10 | "
        f"Quality: {llm_score:.1f}/10 → "
        f"Total: {total:.1f}/10. {llm_reasoning}"
    )
    if red_flags:
        explanation += f" ⚠️ Red flags: {', '.join(red_flags)}"

    return CredibilityScore(
        source_id=source_id,
        url=url,
        title=title,
        domain_score=domain_score,
        recency_score=recency_score,
        cross_ref_score=cross_ref_score,
        llm_judge_score=llm_score,
        total_score=round(total, 2),
        explanation=explanation,
        is_credible=is_credible,
        content=content[:6000],
        published_date=published_date,
    )


def _score_domain(url: str) -> float:
    """Score a URL's domain authority."""
    if not url:
        return 3.0
    url_lower = url.lower()

    # Check exact domain matches first
    for domain, score in DOMAIN_SCORES.items():
        if domain in url_lower:
            return score

    # TLD-based scoring
    try:
        ext = tldextract.extract(url)
        tld = f".{ext.suffix}"
        if tld in DOMAIN_SCORES:
            return DOMAIN_SCORES[tld]
    except Exception:
        pass

    # Heuristics
    if any(x in url_lower for x in ["blog.", "wordpress.", "medium.com", "substack.com"]):
        return 4.0
    if any(x in url_lower for x in ["reddit.com", "quora.com", "forum"]):
        return 3.0
    return 4.5  # default for unknown


def _score_recency(date_str: Optional[str], is_time_sensitive: bool) -> float:
    """Score recency of a source."""
    if not is_time_sensitive:
        return 6.0  # Neutral for non-time-sensitive topics

    if not date_str:
        return 4.0  # Unknown date: below neutral

    try:
        pub_date = dateparser.parse(str(date_str), fuzzy=True)
        if not pub_date:
            return 4.0
        now = datetime.now()
        if pub_date.tzinfo:
            from datetime import timezone
            now = now.replace(tzinfo=timezone.utc)
        age_days = (now - pub_date).days
        if age_days < 0:
            age_days = 0

        if age_days < 30: return 10.0
        if age_days < 90: return 9.0
        if age_days < 180: return 8.0
        if age_days < 365: return 7.0
        if age_days < 730: return 6.0
        if age_days < 1825: return 4.0
        return 2.0
    except Exception:
        return 4.0


def _is_time_sensitive_topic(topic: str) -> bool:
    """Determine if topic requires recent sources."""
    time_sensitive_keywords = [
        "current", "latest", "recent", "2024", "2025", "2026", "today",
        "now", "trend", "news", "update", "market", "price", "covid",
        "election", "policy", "regulation", "startup", "technology"
    ]
    topic_lower = topic.lower()
    return any(kw in topic_lower for kw in time_sensitive_keywords)


async def _batch_llm_judge(sources: List[dict]) -> Dict[str, dict]:
    """Run LLM judge on sources in parallel batches."""
    llm = get_llm_client()
    semaphore = asyncio.Semaphore(5)

    async def judge_one(source: dict) -> tuple[str, dict]:
        url = source.get("url", "")
        content = source.get("content") or source.get("snippet", "")
        excerpt = content[:800] if content else ""

        async with semaphore:
            try:
                from langchain_core.messages import HumanMessage
                prompt = LLM_JUDGE_PROMPT.format(
                    url=url,
                    title=source.get("title", ""),
                    excerpt=excerpt,
                )
                response = await llm.ainvoke([HumanMessage(content=prompt)])
                result = _parse_llm_judge_response(response.content)
                return url, result
            except Exception as e:
                logger.debug(f"[Credibility] LLM judge error for {url}: {e}")
                return url, {"score": 5.0, "reasoning": "Evaluation unavailable", "red_flags": []}

    tasks = [judge_one(s) for s in sources]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    output = {}
    for r in results:
        if isinstance(r, tuple):
            url, data = r
            output[url] = data
    return output


def _parse_llm_judge_response(content: str) -> dict:
    import json
    try:
        content = content.strip()
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        data = json.loads(content.strip())
        return {
            "score": float(data.get("score", 5.0)),
            "reasoning": data.get("reasoning", ""),
            "red_flags": data.get("red_flags", []),
        }
    except Exception:
        match = re.search(r'"score"\s*:\s*(\d+(?:\.\d+)?)', content)
        score = float(match.group(1)) if match else 5.0
        return {"score": score, "reasoning": "Parsing error in evaluation", "red_flags": []}


def _score_to_dict(s: CredibilityScore) -> dict:
    return {
        "source_id": s.source_id,
        "url": s.url,
        "title": s.title,
        "domain_score": s.domain_score,
        "recency_score": s.recency_score,
        "cross_ref_score": s.cross_ref_score,
        "llm_judge_score": s.llm_judge_score,
        "total_score": s.total_score,
        "explanation": s.explanation,
        "is_credible": s.is_credible,
        "content": s.content,
        "published_date": s.published_date,
    }
