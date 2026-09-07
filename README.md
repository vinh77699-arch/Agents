# AI Agentic Research & Report Generator

Multi-agent system that takes a research topic, searches the web, evaluates source credibility, and generates a structured report with full citations.

## Architecture

```
User Input (Topic)
    │
    ▼
┌─────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│   PLANNER   │────▶│ SEARCH & SCRAPER │────▶│ CREDIBILITY EVAL    │
│   AGENT     │     │     AGENT        │     │      AGENT          │
│             │     │                  │     │                     │
│ Topic →     │     │ Parallel search: │     │ Score each source:  │
│ 4-6 sub-    │     │ Tavily + DDG +   │     │ • Domain authority  │
│ questions + │     │ Semantic Scholar │     │ • Recency           │
│ queries     │     │ + Trafilatura    │     │ • Cross-reference   │
└─────────────┘     └──────────────────┘     │ • LLM-as-judge      │
      ▲                                       └──────────┬──────────┘
      │                                                  │
      │  (retry if < 2 credible sources per question,    │ Filter threshold
      │   max 2 retries)                                 │
      └──────────────────────────────────────────────────┘
                                                         │
                                                         ▼
                                            ┌────────────────────┐
                                            │  SYNTHESIS AGENT   │
                                            │      (RAG)         │
                                            │                    │
                                            │ ChromaDB embed +   │
                                            │ retrieve + write   │
                                            │ with [source_id]   │
                                            └────────┬───────────┘
                                                     │
                                                     ▼
                                            ┌────────────────────┐
                                            │  REPORT WRITER     │
                                            │     AGENT          │
                                            │                    │
                                            │ TOC + sections +   │
                                            │ bibliography (APA) │
                                            └────────────────────┘
```

## Stack

| Layer | Technology |
|-------|-----------|
| Orchestration | LangGraph (state machine with retry loop) |
| LLM | Anthropic Claude / OpenAI GPT-4o |
| Search | Tavily API + DuckDuckGo fallback |
| Academic | Semantic Scholar API |
| Scraping | Trafilatura + httpx |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 |
| Vector DB | ChromaDB (local persistent) |
| Backend | FastAPI + SSE streaming |
| Frontend | Next.js 14 + Tailwind CSS |
| Infra | Docker Compose (Postgres + Redis + Chroma) |

## Quick Start

### Prerequisites
- Docker Desktop installed
- At least one API key: `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`

### 1. Configure API keys

```bash
cp .env.example .env
# Edit .env and add your API keys
```

### 2. Start with Docker Compose

```bash
docker compose up --build -d
```

### 3. Open the app

- **Frontend:** http://localhost:3000
- **API docs:** http://localhost:8000/docs

### Local Development (without Docker)

**Backend:**
```bash
cd backend
pip install -r requirements.txt
cp ../.env.example .env  # fill in keys
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

## Credibility Scoring

Each source is scored 0–10 on 4 criteria:

| Criterion | Weight | Description |
|-----------|--------|-------------|
| Domain Authority | 30% | Whitelist scoring: .gov/.edu = 9+, blogs = 4, etc. |
| Recency | 20% | Topic-adaptive: skipped for historical topics |
| Cross-reference | 15% | How many sub-questions the same source appears in |
| LLM-as-Judge | 35% | Rubric: author expertise, citations, bias signals |

Sources below threshold (default 5.0) are **discarded** and logged. If any sub-question has fewer than 2 credible sources, the pipeline retries with new search queries (max 2 retries).

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/research/stream` | POST | SSE stream of research events |
| `/api/v1/research/start` | POST | Start background research session |
| `/api/v1/research/{id}` | GET | Get session status and report |
| `/api/v1/health` | GET | Health check |

## Project Structure

```
D:\Agent\
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── planner.py          # Topic → sub-questions
│   │   │   ├── searcher.py         # Parallel search + scrape
│   │   │   ├── credibility.py      # 4-criterion scoring
│   │   │   ├── synthesizer.py      # RAG + citation tracking
│   │   │   └── report_writer.py    # Final assembly + APA bib
│   │   ├── core/
│   │   │   ├── config.py           # Settings + LLM factory
│   │   │   ├── state.py            # TypedDict state machine
│   │   │   └── pipeline.py         # LangGraph orchestration
│   │   ├── services/
│   │   │   ├── search.py           # Tavily + DuckDuckGo
│   │   │   ├── scraper.py          # Trafilatura extraction
│   │   │   └── vectorstore.py      # ChromaDB wrapper
│   │   ├── api/routes.py           # FastAPI endpoints + SSE
│   │   └── main.py                 # App entry point
│   └── Dockerfile
├── frontend/
│   └── src/
│       ├── app/page.tsx            # Main page with SSE client
│       └── components/
│           ├── ResearchForm.tsx    # Topic input
│           ├── PipelineProgress.tsx # Real-time agent status
│           ├── ReportViewer.tsx    # Markdown report + source tab
│           └── SourceCard.tsx      # Source credibility card
└── docker-compose.yml
```
