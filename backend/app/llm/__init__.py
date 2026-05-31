from ..config import get_settings
from .base import Answerer, Classification, Filter
from .claude import ClaudeAnswerer
from .gemini import GeminiFilter
from .mock import MockAnswerer, MockFilter


def get_filter() -> Filter:
    s = get_settings()
    return GeminiFilter() if s.gemini_api_key else MockFilter()


def get_answerer() -> Answerer:
    s = get_settings()
    return ClaudeAnswerer() if s.anthropic_api_key else MockAnswerer()


__all__ = [
    "Answerer",
    "Classification",
    "Filter",
    "get_filter",
    "get_answerer",
]
