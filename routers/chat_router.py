"""
Chat endpoints -- the core coaching conversation.

POST /api/v1/chat streams the Gemini reply over Server-Sent Events (SSE)
by default: the Flutter app renders the first token in well under a second.
Pass ?stream=false for a plain JSON response.
"""

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from dependencies import get_rag_orchestrator
from middleware.auth_middleware import get_current_uid
from schemas.chat_schemas import ChatRequest, ChatResponse
from services.rag_orchestrator import RagOrchestrator

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])


def _sse_event(payload: dict) -> str:
    """Format one dict as a Server-Sent Events `data:` frame."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post(
    "",
    summary="Send a message to the life coach",
    response_model=ChatResponse,
    responses={200: {"description": "SSE stream (default) or JSON when ?stream=false"}},
)
async def chat(
    body: ChatRequest,
    request: Request,
    stream: bool = True,
    rag: RagOrchestrator = Depends(get_rag_orchestrator),
):
    """
    RAG chat pipeline: embed -> retrieve (memory + chat_history) -> Gemini
    -> persist exchange with vector ID `uid_chat_title_chatnumber`.

    Streaming mode emits SSE frames:
        data: {"type": "chunk", "text": "..."}     (repeated)
        data: {"type": "done", "vector_id": "..."} (final)
    """
    uid = get_current_uid(request)

    if not stream:
        result = rag.answer(uid, body.chat_title, body.message)
        return ChatResponse(answer=result["answer"], vector_id=result["vector_id"])

    def event_stream():
        """Generator bridging the RAG stream into SSE frames."""
        try:
            for event in rag.stream_answer(uid, body.chat_title, body.message):
                yield _sse_event(event)
        except Exception as exc:  # errors mid-stream can't use HTTP status codes
            yield _sse_event({"type": "error", "message": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
