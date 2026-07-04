# Life Coach Backend

FastAPI backend for the Daily Life Coach app — Vedic astrology (Swiss Ephemeris) + Gemini RAG over Pinecone, Firebase Auth/Firestore, Google Calendar and FCM push.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.local.example .env.local        # fill in real keys
# place your Firebase service-account JSON at the path set in .env.local
uvicorn main:app --reload
```

Swagger UI: http://localhost:8000/docs

## Architecture

```
Flutter ── Bearer idToken ──> FirebaseAuthMiddleware (uid) ──> /api/v1 routers
routers ──> services (Gemini / astrology / RAG / calendar / FCM)
services ──> repositories (Firestore /users/{uid}, Pinecone namespaces)
prompts/*.yaml ──> config/prompt_loader.py (never hardcoded)
```

- **Vector IDs:** `uid_chat_title_chatnumber` (e.g. `usr_9f82a_vedic_remedies_001`)
- **Pinecone namespaces:** `memory` (chart facts, goals) / `chat_history` (conversation)
- **Chat streaming:** `POST /api/v1/chat` streams SSE by default; `?stream=false` for JSON
- **Errors:** always `{"success": false, "error": {"code", "message", "detail"}}`; unreachable backends → 503 naming the dead service

## Key endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | /api/v1/chat | Coach chat (SSE stream / JSON) |
| POST/GET | /api/v1/users/me/profile | Birth details + computed chart |
| GET | /api/v1/recommendations/daily | Daily Vedic guidance |
| GET | /api/v1/calendar/oauth/url | Connect Google Calendar |
| GET/POST | /api/v1/calendar/events | Read / write events |
| POST | /api/v1/notifications/token | Register device FCM token |
| POST | /api/v1/notifications/send | Push notification via FCM |
| GET | /health | Liveness (public) |

## Tests

```bash
pytest -q
```
