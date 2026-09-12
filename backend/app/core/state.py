from typing import TypedDict, List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import time


class AgentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str
    content: str = ""
    published_date: Optional[str] = None
    source_id: str = ""

    def __post_init__(self):
        if not self.source_id:
            import hashlib
            self.source_id = hashlib.md5(self.url.encode()).hexdigest()[:8]


@dataclass
class CredibilityScore:
    source_id: str
    url: str
    title: str
    domain_score: float = 0.0       # 0-10
    recency_score: float = 0.0      # 0-10
    cross_ref_score: float = 0.0    # 0-10
    llm_judge_score: float = 0.0    # 0-10
    total_score: float = 0.0        # weighted
    explanation: str = ""
    is_credible: bool = False
    content: str = ""
    published_date: Optional[str] = None


@dataclass
class Citation:
    source_id: str
    sentence_id: str
    url: str
    title: str
    quote: str = ""


@dataclass
class SynthesizedSection:
    sub_question: str
    content: str
    citations: List[Citation] = field(default_factory=list)


@dataclass
class ProgressUpdate:
    agent: str
    status: AgentStatus
    message: str
    timestamp: float = field(default_factory=time.time)
    data: Optional[Dict[str, Any]] = None


class ResearchState(TypedDict):
    # Input
    topic: str
    session_id: str

    # Planner
    sub_questions: List[str]
    search_queries: Dict[str, List[str]]  # sub_question -> list of queries

    # Search & Scrape
    raw_results: Dict[str, List[Any]]  # sub_question -> List[SearchResult]
    search_calls_used: int

    # Credibility evaluation
    credible_sources: Dict[str, List[Any]]  # sub_question -> List[CredibilityScore]
    discarded_sources: Dict[str, List[Any]]  # sub_question -> List[CredibilityScore]
    retry_count: int

    # Synthesis
    synthesized_sections: List[Any]  # List[SynthesizedSection]
    all_sources: Dict[str, Any]  # source_id -> CredibilityScore

    # Report
    final_report: str
    bibliography: List[str]

    # Streaming progress
    progress: List[Any]  # List[ProgressUpdate]
    errors: List[str]
    status: str
