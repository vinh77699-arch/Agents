"""Scraper service: extract clean text content from URLs."""
import asyncio
import logging
from typing import Optional
import httpx
import trafilatura

from app.core.config import settings

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0; +https://research-agent.dev)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


async def scrape_url(url: str) -> Optional[str]:
    """Fetch and extract clean text from a URL."""
    if not url or not url.startswith("http"):
        return None

    try:
        async with httpx.AsyncClient(
            timeout=settings.scrape_timeout,
            headers=HEADERS,
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            if response.status_code != 200:
                logger.debug(f"[Scraper] HTTP {response.status_code} for {url}")
                return None

            content_type = response.headers.get("content-type", "")
            if "pdf" in content_type:
                return await _extract_pdf(response.content)

            html = response.text
            text = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                no_fallback=False,
                favor_recall=True,
                deduplicate=True,
            )
            if text and len(text) > 100:
                return text[:8000]  # Cap at 8k chars per page
            return None

    except Exception as e:
        logger.debug(f"[Scraper] Error scraping {url}: {e}")
        return None


async def _extract_pdf(content: bytes) -> Optional[str]:
    """Extract text from PDF bytes."""
    try:
        import io
        import pdfplumber
        text_parts = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages[:10]:  # Max 10 pages
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        return "\n\n".join(text_parts)[:8000] if text_parts else None
    except Exception as e:
        logger.debug(f"[Scraper] PDF extract error: {e}")
        return None


async def scrape_urls_batch(urls: list[str], max_concurrent: int = 5) -> dict[str, Optional[str]]:
    """Scrape multiple URLs concurrently."""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def scrape_with_sem(url: str) -> tuple[str, Optional[str]]:
        async with semaphore:
            content = await scrape_url(url)
            return url, content

    tasks = [scrape_with_sem(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output = {}
    for r in results:
        if isinstance(r, Exception):
            continue
        url, content = r
        output[url] = content
    return output
