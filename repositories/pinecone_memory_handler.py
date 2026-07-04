"""
Pinecone vector repository (Repository pattern).

Namespace strategy (strict isolation):
    "memory"       -- core extractions: birth chart facts, life goals.
    "chat_history" -- chronological conversation vectors.

Vector ID convention (mandatory): uid_chat_title_chatnumber
    e.g. usr_9f82a_vedic_remedies_001

Every query is metadata-filtered by `uid` as a second isolation layer on top
of namespaces.
"""

import logging
import re

from utils.error_handlers import ServiceUnavailableError

logger = logging.getLogger(__name__)

NAMESPACE_MEMORY = "memory"
NAMESPACE_CHAT_HISTORY = "chat_history"


def build_vector_id(uid: str, chat_title: str, chat_number: int) -> str:
    """
    Build a vector ID in the mandatory `uid_chat_title_chatnumber` format.

    The chat title is slugified (lowercase, underscores) and the number is
    zero-padded to 3 digits, e.g. usr_9f82a_vedic_remedies_001.
    """
    slug = re.sub(r"[^a-z0-9]+", "_", chat_title.lower()).strip("_")
    return f"{uid}_{slug}_{chat_number:03d}"


class PineconeMemoryHandler:
    """Upsert & semantic-query operations against the HNSW-indexed Pinecone index."""

    def __init__(self, index):
        """`index` is a pinecone Index handle created once at app startup."""
        self._index = index

    def upsert_vector(
        self,
        namespace: str,
        vector_id: str,
        embedding: list[float],
        metadata: dict,
    ) -> None:
        """
        Store one embedding with its metadata in the given namespace.

        Metadata always includes `uid` so queries can filter on it natively.
        """
        try:
            self._index.upsert(
                vectors=[{"id": vector_id, "values": embedding, "metadata": metadata}],
                namespace=namespace,
            )
        except Exception as exc:
            raise ServiceUnavailableError("Pinecone", exc) from exc

    def query_similar(
        self,
        namespace: str,
        embedding: list[float],
        uid: str,
        top_k: int = 5,
        extra_filter: dict | None = None,
    ) -> list[dict]:
        """
        Return the top_k most similar records for this user in a namespace.

        Combines the HNSW ANN search with a native metadata filter on uid
        (plus any extra filter, e.g. {"chat_title": "vedic_remedies"}).
        """
        metadata_filter = {"uid": {"$eq": uid}}
        if extra_filter:
            metadata_filter.update(extra_filter)

        try:
            result = self._index.query(
                vector=embedding,
                top_k=top_k,
                namespace=namespace,
                filter=metadata_filter,
                include_metadata=True,
            )
        except Exception as exc:
            raise ServiceUnavailableError("Pinecone", exc) from exc

        return [
            {"id": m["id"], "score": m["score"], "metadata": m.get("metadata", {})}
            for m in result.get("matches", [])
        ]
