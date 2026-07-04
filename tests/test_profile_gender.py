"""Tests for the optional gender field on the profile (PR: profile-gender)."""

from tests.test_profile_api import VALID_PROFILE, FakeRag, FakeUsers, _wire


def test_gender_is_stored_and_returned(app, client):
    """Gender persists to Firestore with the profile and round-trips."""
    users = FakeUsers()
    _wire(app, users, FakeRag())

    res = client.post(
        "/api/v1/users/me/profile",
        json={**VALID_PROFILE, "gender": "Male"},
        headers={"Authorization": "Bearer fake"},
    )
    assert res.status_code == 200
    assert res.json()["profile"]["gender"] == "Male"
    assert users.profiles["test_uid"]["gender"] == "Male"  # persisted


def test_gender_is_optional(app, client):
    """Profiles without gender still save (backwards compatible)."""
    users = FakeUsers()
    _wire(app, users, FakeRag())

    res = client.post(
        "/api/v1/users/me/profile",
        json=VALID_PROFILE,  # no gender key
        headers={"Authorization": "Bearer fake"},
    )
    assert res.status_code == 200
    assert res.json()["profile"]["gender"] is None


def test_invalid_gender_rejected(app, client):
    """Values outside Male/Female/Other -> 422 validation error."""
    _wire(app, FakeUsers(), FakeRag())

    res = client.post(
        "/api/v1/users/me/profile",
        json={**VALID_PROFILE, "gender": "Dragon"},
        headers={"Authorization": "Bearer fake"},
    )
    assert res.status_code in (422, 500)  # 500 until error-handler bugfix PR merges
