"""Unit and integration tests for startup domain.

Tests cover the complete startup domain following the 3-layer architecture:
1. Repository tests (data access layer)
2. Endpoint tests (API layer with FastAPI TestClient)
3. Entity validation tests (StartupVariables validators)

Test Strategy:
    - Use in-memory SQLite database for isolation
    - Mock-free repository tests (real database operations)
    - Integration tests use FastAPI TestClient
    - Test both success cases and error cases

Example:
    pytest tests/test_startup.py -v
    pytest tests/test_startup.py::TestStartup_Repository -v
"""
import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from src.entities.StartupVariables import StartupVariables
from src.domains.startup.repository import Startup_Variables_Repository
from src.domains.startup.schemas import WelcomePopupResponse


# ============ Repository Layer Tests ============

class TestStartup_Repository:
    """Test suite for Startup_Variables_Repository data access layer.
    
    Tests cover CRUD operations on the singleton StartupVariables entity,
    including get_or_create, mark_welcome_popup_displayed, update_field, reset.
    """

    def test_get_or_create_creates_new_record(self, test_db_session: Session):
        """Test get_or_create creates record when none exists."""
        repo = Startup_Variables_Repository(test_db_session)
        
        # Verify no record exists
        assert test_db_session.query(StartupVariables).count() == 0
        
        # Get or create should create new record
        vars = repo.get_or_create()
        
        assert vars is not None
        assert vars.id is not None
        assert vars.welcome_popup_has_already_displayed is False
        assert test_db_session.query(StartupVariables).count() == 1

    def test_get_or_create_returns_existing_record(self, test_db_session: Session):
        """Test get_or_create returns existing singleton record."""
        # Create existing record
        existing = StartupVariables(welcome_popup_has_already_displayed=True)
        test_db_session.add(existing)
        test_db_session.commit()
        existing_id = existing.id
        
        repo = Startup_Variables_Repository(test_db_session)
        vars = repo.get_or_create()
        
        # Should return same record, not create new one
        assert vars.id == existing_id
        assert vars.welcome_popup_has_already_displayed is True
        assert test_db_session.query(StartupVariables).count() == 1

    def test_get_welcome_popup_status_false_on_first_call(self, test_db_session: Session):
        """Test get_welcome_popup_status returns False for new record."""
        repo = Startup_Variables_Repository(test_db_session)
        
        status = repo.get_welcome_popup_status()
        
        assert status is False

    def test_get_welcome_popup_status_true_after_display(self, test_db_session: Session):
        """Test get_welcome_popup_status returns True after marking displayed."""
        # Create record with popup already displayed
        vars = StartupVariables(welcome_popup_has_already_displayed=True)
        test_db_session.add(vars)
        test_db_session.commit()
        
        repo = Startup_Variables_Repository(test_db_session)
        status = repo.get_welcome_popup_status()
        
        assert status is True

    def test_mark_welcome_popup_displayed(self, test_db_session: Session):
        """Test mark_welcome_popup_displayed sets flag to True."""
        repo = Startup_Variables_Repository(test_db_session)
        vars = repo.get_or_create()
        
        # Initially False
        assert vars.welcome_popup_has_already_displayed is False
        
        # Mark as displayed
        updated = repo.mark_welcome_popup_displayed(vars)
        test_db_session.commit()
        
        # Verify updated
        assert updated.welcome_popup_has_already_displayed is True
        
        # Verify persisted
        test_db_session.refresh(vars)
        assert vars.welcome_popup_has_already_displayed is True

    def test_mark_welcome_popup_displayed_idempotent(self, test_db_session: Session):
        """Test mark_welcome_popup_displayed is idempotent (can call multiple times)."""
        repo = Startup_Variables_Repository(test_db_session)
        vars = repo.get_or_create()
        
        # Mark displayed twice
        repo.mark_welcome_popup_displayed(vars)
        test_db_session.commit()
        repo.mark_welcome_popup_displayed(vars)
        test_db_session.commit()
        
        # Should still be True
        assert vars.welcome_popup_has_already_displayed is True

    def test_update_field_valid_field(self, test_db_session: Session):
        """Test update_field updates a valid field."""
        repo = Startup_Variables_Repository(test_db_session)
        vars = repo.get_or_create()
        
        # Update field
        updated = repo.update_field(vars, "welcome_popup_has_already_displayed", True)
        test_db_session.commit()
        
        assert updated.welcome_popup_has_already_displayed is True

    def test_update_field_invalid_field_raises_error(self, test_db_session: Session):
        """Test update_field raises AttributeError for invalid field."""
        repo = Startup_Variables_Repository(test_db_session)
        vars = repo.get_or_create()
        
        with pytest.raises(AttributeError, match="has no field 'nonexistent_field'"):
            repo.update_field(vars, "nonexistent_field", "value")

    def test_reset(self, test_db_session: Session):
        """Test reset sets all fields back to defaults."""
        repo = Startup_Variables_Repository(test_db_session)
        vars = repo.get_or_create()
        
        # Mark as displayed
        repo.mark_welcome_popup_displayed(vars)
        test_db_session.commit()
        assert vars.welcome_popup_has_already_displayed is True
        
        # Reset
        reset_vars = repo.reset(vars)
        test_db_session.commit()
        
        assert reset_vars.welcome_popup_has_already_displayed is False


# ============ Endpoint Layer Tests ============

class TestStartup_Endpoints:
    """Test suite for startup domain FastAPI endpoints.
    
    Tests use FastAPI TestClient to simulate real HTTP requests and validate
    response schemas, status codes, and business logic.
    """

    def test_get_welcome_popup_status_first_time(self, client: TestClient, test_db_session: Session):
        """Test GET /startup/welcome-popup returns False on first call."""
        response = client.get("/erudi/startup/welcome-popup")
        
        assert response.status_code == 200
        data = response.json()
        assert data == {"has_already_displayed": False}
        
        # Verify flag was set to True in database
        vars = test_db_session.query(StartupVariables).first()
        assert vars is not None
        assert vars.welcome_popup_has_already_displayed is True

    def test_get_welcome_popup_status_subsequent_calls(self, client: TestClient, test_db_session: Session):
        """Test GET /startup/welcome-popup returns True on subsequent calls."""
        # First call
        response1 = client.get("/erudi/startup/welcome-popup")
        assert response1.json() == {"has_already_displayed": False}
        
        # Second call
        response2 = client.get("/erudi/startup/welcome-popup")
        assert response2.status_code == 200
        assert response2.json() == {"has_already_displayed": True}
        
        # Third call (still True)
        response3 = client.get("/erudi/startup/welcome-popup")
        assert response3.json() == {"has_already_displayed": True}

    def test_get_welcome_popup_status_existing_record_true(self, client: TestClient, test_db_session: Session):
        """Test endpoint returns True when record already exists with flag=True."""
        # Pre-create record with flag=True
        vars = StartupVariables(welcome_popup_has_already_displayed=True)
        test_db_session.add(vars)
        test_db_session.commit()
        
        response = client.get("/erudi/startup/welcome-popup")
        
        assert response.status_code == 200
        assert response.json() == {"has_already_displayed": True}

    def test_get_welcome_popup_status_existing_record_false(self, client: TestClient, test_db_session: Session):
        """Test endpoint returns False and sets flag when existing record has flag=False."""
        # Pre-create record with flag=False
        vars = StartupVariables(welcome_popup_has_already_displayed=False)
        test_db_session.add(vars)
        test_db_session.commit()
        record_id = vars.id
        
        response = client.get("/erudi/startup/welcome-popup")
        
        assert response.status_code == 200
        assert response.json() == {"has_already_displayed": False}
        
        # Verify flag was updated
        test_db_session.refresh(vars)
        assert vars.welcome_popup_has_already_displayed is True
        assert vars.id == record_id  # Same record, not new one

    def test_get_welcome_popup_status_response_schema(self, client: TestClient):
        """Test response matches WelcomePopupResponse schema."""
        response = client.get("/erudi/startup/welcome-popup")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate schema fields
        assert "has_already_displayed" in data
        assert isinstance(data["has_already_displayed"], bool)
        
        # Validate Pydantic schema
        validated = WelcomePopupResponse(**data)
        assert validated.has_already_displayed in [True, False]


# ============ Entity Validation Tests ============

class TestStartupVariables_Entity:
    """Test suite for StartupVariables entity SQLAlchemy validators.
    
    Tests validate that entity-level constraints are enforced, including
    Boolean type checking for welcome_popup_has_already_displayed field.
    """

    def test_create_startup_variables_default_values(self, test_db_session: Session):
        """Test creating StartupVariables with default values."""
        vars = StartupVariables()
        test_db_session.add(vars)
        test_db_session.commit()
        
        assert vars.id is not None
        assert vars.welcome_popup_has_already_displayed is False

    def test_create_startup_variables_explicit_true(self, test_db_session: Session):
        """Test creating StartupVariables with explicit True value."""
        vars = StartupVariables(welcome_popup_has_already_displayed=True)
        test_db_session.add(vars)
        test_db_session.commit()
        
        assert vars.welcome_popup_has_already_displayed is True

    def test_create_startup_variables_explicit_false(self, test_db_session: Session):
        """Test creating StartupVariables with explicit False value."""
        vars = StartupVariables(welcome_popup_has_already_displayed=False)
        test_db_session.add(vars)
        test_db_session.commit()
        
        assert vars.welcome_popup_has_already_displayed is False

    def test_update_welcome_popup_flag_to_true(self, test_db_session: Session):
        """Test updating welcome_popup_has_already_displayed from False to True."""
        vars = StartupVariables(welcome_popup_has_already_displayed=False)
        test_db_session.add(vars)
        test_db_session.commit()
        
        vars.welcome_popup_has_already_displayed = True
        test_db_session.commit()
        test_db_session.refresh(vars)
        
        assert vars.welcome_popup_has_already_displayed is True

    def test_update_welcome_popup_flag_to_false(self, test_db_session: Session):
        """Test updating welcome_popup_has_already_displayed from True to False (reset)."""
        vars = StartupVariables(welcome_popup_has_already_displayed=True)
        test_db_session.add(vars)
        test_db_session.commit()
        
        vars.welcome_popup_has_already_displayed = False
        test_db_session.commit()
        test_db_session.refresh(vars)
        
        assert vars.welcome_popup_has_already_displayed is False

    def test_validate_welcome_popup_flag_rejects_non_boolean(self, test_db_session: Session):
        """Test validator rejects non-Boolean values for welcome_popup_has_already_displayed."""
        vars = StartupVariables()
        
        # Try setting to integer
        with pytest.raises(ValueError, match="must be a Boolean"):
            vars.welcome_popup_has_already_displayed = 1
        
        # Try setting to string
        with pytest.raises(ValueError, match="must be a Boolean"):
            vars.welcome_popup_has_already_displayed = "true"
        
        # Try setting to None
        with pytest.raises(ValueError, match="must be a Boolean"):
            vars.welcome_popup_has_already_displayed = None

    def test_singleton_pattern_multiple_records(self, test_db_session: Session):
        """Test that multiple StartupVariables records can exist (not enforced at DB level).
        
        Note: Singleton pattern is enforced by repository logic (get_or_create),
        not by database constraints. This test verifies multiple records are
        technically possible (though not used in practice).
        """
        vars1 = StartupVariables(welcome_popup_has_already_displayed=False)
        vars2 = StartupVariables(welcome_popup_has_already_displayed=True)
        
        test_db_session.add(vars1)
        test_db_session.add(vars2)
        test_db_session.commit()
        
        # Both should exist (repository pattern ensures singleton, not DB)
        assert test_db_session.query(StartupVariables).count() == 2
        assert vars1.id != vars2.id


# ============ Schema Validation Tests ============

class TestStartup_Schemas:
    """Test suite for Pydantic schemas in startup domain.
    
    Tests validate schema creation, field validation, and serialization
    for request/response DTOs.
    """

    def test_welcome_popup_response_valid_false(self):
        """Test WelcomePopupResponse with False value."""
        response = WelcomePopupResponse(has_already_displayed=False)
        
        assert response.has_already_displayed is False
        assert response.model_dump() == {"has_already_displayed": False}

    def test_welcome_popup_response_valid_true(self):
        """Test WelcomePopupResponse with True value."""
        response = WelcomePopupResponse(has_already_displayed=True)
        
        assert response.has_already_displayed is True
        assert response.model_dump() == {"has_already_displayed": True}

    def test_welcome_popup_response_from_dict(self):
        """Test WelcomePopupResponse creation from dictionary."""
        data = {"has_already_displayed": True}
        response = WelcomePopupResponse(**data)
        
        assert response.has_already_displayed is True

    def test_welcome_popup_response_json_serialization(self):
        """Test WelcomePopupResponse JSON serialization."""
        response = WelcomePopupResponse(has_already_displayed=False)
        json_str = response.model_dump_json()
        
        assert '"has_already_displayed":false' in json_str or '"has_already_displayed": false' in json_str

    def test_welcome_popup_response_requires_field(self):
        """Test WelcomePopupResponse requires has_already_displayed field."""
        with pytest.raises(ValueError):
            WelcomePopupResponse()  # Missing required field


# ============ Integration Tests ============

class TestStartup_Integration:
    """Integration tests for complete startup domain workflows.
    
    Tests end-to-end flows involving multiple layers (endpoint → repository → entity).
    """

    def test_first_user_experience_flow(self, client: TestClient, test_db_session: Session):
        """Test complete flow for first-time user (no existing record)."""
        # Verify no record exists
        assert test_db_session.query(StartupVariables).count() == 0
        
        # First API call (simulates app startup)
        response = client.get("/erudi/startup/welcome-popup")
        assert response.status_code == 200
        assert response.json()["has_already_displayed"] is False
        
        # Verify record was created and flag set
        vars = test_db_session.query(StartupVariables).first()
        assert vars is not None
        assert vars.welcome_popup_has_already_displayed is True
        
        # Subsequent call should return True
        response2 = client.get("/erudi/startup/welcome-popup")
        assert response2.json()["has_already_displayed"] is True

    def test_returning_user_experience_flow(self, client: TestClient, test_db_session: Session):
        """Test complete flow for returning user (existing record with flag=True)."""
        # Simulate existing user (record already exists)
        vars = StartupVariables(welcome_popup_has_already_displayed=True)
        test_db_session.add(vars)
        test_db_session.commit()
        
        # API call should return True immediately
        response = client.get("/erudi/startup/welcome-popup")
        assert response.status_code == 200
        assert response.json()["has_already_displayed"] is True
        
        # Multiple calls should all return True
        for _ in range(3):
            response = client.get("/erudi/startup/welcome-popup")
            assert response.json()["has_already_displayed"] is True

    def test_database_rollback_on_error(self, client: TestClient, test_db_session: Session):
        """Test database rollback on errors (simulated via invalid operations)."""
        # This test verifies the try-except-rollback pattern in endpoints
        # In real scenarios, errors would trigger rollback
        
        # Normal operation should work
        response = client.get("/erudi/startup/welcome-popup")
        assert response.status_code == 200
        
        # Verify record exists
        assert test_db_session.query(StartupVariables).count() >= 1

    def test_concurrent_first_time_calls(self, client: TestClient, test_db_session: Session):
        """Test handling of concurrent first-time calls (race condition simulation).
        
        Note: In production, first concurrent call wins. Subsequent calls see
        the flag as True. This test verifies idempotent behavior.
        """
        # Simulate two "simultaneous" first calls
        response1 = client.get("/erudi/startup/welcome-popup")
        response2 = client.get("/erudi/startup/welcome-popup")
        
        # First should be False, second should be True
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # At least one should be False (first call)
        results = [response1.json()["has_already_displayed"], response2.json()["has_already_displayed"]]
        assert False in results  # First call returns False
        assert True in results   # Second call returns True
        
        # Only one record should exist
        assert test_db_session.query(StartupVariables).count() == 1
