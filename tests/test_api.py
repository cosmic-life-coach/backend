"""API-level tests: auth middleware, error envelope, chat flow, Swagger docs."""

import json

import dependencies
from services.rag_orchestrator import RagOrchestrator


class FakeRag:
    """Stand-in orchestrator: no Gemini/Pinecone/Firestore calls."""

    def answer(self, uid, chat_title, message):
        return {"answer": f"echo:{message}", "vector_id": f"{uid}_{chat_title}_001"}

    def stream_answer(self, uid, chat_title, message):
        yield {"type": "chunk", "text": "Hello "}
        yield {"type": "chunk", "text": "world"}
        yield {"type": "done", "vector_id": f"{uid}_{chat_title}_001"}


def test_health_is_public(client):
    """/health must respond without any Authorization header."""
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_swagger_docs_generate(client):
    """OpenAPI schema builds and includes the chat route (Swagger works)."""
    res = client.get("/openapi.json")
    assert res.status_code == 200
    assert "/api/v1/chat" in res.json()["paths"]


def test_missing_token_returns_envelope(client):
    """Protected routes without a Bearer token -> 401 + standard envelope."""
    res = client.post("/api/v1/chat", json={"chat_title": "t", "message": "hi"})
    assert res.status_code == 401
    body = res.json()
    assert body["success"] is False
    assert body["error"]["code"] == "MISSING_TOKEN"


def test_validation_error_envelope(client):
    """Bad payload -> 422 VALIDATION_ERROR in the standard envelope."""
    res = client.post(
        "/api/v1/chat?stream=false",
        json={"chat_title": ""},  # missing message, empty title
        headers={"Authorization": "Bearer fake"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_chat_json_mode(app, client):
    """?stream=false returns a plain JSON answer with the vector ID."""
    app.dependency_overrides[dependencies.get_rag_orchestrator] = lambda: FakeRag()
    res = client.post(
        "/api/v1/chat?stream=false",
        json={"chat_title": "goals", "message": "hi"},
        headers={"Authorization": "Bearer fake"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["answer"] == "echo:hi"
    assert body["vector_id"] == "test_uid_goals_001"


def test_chat_sse_stream(app, client):
    """Default mode streams SSE frames ending with a 'done' event."""
    app.dependency_overrides[dependencies.get_rag_orchestrator] = lambda: FakeRag()
    res = client.post(
        "/api/v1/chat",
        json={"chat_title": "goals", "message": "hi"},
        headers={"Authorization": "Bearer fake"},
    )
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")

    events = [
        json.loads(line.removeprefix("data: "))
        for line in res.text.splitlines()
        if line.startswith("data: ")
    ]
    assert [e["type"] for e in events] == ["chunk", "chunk", "done"]
    assert events[-1]["vector_id"] == "test_uid_goals_001"


def test_service_unavailable_envelope(app, client):
    """A dead backend surfaces as 503 with a clear 'not connected' message."""
    from utils.error_handlers import ServiceUnavailableError

    class DeadRag:
        def answer(self, *args):
            raise ServiceUnavailableError("Pinecone", RuntimeError("conn refused"))

    app.dependency_overrides[dependencies.get_rag_orchestrator] = lambda: DeadRag()
    res = client.post(
        "/api/v1/chat?stream=false",
        json={"chat_title": "goals", "message": "hi"},
        headers={"Authorization": "Bearer fake"},
    )
    assert res.status_code == 503
    body = res.json()
    assert body["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert "Pinecone" in body["error"]["message"]
