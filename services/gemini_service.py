"""
Gemini LLM service (Service pattern).

Thin wrapper around the official Google GenAI SDK (`google-genai`) providing:
  * streaming chat generation (token-by-token, feeds the SSE endpoint)
  * one-shot generation (non-stream fallback / daily recommendation)
  * text embeddings for Pinecone storage & retrieval
"""

import logging
from collections.abc import Iterator

from google import genai
from google.genai import types

from config.settings import get_settings
from utils.error_handlers import ServiceUnavailableError

logger = logging.getLogger(__name__)


class GeminiService:
    """Single entry point for all Gemini calls (chat + embeddings)."""

    def __init__(self):
        """Create the GenAI client with the API key from .env.local."""
        settings = get_settings()
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_model_name
        self._embedding_model = settings.gemini_embedding_model
        self._embedding_dim = settings.gemini_embedding_dimension

    def stream_chat(self, system_prompt: str, user_message: str) -> Iterator[str]:
        """
        Yield response text chunks as Gemini generates them.

        Used by the SSE chat endpoint so the Flutter app renders the first
        token in well under a second instead of waiting for the full reply.
        """
        try:
            stream = self._client.models.generate_content_stream(
                model=self._model,
                contents=user_message,
                config=types.GenerateContentConfig(system_instruction=system_prompt),
            )
            for chunk in stream:
                if chunk.text:
                    yield chunk.text
        except Exception as exc:
            raise ServiceUnavailableError("Gemini", exc) from exc

    def generate(self, system_prompt: str, user_message: str) -> str:
        """Return the full response text in one shot (non-streaming)."""
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=user_message,
                config=types.GenerateContentConfig(system_instruction=system_prompt),
            )
            return response.text or ""
        except Exception as exc:
            raise ServiceUnavailableError("Gemini", exc) from exc

    def embed_text(self, text: str) -> list[float]:
        """Return the embedding vector for `text` (dimension from settings)."""
        try:
            result = self._client.models.embed_content(
                model=self._embedding_model,
                contents=text,
                config=types.EmbedContentConfig(output_dimensionality=self._embedding_dim),
            )
            return list(result.embeddings[0].values)
        except Exception as exc:
            raise ServiceUnavailableError("Gemini (embeddings)", exc) from exc
