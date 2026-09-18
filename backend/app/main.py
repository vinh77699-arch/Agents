"""FastAPI application entry point."""
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.documents import router as docs_router
from app.api.routes import router as research_router
from app.core.config import settings
from app.core.database import init_db

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AI Research Agent backend starting up...")
    import os
    os.makedirs(settings.chroma_persist_dir, exist_ok=True)
    await init_db()
    logger.info(f"Credibility threshold: {settings.credibility_threshold}")
    yield
    logger.info("Backend shutting down...")


app = FastAPI(
    title="AI Research Agent API",
    description="Multi-agent research report generator with credibility scoring, auth, and document library",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(research_router, prefix="/api/v1")
app.include_router(docs_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"name": "AI Research Agent", "version": "2.0.0", "docs": "/docs"}
