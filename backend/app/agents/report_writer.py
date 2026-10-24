"""Report Writer Agent: assembles final Markdown/HTML report with TOC and bibliography."""
import json
import logging
import re
from typing import List, Dict
from datetime import datetime

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import get_llm_client, settings
from app.core.state import ResearchState, ProgressUpdate, AgentStatus

logger = logging.getLogger(__name__)

REPORT_SYSTEM = """Bạn là một biên tập viên học thuật cấp cao. Nhiệm vụ của bạn là tổng hợp một báo cáo nghiên cứu hoàn chỉnh.
QUAN TRỌNG: Viết toàn bộ nội dung bằng tiếng Việt, sử dụng văn phong học thuật trang trọng.
Không thêm nội dung không có trong các phần đã tổng hợp.
Chỉ viết phần giới thiệu và kết luận ngắn gọn để kết nối các phần với nhau."""

REPORT_INTRO_PROMPT = """Chủ đề nghiên cứu: {topic}

Tóm tắt các phần đã tổng hợp:
{sections_summary}

Viết phần giới thiệu 2-3 đoạn văn bằng tiếng Việt cho báo cáo nghiên cứu này, bao gồm:
1. Bối cảnh và lý do của chủ đề
2. Phạm vi nghiên cứu
3. Cấu trúc của báo cáo

Chỉ trả về phần giới thiệu (không có tiêu đề, không có JSON)."""

REPORT_CONCLUSION_PROMPT = """Dựa trên các phát hiện nghiên cứu đã tổng hợp sau:

{sections_summary}

Viết phần kết luận 2-3 đoạn văn bằng tiếng Việt, bao gồm:
1. Tổng hợp các phát hiện chính
2. Ghi nhận hạn chế của nguồn/nghiên cứu
3. Đề xuất hướng nghiên cứu tiếp theo

Chỉ trả về phần kết luận (không có tiêu đề, không có JSON)."""


async def run_report_writer(state: ResearchState) -> ResearchState:
    """Assemble the final research report."""
    logger.info("[ReportWriter] Assembling final report")

    progress = list(state.get("progress", []))
    progress.append(ProgressUpdate(
        agent="report_writer",
        status=AgentStatus.RUNNING,
        message="Đang viết báo cáo hoàn chỉnh..."
    ))

    topic = state.get("topic", "Research Report")
    synthesized_sections = state.get("synthesized_sections", [])
    all_sources = state.get("all_sources", {})
    credible_sources = state.get("credible_sources", {})
    discarded_sources = state.get("discarded_sources", {})

    llm = get_llm_client()

    # Generate introduction
    sections_summary = _build_sections_summary(synthesized_sections)
    intro_response = await llm.ainvoke([
        SystemMessage(content=REPORT_SYSTEM),
        HumanMessage(content=REPORT_INTRO_PROMPT.format(
            topic=topic, sections_summary=sections_summary[:3000]
        ))
    ])
    introduction = intro_response.content.strip()

    # Generate conclusion
    conclusion_response = await llm.ainvoke([
        SystemMessage(content=REPORT_SYSTEM),
        HumanMessage(content=REPORT_CONCLUSION_PROMPT.format(
            sections_summary=sections_summary[:3000]
        ))
    ])
    conclusion = conclusion_response.content.strip()

    # Build bibliography (APA format)
    bibliography = _build_bibliography(all_sources, synthesized_sections)

    # Assemble complete report
    report_md = _assemble_markdown_report(
        topic=topic,
        introduction=introduction,
        sections=synthesized_sections,
        conclusion=conclusion,
        bibliography=bibliography,
        all_sources=all_sources,
        credible_sources=credible_sources,
        discarded_sources=discarded_sources,
    )

    progress.append(ProgressUpdate(
        agent="report_writer",
        status=AgentStatus.COMPLETED,
        message="Báo cáo hoàn thành!",
        data={"word_count": len(report_md.split()), "sources_cited": len(bibliography)}
    ))

    state["final_report"] = report_md
    state["bibliography"] = bibliography
    state["progress"] = progress
    state["status"] = "completed"
    return state


def _build_sections_summary(sections: List[dict]) -> str:
    parts = []
    for s in sections:
        q = s.get("sub_question", "")
        content_preview = s.get("content", "")[:300]
        parts.append(f"**{q}**\n{content_preview}...")
    return "\n\n".join(parts)


def _assemble_markdown_report(
    topic: str,
    introduction: str,
    sections: List[dict],
    conclusion: str,
    bibliography: List[str],
    all_sources: Dict,
    credible_sources: Dict,
    discarded_sources: Dict,
) -> str:
    now = datetime.now().strftime("%d/%m/%Y")
    total_credible = sum(len(v) for v in credible_sources.values())
    total_discarded = sum(len(v) for v in discarded_sources.values())

    lines = []

    # Title
    lines.append(f"# {topic}")
    lines.append(f"\n*Được tạo bởi AI Research Agent — {now}*\n")

    # Table of Contents
    lines.append("## Mục lục\n")
    lines.append("1. [Giới thiệu](#giới-thiệu)")
    for i, s in enumerate(sections, 2):
        q = s.get("sub_question", f"Phần {i}")
        anchor = _to_anchor(q)
        lines.append(f"{i}. [{q}](#{anchor})")
    lines.append(f"{len(sections)+2}. [Kết luận](#kết-luận)")
    lines.append(f"{len(sections)+3}. [Báo cáo chất lượng nguồn](#báo-cáo-chất-lượng-nguồn)")
    lines.append(f"{len(sections)+4}. [Tài liệu tham khảo](#tài-liệu-tham-khảo)")
    lines.append("")

    # Introduction
    lines.append("## Giới thiệu\n")
    lines.append(introduction)
    lines.append("")

    # Sections
    for s in sections:
        q = s.get("sub_question", "")
        content = s.get("content", "")
        citations = s.get("citations", [])

        lines.append(f"## {q}\n")
        lines.append(content)
        lines.append("")

        # Inline source notes for this section
        if citations:
            lines.append("> **Nguồn sử dụng trong phần này:**")
            for c in citations:
                lines.append(f"> - [{c['title'] or c['url']}]({c['url']}) — Điểm: {c.get('score', '?'):.1f}/10")
            lines.append("")

    # Conclusion
    lines.append("## Kết luận\n")
    lines.append(conclusion)
    lines.append("")

    # Source Quality Report
    lines.append("## Báo cáo chất lượng nguồn\n")
    lines.append(f"**Tổng số nguồn đánh giá:** {total_credible + total_discarded}")
    lines.append(f"**Nguồn đáng tin cậy (ngưỡng ≥ {settings.credibility_threshold}):** {total_credible}")
    lines.append(f"**Nguồn bị loại:** {total_discarded}\n")

    if all_sources:
        lines.append("### Nguồn đáng tin cậy\n")
        lines.append("| # | Tiêu đề | Điểm | Tên miền | Thời sự | Chất lượng |")
        lines.append("|---|---------|------|----------|---------|------------|")
        credible_list = [s for s in all_sources.values() if s.get("is_credible")]
        credible_list.sort(key=lambda x: x.get("total_score", 0), reverse=True)
        for i, s in enumerate(credible_list, 1):
            title = (s.get("title") or s.get("url", ""))[:50]
            lines.append(
                f"| {i} | [{title}]({s.get('url', '#')}) | "
                f"**{s.get('total_score', 0):.1f}** | "
                f"{s.get('domain_score', 0):.1f} | "
                f"{s.get('recency_score', 0):.1f} | "
                f"{s.get('llm_judge_score', 0):.1f} |"
            )
        lines.append("")

        # Discarded sources with reasons
        discarded_list = [s for s in all_sources.values() if not s.get("is_credible")]
        if discarded_list:
            lines.append("### Nguồn bị loại\n")
            lines.append("<details><summary>Nhấn để xem nguồn bị loại</summary>\n")
            for s in discarded_list:
                title = (s.get("title") or s.get("url", ""))[:60]
                lines.append(f"- **[{title}]({s.get('url', '#')})** — Điểm: {s.get('total_score', 0):.1f}/10")
                lines.append(f"  > {s.get('explanation', 'Không có giải thích')}")
            lines.append("</details>\n")

    # Bibliography
    lines.append("## Tài liệu tham khảo\n")
    for i, ref in enumerate(bibliography, 1):
        lines.append(f"{i}. {ref}")
    lines.append("")

    return "\n".join(lines)


def _build_bibliography(all_sources: Dict, sections: List[dict]) -> List[str]:
    """Build APA-style bibliography from cited sources."""
    used_ids = set()
    for s in sections:
        for c in s.get("citations", []):
            used_ids.add(c["source_id"])

    refs = []
    for sid, source in all_sources.items():
        if sid not in used_ids and source.get("is_credible"):
            used_ids.add(sid)

    for sid in used_ids:
        source = all_sources.get(sid)
        if not source:
            continue
        ref = _format_apa(source)
        refs.append(ref)

    return sorted(refs)


def _format_apa(source: dict) -> str:
    """Format a source in APA style."""
    title = source.get("title", "Untitled")
    url = source.get("url", "")
    date = source.get("published_date", "n.d.")
    if date and len(str(date)) == 4:
        year = date
    elif date:
        try:
            from dateutil import parser as dateparser
            year = str(dateparser.parse(str(date)).year)
        except Exception:
            year = str(date)
    else:
        year = "n.d."

    domain = ""
    try:
        import tldextract
        ext = tldextract.extract(url)
        domain = f"{ext.domain}.{ext.suffix}".title()
    except Exception:
        domain = url[:30]

    return f"{domain}. ({year}). *{title}*. Retrieved from {url}"


def _to_anchor(text: str) -> str:
    return re.sub(r'[^a-z0-9-]', '', text.lower().replace(' ', '-'))
