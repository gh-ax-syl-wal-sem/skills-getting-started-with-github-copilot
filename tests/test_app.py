"""
Test suite for Mergington High School Activities API
"""

import pytest
from fastapi.testclient import TestClient
from src.app import app, activities


@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_activities():
    """Reset activities data before each test"""
    # Store original state
    original_activities = {
        name: {
            "description": details["description"],
            "schedule": details["schedule"],
            "max_participants": details["max_participants"],
            "participants": details["participants"].copy()
        }
        for name, details in activities.items()
    }
    
    yield
    
    # Restore original state after test
    for name, details in original_activities.items():
        activities[name]["participants"] = details["participants"].copy()


class TestRootEndpoint:
    """Tests for the root endpoint"""
    
    def test_root_redirects_to_static(self, client):
        """Test that root URL redirects to static index.html"""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/static/index.html"


class TestGetActivities:
    """Tests for GET /activities endpoint"""
    
    def test_get_all_activities(self, client):
        """Test retrieving all activities"""
        response = client.get("/activities")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
        assert len(data) > 0
        assert "Chess Club" in data
        assert "Programming Class" in data
    
    def test_activity_structure(self, client):
        """Test that each activity has the required fields"""
        response = client.get("/activities")
        data = response.json()
        
        for activity_name, details in data.items():
            assert "description" in details
            assert "schedule" in details
            assert "max_participants" in details
            assert "participants" in details
            assert isinstance(details["participants"], list)
            assert isinstance(details["max_participants"], int)


class TestSignupEndpoint:
    """Tests for POST /activities/{activity_name}/signup endpoint"""
    
    def test_signup_success(self, client):
        """Test successful signup for an activity"""
        response = client.post(
            "/activities/Chess%20Club/signup?email=test@mergington.edu"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "test@mergington.edu" in data["message"]
        assert "Chess Club" in data["message"]
        
        # Verify the participant was added
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert "test@mergington.edu" in activities_data["Chess Club"]["participants"]
    
    def test_signup_nonexistent_activity(self, client):
        """Test signup for an activity that doesn't exist"""
        response = client.post(
            "/activities/NonExistent%20Activity/signup?email=test@mergington.edu"
        )
        assert response.status_code == 404
        assert "Activity not found" in response.json()["detail"]
    
    def test_signup_duplicate_prevention(self, client):
        """Test that duplicate signups are prevented"""
        email = "duplicate@mergington.edu"
        activity = "Chess Club"
        
        # First signup should succeed
        response1 = client.post(
            f"/activities/{activity}/signup?email={email}"
        )
        assert response1.status_code == 200
        
        # Second signup should fail
        response2 = client.post(
            f"/activities/{activity}/signup?email={email}"
        )
        assert response2.status_code == 400
        assert "already signed up" in response2.json()["detail"].lower()
    
    def test_signup_already_in_another_activity(self, client):
        """Test that a student already in one activity cannot join another"""
        email = "busy@mergington.edu"
        
        # Sign up for first activity
        response1 = client.post(
            "/activities/Chess%20Club/signup?email=" + email
        )
        assert response1.status_code == 200
        
        # Try to sign up for second activity
        response2 = client.post(
            "/activities/Programming%20Class/signup?email=" + email
        )
        assert response2.status_code == 400
        assert "already signed up" in response2.json()["detail"].lower()


class TestUnregisterEndpoint:
    """Tests for DELETE /activities/{activity_name}/participant endpoint"""
    
    def test_unregister_success(self, client):
        """Test successful unregistration of a participant"""
        email = "toremove@mergington.edu"
        activity = "Chess Club"
        
        # First, sign up the participant
        client.post(f"/activities/{activity}/signup?email={email}")
        
        # Then unregister them
        response = client.delete(
            f"/activities/{activity}/participant?email={email}"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert email in data["message"]
        
        # Verify the participant was removed
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert email not in activities_data[activity]["participants"]
    
    def test_unregister_nonexistent_activity(self, client):
        """Test unregistering from an activity that doesn't exist"""
        response = client.delete(
            "/activities/NonExistent%20Activity/participant?email=test@mergington.edu"
        )
        assert response.status_code == 404
        assert "Activity not found" in response.json()["detail"]
    
    def test_unregister_nonexistent_participant(self, client):
        """Test unregistering a participant who isn't signed up"""
        response = client.delete(
            "/activities/Chess%20Club/participant?email=notregistered@mergington.edu"
        )
        assert response.status_code == 404
        assert "Participant not found" in response.json()["detail"]
    
    def test_unregister_existing_participant(self, client):
        """Test unregistering a participant who was already in the activity"""
        # Use an existing participant from the initial data
        email = "michael@mergington.edu"
        activity = "Chess Club"
        
        # Verify participant exists
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert email in activities_data[activity]["participants"]
        
        # Unregister the participant
        response = client.delete(
            f"/activities/{activity}/participant?email={email}"
        )
        assert response.status_code == 200
        
        # Verify removal
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert email not in activities_data[activity]["participants"]


class TestDataIntegrity:
    """Tests for data integrity and edge cases"""
    
    def test_participant_count_updates(self, client):
        """Test that participant count is accurately reflected"""
        activity = "Art Club"
        
        # Get initial count
        response = client.get("/activities")
        initial_count = len(response.json()[activity]["participants"])
        
        # Add a participant
        client.post(f"/activities/{activity}/signup?email=newstudent@mergington.edu")
        
        # Verify count increased
        response = client.get("/activities")
        new_count = len(response.json()[activity]["participants"])
        assert new_count == initial_count + 1
        
        # Remove a participant
        client.delete(f"/activities/{activity}/participant?email=newstudent@mergington.edu")
        
        # Verify count decreased
        response = client.get("/activities")
        final_count = len(response.json()[activity]["participants"])
        assert final_count == initial_count
    
    def test_multiple_activities_independence(self, client):
        """Test that changes to one activity don't affect others"""
        email = "independent@mergington.edu"
        
        # Sign up for one activity
        client.post("/activities/Chess%20Club/signup?email=" + email)
        
        # Verify it doesn't appear in other activities
        response = client.get("/activities")
        data = response.json()
        
        assert email in data["Chess Club"]["participants"]
        assert email not in data["Programming Class"]["participants"]
        assert email not in data["Gym Class"]["participants"]
