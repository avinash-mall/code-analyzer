"""
Local LLM client module.
Provides OpenAI-compatible interface for local LLMs (Ollama, vLLM, etc.).
"""

from .client import LocalLLMClient

__all__ = ['LocalLLMClient']

