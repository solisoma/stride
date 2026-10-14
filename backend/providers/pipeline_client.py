import os
from utils.tracing import trace_client
from openai import OpenAI


def create_pipeline_client(settings):
    if settings.ollama_enabled:
        return trace_client(OpenAI(base_url=settings.base_url or 'http://localhost:11434/v1', api_key=settings.api_key or 'ollama', timeout=float(os.getenv('LLM_TIMEOUT_SECONDS', '30')), max_retries=0), 'pipeline')
    if not settings.api_key:
        raise ValueError('Configure LLM_API_KEY for semantic ingestion and retrieval')
    return trace_client(OpenAI(api_key=settings.api_key, base_url=settings.base_url, timeout=float(os.getenv('LLM_TIMEOUT_SECONDS', '30')), max_retries=0), 'pipeline')
