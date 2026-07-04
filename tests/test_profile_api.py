"""API tests for the structured-chart profile endpoints (PR: structured-chart-api)."""

import dependencies


class FakeUsers:
    """In-memory stand-in for FirestoreUserRepository."""

    def __init__(self):
        self.profiles: dict[str, dict] = {}
        self.insights: dict[str, dict] = {}

    def get_profile(self, uid):
        return self.profiles.get(uid)

    def save_profile(self, uid, profile):
        self.profiles[uid] = profile

    def get_chart_insights(self, uid):
        return self.insights.get(uid)

    def save_chart_insights(self, uid, insights):
        self.insights[uid] = insights


class FakeRag:
    """Returns canned insights without touching Gemini."""

    def chart_insights(self, chart_summary):
        return {"headline": "Test Lagna", "summary": "ok", "placements": {}}


VALID_PROFILE = {
    "name": "Arjun Mehta",
    "dob": "1998-03-21",
    "birth_time": "14:35",
    "birth_place": "Jaipur, India",
    "lat": 26.91,
    "lon": 75.79,
    "tz_offset": 5.5,
}


def _wire(app, users, rag):
    app.dependency_overrides[dependencies.get_user_repository] = lambda: users
    app.dependency_overrides[dependencies.get_rag_orchestrator] = lambda: rag


def test_save_profile_returns_structured_chart(app, client):
    """POST returns chart JSON with all 9 grahas + ascendant + insights."""
    users, rag = FakeUsers(), FakeRag()
    _wire(app, users, rag)

    res = client.post(
        "/api/v1/users/me/profile",
        json=VALID_PROFILE,
        headers={"Authorization": "Bearer fake"},
    )
    assert res.status_code == 200
    body = res.json()

    chart = body["chart"]
    assert set(chart["planets"].keys()) == {
        "Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu",
    }
    assert "sign" in chart["ascendant"]
    assert body["insights"]["headline"] == "Test Lagna"
    assert users.insights["test_uid"]["headline"] == "Test Lagna"  # persisted


def test_get_profile_includes_chart_and_stored_insights(app, client):
    """GET recomputes the chart and returns insights from Firestore."""
    users, rag = FakeUsers(), FakeRag()
    users.profiles["test_uid"] = VALID_PROFILE
    users.insights["test_uid"] = {"headline": "Stored"}
    _wire(app, users, rag)

    res = client.get(
        "/api/v1/users/me/profile", headers={"Authorization": "Bearer fake"}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["chart"]["planets"]["Moon"]["nakshatra"]
    assert body["insights"] == {"headline": "Stored"}


def test_save_profile_survives_gemini_outage(app, client):
    """Insights generation failing must not block the profile save."""

    class DeadRag:
        def chart_insights(self, chart_summary):
            return None  # rag.chart_insights already soft-fails to None

    users = FakeUsers()
    _wire(app, users, DeadRag())

    res = client.post(
        "/api/v1/users/me/profile",
        json=VALID_PROFILE,
        headers={"Authorization": "Bearer fake"},
    )
    assert res.status_code == 200
    assert res.json()["insights"] is None
    assert users.profiles["test_uid"]["name"] == "Arjun Mehta"  # still saved
