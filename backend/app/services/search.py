"""Search service: Tavily primary, DuckDuckGo fallback."""
import asyncio
import hashlib
import logging
from typing import List, Optional
from dataclasses import asdict

import httpx

from app.core.config import settings
from app.core.state import SearchResult

logger = logging.getLogger(__name__)


class SearchService:
    def __init__(self):
        self._cache: dict = {}

    def _cache_key(self, query: str) -> str:
        return hashlib.md5(query.encode()).hexdigest()

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Search with Tavily primary, DuckDuckGo fallback."""
        key = self._cache_key(query)
        if key in self._cache:
            logger.debug(f"[Search] Cache hit for: {query[:50]}")
            return self._cache[key]

        results = []
        if settings.tavily_api_key:
            results = await self._tavily_search(query, max_results)

        if not results:
            logger.info(f"[Search] Falling back to DuckDuckGo for: {query[:50]}")
            results = await self._ddg_search(query, max_results)

        self._cache[key] = results
        return results

    async def _tavily_search(self, query: str, max_results: int) -> List[SearchResult]:
        try:
            async with httpx.AsyncClient(timeout=settings.search_timeout) as client:
                response = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": settings.tavily_api_key,
                        "query": query,
                        "max_results": max_results,
                        "include_raw_content": True,
                        "search_depth": "advanced",
                    }
                )
                response.raise_for_status()
                data = response.json()
                results = []
                for r in data.get("results", []):
                    results.append(SearchResult(
                        url=r.get("url", ""),
                        title=r.get("title", ""),
                        snippet=r.get("content", "")[:500],
                        content=r.get("raw_content", r.get("content", ""))[:5000],
                        published_date=r.get("published_date"),
                    ))
                return results
        except Exception as e:
            logger.warning(f"[Search] Tavily error: {e}")
            return []

    async def _ddg_search(self, query: str, max_results: int) -> List[SearchResult]:
        try:
            from duckduckgo_search import AsyncDDGS
            async with AsyncDDGS() as ddgs:
                raw = await ddgs.atext(query, max_results=max_results)
                results = []
                for r in raw:
                    results.append(SearchResult(
                        url=r.get("href", ""),
                        title=r.get("title", ""),
                        snippet=r.get("body", "")[:500],
                        content=r.get("body", "")[:3000],
                    ))
                return results
        except Exception as e:
            logger.warning(f"[Search] DuckDuckGo error: {e}")
            return []

    async def search_academic(self, query: str, max_results: int = 3) -> List[SearchResult]:
        """Search academic sources via Semantic Scholar API."""
        results = []
        try:
            async with httpx.AsyncClient(timeout=settings.search_timeout) as client:
                response = await client.get(
                    "https://api.semanticscholar.org/graph/v1/paper/search",
                    params={
                        "query": query,
                        "limit": max_results,
                        "fields": "title,abstract,year,url,authors,externalIds",
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    for p in data.get("data", []):
                        url = p.get("url") or f"https://www.semanticscholar.org/paper/{p.get('paperId','')}"
                        results.append(SearchResult(
                            url=url,
                            title=p.get("title", ""),
                            snippet=p.get("abstract", "")[:500],
                            content=p.get("abstract", ""),
                            published_date=str(p.get("year", "")) if p.get("year") else None,
                        ))
        except Exception as e:
            logger.warning(f"[Search] Semantic Scholar error: {e}")
        return results


search_service = SearchService()
