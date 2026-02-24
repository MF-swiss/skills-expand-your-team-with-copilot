"""
Tests for the Mergington High School Activities API
"""

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


# Sample activity data used across tests
SAMPLE_ACTIVITIES = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Mondays and Fridays, 3:15 PM - 4:45 PM",
        "schedule_details": {"days": ["Monday", "Friday"], "start_time": "15:15", "end_time": "16:45"},
        "max_participants": 12,
        "participants": ["student1@mergington.edu"],
    },
    "Art Club": {
        "description": "Explore various art techniques and create masterpieces",
        "schedule": "Thursdays, 3:15 PM - 5:00 PM",
        "schedule_details": {"days": ["Thursday"], "start_time": "15:15", "end_time": "17:00"},
        "max_participants": 15,
        "participants": [],
    },
}


def _make_activity_doc(name, details):
    """Return a MongoDB-style document with _id set to the activity name."""
    doc = {"_id": name, **details}
    return doc


def _activity_cursor(activities=None):
    """Return a mock MongoDB cursor for the given activities dict."""
    if activities is None:
        activities = SAMPLE_ACTIVITIES
    return [_make_activity_doc(name, details) for name, details in activities.items()]


def get_client():
    """Create a TestClient with MongoDB mocked out."""
    with patch("src.backend.database.MongoClient") as mock_mongo:
        # Set up the mock database collections
        mock_db = MagicMock()
        mock_mongo.return_value.__getitem__.return_value = mock_db

        mock_activities = MagicMock()
        mock_teachers = MagicMock()
        mock_db.__getitem__.side_effect = lambda name: (
            mock_activities if name == "activities" else mock_teachers
        )

        # Pretend the database is already populated
        mock_activities.count_documents.return_value = len(SAMPLE_ACTIVITIES)
        mock_teachers.count_documents.return_value = 1

        from src.app import app
        return TestClient(app), mock_activities, mock_teachers


# ---------------------------------------------------------------------------
# Activity endpoint tests
# ---------------------------------------------------------------------------

def test_get_activities_returns_200():
    """GET /activities should return HTTP 200."""
    with patch("src.backend.routers.activities.activities_collection") as mock_col:
        mock_col.find.return_value = _activity_cursor()
        client, _, _ = get_client()
        response = client.get("/activities")
        assert response.status_code == 200


def test_get_activities_returns_dict():
    """GET /activities should return a dictionary of activities."""
    with patch("src.backend.routers.activities.activities_collection") as mock_col:
        mock_col.find.return_value = _activity_cursor()
        client, _, _ = get_client()
        response = client.get("/activities")
        data = response.json()
        assert isinstance(data, dict)


def test_signup_requires_teacher():
    """POST /activities/{name}/signup without teacher should return 401."""
    client, _, _ = get_client()
    with patch("src.backend.routers.activities.activities_collection"):
        response = client.post(
            "/activities/Chess Club/signup",
            params={"email": "new@mergington.edu"},
        )
    assert response.status_code == 401


def test_signup_for_activity():
    """POST /activities/{name}/signup with valid teacher should succeed."""
    client, _, _ = get_client()

    mock_teacher = {"_id": "mchen", "display_name": "Mr. Chen", "role": "teacher"}
    mock_activity = _make_activity_doc("Chess Club", SAMPLE_ACTIVITIES["Chess Club"])

    with (
        patch("src.backend.routers.activities.teachers_collection") as mock_teachers,
        patch("src.backend.routers.activities.activities_collection") as mock_activities,
    ):
        mock_teachers.find_one.return_value = mock_teacher
        mock_activities.find_one.return_value = mock_activity
        mock_activities.update_one.return_value = MagicMock(modified_count=1)

        response = client.post(
            "/activities/Chess Club/signup",
            params={"email": "newstudent@mergington.edu", "teacher_username": "mchen"},
        )

    assert response.status_code == 200
    assert "newstudent@mergington.edu" in response.json()["message"]


def test_signup_duplicate_student():
    """Signing up a student who is already enrolled should return 400."""
    client, _, _ = get_client()

    mock_teacher = {"_id": "mchen", "display_name": "Mr. Chen", "role": "teacher"}
    mock_activity = _make_activity_doc("Chess Club", SAMPLE_ACTIVITIES["Chess Club"])

    with (
        patch("src.backend.routers.activities.teachers_collection") as mock_teachers,
        patch("src.backend.routers.activities.activities_collection") as mock_activities,
    ):
        mock_teachers.find_one.return_value = mock_teacher
        mock_activities.find_one.return_value = mock_activity

        # "student1@mergington.edu" is already in the participants list
        response = client.post(
            "/activities/Chess Club/signup",
            params={"email": "student1@mergington.edu", "teacher_username": "mchen"},
        )

    assert response.status_code == 400


def test_unregister_from_activity():
    """POST /activities/{name}/unregister should remove an enrolled student."""
    client, _, _ = get_client()

    mock_teacher = {"_id": "mchen", "display_name": "Mr. Chen", "role": "teacher"}
    mock_activity = _make_activity_doc("Chess Club", SAMPLE_ACTIVITIES["Chess Club"])

    with (
        patch("src.backend.routers.activities.teachers_collection") as mock_teachers,
        patch("src.backend.routers.activities.activities_collection") as mock_activities,
    ):
        mock_teachers.find_one.return_value = mock_teacher
        mock_activities.find_one.return_value = mock_activity
        mock_activities.update_one.return_value = MagicMock(modified_count=1)

        response = client.post(
            "/activities/Chess Club/unregister",
            params={"email": "student1@mergington.edu", "teacher_username": "mchen"},
        )

    assert response.status_code == 200


def test_unregister_not_enrolled():
    """Unregistering a student who is not enrolled should return 400."""
    client, _, _ = get_client()

    mock_teacher = {"_id": "mchen", "display_name": "Mr. Chen", "role": "teacher"}
    mock_activity = _make_activity_doc("Chess Club", SAMPLE_ACTIVITIES["Chess Club"])

    with (
        patch("src.backend.routers.activities.teachers_collection") as mock_teachers,
        patch("src.backend.routers.activities.activities_collection") as mock_activities,
    ):
        mock_teachers.find_one.return_value = mock_teacher
        mock_activities.find_one.return_value = mock_activity

        response = client.post(
            "/activities/Chess Club/unregister",
            params={"email": "nothere@mergington.edu", "teacher_username": "mchen"},
        )

    assert response.status_code == 400


def test_activity_not_found():
    """Signing up for a non-existent activity should return 404."""
    client, _, _ = get_client()

    mock_teacher = {"_id": "mchen", "display_name": "Mr. Chen", "role": "teacher"}

    with (
        patch("src.backend.routers.activities.teachers_collection") as mock_teachers,
        patch("src.backend.routers.activities.activities_collection") as mock_activities,
    ):
        mock_teachers.find_one.return_value = mock_teacher
        mock_activities.find_one.return_value = None

        response = client.post(
            "/activities/Nonexistent Club/signup",
            params={"email": "student@mergington.edu", "teacher_username": "mchen"},
        )

    assert response.status_code == 404
