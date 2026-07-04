"""
RAG orchestrator (Service pattern).

Pipeline for every chat message:
    1. Embed the user message (Gemini embeddings).
    2. Retrieve relevant vectors from Pinecone:
         - "memory" namespace       -> long-term facts (chart, goals)
         - "chat_history" namespace -> recent conversation context
    3. Build the system prompt from /prompts/prompt.yml with retrieved context.
    4. Generate the answer with Gemini (streamed or one-shot).
    5. Persist the exchange back into "chat_history" with the mandatory
       vector ID format uid_chat_title_chatnumber.
"""

import logging
from collections.abc import Iterator
from datetime import date

from config.prompt_loader import get_prompt
from repositories.firestore_user_repository import FirestoreUserRepository
from repositories.pinecone_memory_handler import (
    NAMESPACE_CHAT_HISTORY,
    NAMESPACE_MEMORY,
    PineconeMemoryHandler,
    build_vector_id,
)
from services.astrology_engine_service import compute_birth_chart, summarize_chart_for_prompt
from services.gemini_service import GeminiService

logger = logging.getLogger(__name__)


class RagOrchestrator:
    """Coordinates repositories + Gemini for retrieval-augmented coaching."""

    def __init__(
        self,
        gemini: GeminiService,
        memory: PineconeMemoryHandler,
        users: FirestoreUserRepository,
    ):
        self._gemini = gemini
        self._memory = memory
        self._users = users

    # ---------- internal helpers ----------

    def _birth_chart_summary(self, uid: str) -> str:
        """Compute the user's chart from their stored profile (or explain absence)."""
        profile = self._users.get_profile(uid)
        if not profile or "dob" not in profile:
            return "No birth details on file. Ask the user for date, time and place of birth."
        try:
            from datetime import datetime

            birth_dt = datetime.fromisoformat(f"{profile['dob']}T{profile['birth_time']}")
            chart = compute_birth_chart(
                birth_dt, profile["tz_offset"], profile["lat"], profile["lon"]
            )
            return summarize_chart_for_prompt(chart)
        except Exception as exc:
            logger.warning("Chart computation failed for %s: %s", uid, exc)
            return "Birth chart could not be computed from stored details."

    def _retrieve_context(self, uid: str, query_embedding: list[float]) -> tuple[str, str]:
        """Query both namespaces and return (memories_text, history_text)."""
        memories = self._memory.query_similar(NAMESPACE_MEMORY, query_embedding, uid, top_k=5)
        history = self._memory.query_similar(
            NAMESPACE_CHAT_HISTORY, query_embedding, uid, top_k=5
        )
        mem_text = "\n".join(m["metadata"].get("text", "") for m in memories) or "None yet."
        hist_text = "\n".join(h["metadata"].get("text", "") for h in history) or "None yet."
        return mem_text, hist_text

    def _build_system_prompt(self, uid: str, query_embedding: list[float]) -> str:
        """Fill the YAML system prompt with chart + retrieved context."""
        memories, history = self._retrieve_context(uid, query_embedding)
        template = get_prompt("prompt.yml", "system_prompt")
        return template.format(
            birth_chart=self._birth_chart_summary(uid),
            memories=memories,
            chat_history=history,
        )

    def _store_exchange(
        self, uid: str, chat_title: str, user_message: str, answer: str,
        query_embedding: list[float],
    ) -> str:
        """Persist the Q/A pair to chat_history; returns the new vector ID."""
        chat_number = self._users.next_chat_number(uid, chat_title)
        vector_id = build_vector_id(uid, chat_title, chat_number)
        self._memory.upsert_vector(
            namespace=NAMESPACE_CHAT_HISTORY,
            vector_id=vector_id,
            embedding=query_embedding,
            metadata={
                "uid": uid,
                "chat_title": chat_title,
                "chat_number": chat_number,
                "text": f"User: {user_message}\nCoach: {answer}",
                "date": date.today().isoformat(),
            },
        )
        return vector_id

    # ---------- public API ----------

    def stream_answer(
        self, uid: str, chat_title: str, user_message: str
    ) -> Iterator[dict]:
        """
        Stream the coach's answer chunk-by-chunk for the SSE endpoint.

        Yields {"type": "chunk", "text": ...} events, then one final
        {"type": "done", "vector_id": ...} event after persistence.
        """
        query_embedding = self._gemini.embed_text(user_message)
        system_prompt = self._build_system_prompt(uid, query_embedding)

        answer_parts: list[str] = []
        for chunk in self._gemini.stream_chat(system_prompt, user_message):
            answer_parts.append(chunk)
            yield {"type": "chunk", "text": chunk}

        vector_id = self._store_exchange(
            uid, chat_title, user_message, "".join(answer_parts), query_embedding
        )
        yield {"type": "done", "vector_id": vector_id}

    def answer(self, uid: str, chat_title: str, user_message: str) -> dict:
        """Non-streaming variant: return the full answer plus its vector ID."""
        query_embedding = self._gemini.embed_text(user_message)
        system_prompt = self._build_system_prompt(uid, query_embedding)
        answer = self._gemini.generate(system_prompt, user_message)
        vector_id = self._store_exchange(uid, chat_title, user_message, answer, query_embedding)
        return {"answer": answer, "vector_id": vector_id}

    def chart_insights(self, chart_summary: str) -> dict | None:
        """
        Generate structured interpretation JSON for a computed chart.

        Gemini interprets (headline, summary, per-placement texts) -- it never
        computes positions; those come from the Swiss Ephemeris engine.
        Returns None instead of raising if generation or parsing fails, so a
        profile save never blocks on the LLM.
        """
        import json

        template = get_prompt("prompt_chart_insights.yaml", "system_prompt")
        try:
            raw = self._gemini.generate(
                template.format(birth_chart=chart_summary),
                "Generate the chart interpretation JSON.",
            )
            cleaned = raw.strip().removeprefix("```json").removesuffix("```").strip()
            parsed = json.loads(cleaned)
            return parsed if isinstance(parsed, dict) else None
        except Exception as exc:  # LLM down or malformed JSON -> degrade softly
            logger.warning("Chart insights generation failed: %s", exc)
            return None

    def daily_recommendation(self, uid: str, calendar_events_text: str) -> str:
        """Generate today's recommendation from chart + calendar context."""
        template = get_prompt("prompt_daily_recommendation.yaml", "system_prompt")
        system_prompt = template.format(
            birth_chart=self._birth_chart_summary(uid),
            today=date.today().isoformat(),
            calendar_events=calendar_events_text or "No events today.",
        )
        return self._gemini.generate(system_prompt, "Generate today's recommendation.")
