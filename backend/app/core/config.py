from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os


class Settings(BaseSettings):
    # LLM
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    nvidia_api_key: Optional[str] = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "meta/llama-3.3-70b-instruct"
    default_llm_provider: str = "anthropic"

    # Search
    tavily_api_key: Optional[str] = None

    # Databases
    postgres_url: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/research_agent"
    redis_url: str = "redis://redis:6379"
    chroma_persist_dir: str = "/data/chroma"

    # App limits
    max_search_calls: int = 15
    max_retry_loops: int = 2
    credibility_threshold: float = 5.0
    min_credible_sources_per_question: int = 2
    search_timeout: int = 30
    scrape_timeout: int = 15

    # Embedding
    default_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Logging
    log_level: str = "INFO"

    model_config = {"env_file": [".env.local", ".env"], "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()


def get_llm_client(provider: Optional[str] = None):
    """Factory function to get LLM client."""
    p = provider or settings.default_llm_provider

    if p == "nvidia" and settings.nvidia_api_key:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.nvidia_model,
            api_key=settings.nvidia_api_key,
            base_url=settings.nvidia_base_url,
            temperature=0.1,
            max_tokens=8000,
        )
    elif p == "anthropic" and settings.anthropic_api_key:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model="claude-opus-5-20251101",
            api_key=settings.anthropic_api_key,
            temperature=0.1,
            max_tokens=8000,
        )
    elif settings.openai_api_key:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model="gpt-4o",
            api_key=settings.openai_api_key,
            temperature=0.1,
            max_tokens=8000,
        )
    elif settings.nvidia_api_key:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.nvidia_model,
            api_key=settings.nvidia_api_key,
            base_url=settings.nvidia_base_url,
            temperature=0.1,
            max_tokens=8000,
        )
    raise ValueError("No valid LLM API key found. Set NVIDIA_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY.")
