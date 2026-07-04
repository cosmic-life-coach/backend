"""
Shared test fixtures.

Injects dummy environment variables and disables real Firebase initialization
so the full FastAPI app can be built without any live credentials.
"""

import os
import sys
from pathlib import Path

import pytest

# Make the project root importable when pytest runs from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Dummy env so pydantic-settings validation passes in tests.
os.environ.update({
    "GEMINI_API_KEY": "test-key",
    "PINECONE_API_KEY": "test-key",
    "FIREBASE_SERVICE_ACCOUNT_PATH": "/tmp/fake-service-account.json",
    "GOOGLE_OAUTH_CLIENT_ID": "test-client",
    "GOOGLE_OAUTH_CLIENT_SECRET": "test-secret",
    "GOOGLE_OAUTH_REDIRECT_URI": "http://localhost:8000/api/v1/calendar/oauth/callback",
})


@pytest.fixture
def app(monkeypatch):
    """Build the FastAPI app with Firebase initialization stubbed out."""
    import dependencies

    monkeypatch.setattr(dependencies, "init_firebase", lambda: None)

    # main.create_app re-imports init_firebase from dependencies at call time,
    # so patching the module attribute above is sufficient.
    from main import create_app

    return create_app()


@pytest.fixture
def client(app, monkeypatch):
    """TestClient with Firebase token verification mocked to uid 'test_uid'."""
    from fastapi.testclient import TestClient
    import firebase_admin.auth as fb_auth

    monkeypatch.setattr(fb_auth, "verify_id_token", lambda token: {"uid": "test_uid"})
    return TestClient(app, raise_server_exceptions=False)
