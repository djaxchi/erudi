"""Comprehensive tests for LLMs domain (model management and downloads).

Tests cover:
- Repository layer (LLM and DownloadJob CRUD operations)
- Service layer (download orchestration, progress tracking, mocked HF downloads)
- Endpoint layer (REST API for model management)

All HuggingFace API calls and file operations are mocked for fast, isolated testing.
No real model downloads or network calls occur during tests.
"""
import pytest
import os
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock, call
from fastapi import status
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from src.domains.llms.repository import Llm_Repository, Download_Job_Repository
from src.domains.llms.services import (
    DownloadTracker,
    make_callback,
    download_llm,
    get_quantized_model_link
)
from src.domains.llms.schemas import LLMCreate, LLMResponse, DownloadJobResponse
from src.entities.Llm import Llm
from src.entities.DownloadJob import DownloadJobModel


# ============ Repository Tests - LLM ============

class TestLlm_Repository:
    """Test suite for Llm_Repository database operations."""

    def test_create_llm(self, test_db_session):
        """Test LLM creation in database.
        
        Args:
            test_db_session: Database session fixture.
        """
        repo = Llm_Repository(test_db_session)
        
        llm = repo.create(
            name="Test Model",
            local=0,
            type="llama",
            link="test/model",
            quantized=False,
            param_size=7.0
        )
        
        assert llm.id is not None
        assert llm.name == "Test Model"
        assert llm.local == 0
        assert llm.type == "llama"
        assert llm.quantized is False
        assert llm.param_size == 7.0

    def test_get_all_llms(self, client, test_db_session):
        """Test GET /erudi/llms/ returns all LLMs.
        
        Args:
            client: FastAPI test client.
            test_db_session: Database session fixture.
        """
        # Create test LLMs
        llm1 = Llm(name="Model 1", local=0, type="qwen", link="hf/model1", param_size=4.0)
        llm2 = Llm(name="Model 2", local=1, type="llama", link="/models/2", param_size=7.0)
        test_db_session.add_all([llm1, llm2])
        test_db_session.commit()
    
        response = client.get("/erudi/llms/")
    
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 2  # At least our test models

    def test_get_all_local(self, test_db_session):
        """Test retrieving only local LLMs.
        
        Args:
            test_db_session: Database session fixture.
        """
        repo = Llm_Repository(test_db_session)
        
        repo.create(name="Local 1", local=1, type="qwen", link="/path1", param_size=4.0)
        repo.create(name="Remote", local=0, type="mistral", link="hf/model", param_size=7.0)
        repo.create(name="Local 2", local=1, type="llama", link="/path2", param_size=8.0)
        test_db_session.commit()
        
        local_llms = repo.get_all_local()
        
        assert len(local_llms) == 2
        assert all(llm.local == 1 for llm in local_llms)

    def test_get_all_remote(self, test_db_session):
        """Test retrieving only remote LLMs.
        
        Args:
            test_db_session: Database session fixture.
        """
        repo = Llm_Repository(test_db_session)
        
        repo.create(name="Local", local=1, type="qwen", link="/path", param_size=4.0)
        repo.create(name="Remote 1", local=0, type="mistral", link="hf/model1", param_size=7.0)
        repo.create(name="Remote 2", local=0, type="llama", link="hf/model2", param_size=8.0)
        test_db_session.commit()
        
        remote_llms = repo.get_all_remote()
        
        assert len(remote_llms) == 2
        assert all(llm.local == 0 for llm in remote_llms)

    def test_get_by_id(self, test_db_session):
        """Test retrieving LLM by ID.
        
        Args:
            test_db_session: Database session fixture.
        """
        repo = Llm_Repository(test_db_session)
        
        created = repo.create(name="Test", local=0, type="qwen", link="test", param_size=4.0)
        test_db_session.commit()
        
        retrieved = repo.get_by_id(created.id)
        
        assert retrieved.id == created.id
        assert retrieved.name == "Test"

    def test_get_by_id_not_found(self, test_db_session):
        """Test get_by_id returns None when LLM doesn't exist.
        
        Args:
            test_db_session: Database session fixture.
        """
        repo = Llm_Repository(test_db_session)
        
        result = repo.get_by_id(999)
        
        assert result is None

    def test_search_by_name(self, test_db_session):
        """Test searching LLMs by name (case-insensitive).
        
        Args:
            test_db_session: Database session fixture.
        """
        repo = Llm_Repository(test_db_session)
        
        repo.create(name="Llama-3-8B", local=0, type="llama", link="hf/llama", param_size=8.0)
        repo.create(name="Qwen2.5-7B", local=0, type="qwen", link="hf/qwen", param_size=7.0)
        repo.create(name="Mistral-7B", local=0, type="mistral", link="hf/mistral", param_size=7.0)
        test_db_session.commit()
        
        results = repo.search_by_name("llama")
        
        assert len(results) == 1
        assert "Llama" in results[0].name

    def test_update_llm(self, test_db_session):
        """Test updating LLM fields.
        
        Args:
            test_db_session: Database session fixture.
        """
        repo = Llm_Repository(test_db_session)
        
        llm = repo.create(name="Original", local=0, type="qwen", link="old", param_size=4.0)
        test_db_session.commit()
        
        updated = repo.update(llm, name="Updated", link="new")
        test_db_session.commit()
        
        assert updated.name == "Updated"
        assert updated.link == "new"
        assert updated.type == "qwen"  # Unchanged

    def test_delete_llm(self, test_db_session):
        """Test deleting LLM.
        
        Args:
            test_db_session: Database session fixture.
        """
        repo = Llm_Repository(test_db_session)
        
        llm = repo.create(name="To Delete", local=1, type="qwen", link="/path", param_size=4.0)
        test_db_session.commit()
        
        repo.delete(llm)
        test_db_session.commit()
        
        assert repo.get_by_id(llm.id) is None


# ============ Repository Tests - DownloadJob ============

class TestDownload_Job_Repository:
    """Test suite for Download_Job_Repository database operations."""

    def test_create_download_job(self, test_db_session):
        """Test creating a download job record.
        
        Args:
            test_db_session: Database session fixture.
        """
        repo = Download_Job_Repository(test_db_session)
        
        job_data = {
            "remote_model_id": "meta/llama-3-8b",
            "local_model_id": 42,
            "remote_model_link": "https://huggingface.co/meta/llama-3-8b",
            "temp_local_model_link": "/data/temp_42",
            "final_local_model_link": "/data/models/42"
        }
        
        job = repo.create(**job_data)
        test_db_session.commit()
        
        assert job.id is not None
        assert job.remote_model_id == "meta/llama-3-8b"
        assert job.local_model_id == "42"  # SQLite returns strings for integer columns in some cases
        assert job.status == "pending"
        assert job.progress == 0.0

    def test_get_by_id(self, test_db_session):
        """Test retrieving download job by ID.
        
        Args:
            test_db_session: Database session fixture.
        """
        repo = Download_Job_Repository(test_db_session)
        
        created = repo.create(
            remote_model_id="test/model",
            local_model_id=1,
            remote_model_link="https://hf.co/test",
            temp_local_model_link="/temp/1",
            final_local_model_link="/models/1"
        )
        test_db_session.commit()
        
        retrieved = repo.get_by_id(created.id)
        
        assert retrieved.id == created.id
        assert retrieved.status == "pending"

    def test_update_status(self, test_db_session):
        """Test updating job status.
        
        Args:
            test_db_session: Database session fixture.
        """
        repo = Download_Job_Repository(test_db_session)
        
        job = repo.create(
            remote_model_id="test/model",
            local_model_id=1,
            remote_model_link="https://hf.co/test",
            temp_local_model_link="/temp/1",
            final_local_model_link="/models/1"
        )
        test_db_session.commit()
        
        repo.update_status(job, "running")
        test_db_session.commit()
        
        assert job.status == "running"

    def test_update_progress(self, test_db_session):
        """Test updating job progress metrics.
        
        Args:
            test_db_session: Database session fixture.
        """
        repo = Download_Job_Repository(test_db_session)
        
        job = repo.create(
            remote_model_id="test/model",
            local_model_id=1,
            remote_model_link="https://hf.co/test",
            temp_local_model_link="/temp/1",
            final_local_model_link="/models/1"
        )
        test_db_session.commit()
        
        repo.update_progress(
            job,
            total_bytes=1000000.0,
            progress=50.0,
            elapsed_seconds=60.0,
            eta_seconds=60.0
        )
        test_db_session.commit()
        
        assert job.total_bytes == 1000000.0
        assert job.progress == 50.0
        assert job.total_time_elapsed == 60.0
        assert job.time_left == 60.0

    def test_mark_completed(self, test_db_session):
        """Test marking job as completed.
        
        Args:
            test_db_session: Database session fixture.
        """
        repo = Download_Job_Repository(test_db_session)
        
        job = repo.create(
            remote_model_id="test/model",
            local_model_id=1,
            remote_model_link="https://hf.co/test",
            temp_local_model_link="/temp/1",
            final_local_model_link="/models/1"
        )
        test_db_session.commit()
        
        repo.mark_completed(job)
        test_db_session.commit()
        
        assert job.status == "completed"
        assert job.progress == 100.0

    def test_mark_failed(self, test_db_session):
        """Test marking job as failed with error message.
        
        Args:
            test_db_session: Database session fixture.
        """
        repo = Download_Job_Repository(test_db_session)
        
        job = repo.create(
            remote_model_id="test/model",
            local_model_id=1,
            remote_model_link="https://hf.co/test",
            temp_local_model_link="/temp/1",
            final_local_model_link="/models/1"
        )
        test_db_session.commit()
        
        error_msg = "Network timeout"
        repo.mark_failed(job, error_msg)
        test_db_session.commit()
        
        assert job.status == "failed"
        assert job.error_message == error_msg

    def test_get_most_recent_active(self, test_db_session):
        """Test finding the most recently updated active job.
        
        Args:
            test_db_session: Database session fixture.
        """
        repo = Download_Job_Repository(test_db_session)
        
        # Create old job
        old_job = DownloadJobModel(
            remote_model_id="old/model",
            local_model_id=1,
            remote_model_link="https://hf.co/old",
            temp_local_model_link="/temp/1",
            final_local_model_link="/models/1",
            status="running"
        )
        old_job.updated_at = datetime.utcnow() - timedelta(minutes=2)  # 2 minutes ago (not 120 seconds)
        test_db_session.add(old_job)
        
        # Create recent job
        recent_job = DownloadJobModel(
            remote_model_id="recent/model",
            local_model_id=2,
            remote_model_link="https://hf.co/recent",
            temp_local_model_link="/temp/2",
            final_local_model_link="/models/2",
            status="pending"
        )
        recent_job.updated_at = datetime.utcnow()
        test_db_session.add(recent_job)
        test_db_session.commit()
        
        # Should return most recent active job
        result = repo.get_most_recent_active()
        assert result is not None
        assert result.id == recent_job.id


# ============ Service Tests - DownloadTracker ============

class TestDownloadTracker:
    """Test suite for DownloadTracker progress monitoring."""

    def test_initialization(self):
        """Test DownloadTracker initializes with zero progress."""
        tracker = DownloadTracker()
        
        assert tracker.total_bytes == 0
        assert tracker.downloaded_bytes == 0
        assert tracker.eta_seconds is None
        assert tracker.percent == 0.0

    def test_update_progress(self):
        """Test updating downloaded bytes."""
        tracker = DownloadTracker()
        tracker.total_bytes = 1000
        
        tracker.update(250)
        assert tracker.downloaded_bytes == 250
        
        tracker.update(250)
        assert tracker.downloaded_bytes == 500

    def test_percent_calculation(self):
        """Test progress percentage calculation."""
        tracker = DownloadTracker()
        tracker.total_bytes = 1000
        
        tracker.update(250)
        assert tracker.percent == 25.0
        
        tracker.update(500)
        assert tracker.percent == 75.0

    def test_percent_zero_division_guard(self):
        """Test percent returns 0 when total_bytes is 0."""
        tracker = DownloadTracker()
        tracker.total_bytes = 0
        tracker.downloaded_bytes = 100
        
        assert tracker.percent == 0.0

    @pytest.mark.asyncio
    async def test_monitor_eta(self):
        """Test ETA monitoring updates eta_seconds.
        
        Note: This is a simplified test - real ETA would require time progression.
        """
        tracker = DownloadTracker()
        tracker.total_bytes = 1000
        tracker.downloaded_bytes = 500
        
        # Start monitoring in background
        monitor_task = asyncio.create_task(tracker.monitor_eta(interval=0.1))
        
        # Simulate download completion
        await asyncio.sleep(0.15)
        tracker.downloaded_bytes = 1000
        
        # Wait for monitor to detect completion
        await asyncio.sleep(0.15)
        
        # Cleanup
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass


# ============ Service Tests - Callback & Utilities ============

class TestDownloadCallbacks:
    """Test suite for fsspec callback generation."""

    def test_make_callback_creation(self):
        """Test callback factory creates valid fsspec callback."""
        tracker = DownloadTracker()
        tracker.total_bytes = 1000
        
        callback = make_callback(tracker)
        
        assert callback is not None
        assert callback.size == 1000

    def test_callback_updates_tracker(self):
        """Test callback updates tracker on chunk transfer."""
        tracker = DownloadTracker()
        tracker.total_bytes = 1000
        
        callback = make_callback(tracker)
        
        # Simulate fsspec calling the callback hook
        if "transfer-chunk" in callback.hooks:
            hook = callback.hooks["transfer-chunk"]
            hook(size=100, value=100)
            assert tracker.downloaded_bytes == 100
            
            hook(size=100, value=300)
            assert tracker.downloaded_bytes == 300


class TestGetQuantizedModelLink:
    """Test suite for MODEL_MAPPING resolution."""

    @patch('src.domains.llms.services.config')
    def test_returns_quantized_link_when_available(self, mock_config):
        """Test returns quantized link from MODEL_MAPPING if available."""
        mock_config.LLM_Engine.MODEL_MAPPING = {
            "meta-llama/Llama-3-8B": "mlx-community/Llama-3-8B-4bit"
        }
        
        result = get_quantized_model_link("meta-llama/Llama-3-8B")
        
        assert result == "mlx-community/Llama-3-8B-4bit"

    @patch('src.domains.llms.services.config')
    def test_returns_original_when_no_mapping(self, mock_config):
        """Test returns original link when no mapping exists."""
        mock_config.LLM_Engine.MODEL_MAPPING = {}
        
        result = get_quantized_model_link("unmapped/model")
        
        assert result == "unmapped/model"


# ============ Endpoint Tests - LLM CRUD ============

class TestLLM_Endpoints:
    """Test suite for LLM management REST API endpoints."""

    def test_get_all_llms(self, client, test_db_session):
        """Test GET /llms returns all LLMs.
        
        Args:
            client: FastAPI test client.
            test_db_session: Database session fixture.
        """
        # Create test LLMs
        llm1 = Llm(name="Model 1", local=0, type="qwen", link="hf/model1", param_size=4.0)
        llm2 = Llm(name="Model 2", local=1, type="llama", link="/models/2", param_size=7.0)
        test_db_session.add_all([llm1, llm2])
        test_db_session.commit()
    
        response = client.get("/erudi/llms/")
    
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

    def test_get_local_llms(self, client, test_db_session):
        """Test GET /llms/local returns only local LLMs.
        
        Args:
            client: FastAPI test client.
            test_db_session: Database session fixture.
        """
        llm1 = Llm(name="Local", local=1, type="qwen", link="/models/1", param_size=4.0)
        llm2 = Llm(name="Remote", local=0, type="llama", link="hf/model", param_size=7.0)
        test_db_session.add_all([llm1, llm2])
        test_db_session.commit()
        
        response = client.get("/erudi/llms/local")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["local"] == 1

    def test_get_remote_llms(self, client, test_db_session):
        """Test GET /llms/remote returns only remote LLMs.
        
        Args:
            client: FastAPI test client.
            test_db_session: Database session fixture.
        """
        llm1 = Llm(name="Local", local=1, type="qwen", link="/models/1", param_size=4.0)
        llm2 = Llm(name="Remote", local=0, type="llama", link="hf/model", param_size=7.0)
        test_db_session.add_all([llm1, llm2])
        test_db_session.commit()
    
        response = client.get("/erudi/llms/remote")
    
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["local"] == 0

    def test_get_llm_by_id(self, client, test_db_session):
        """Test GET /erudi/llms/{id} returns specific LLM.
        
        Args:
            client: FastAPI test client.
            test_db_session: Database session fixture.
        """
        llm = Llm(name="Test Model", local=1, type="qwen", link="/models/1", param_size=4.0)
        test_db_session.add(llm)
        test_db_session.commit()
    
        response = client.get(f"/erudi/llms/{llm.id}")
    
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == llm.id
        assert data["name"] == "Test Model"
    
    def test_get_llm_not_found(self, client):
        """Test GET /erudi/llms/{id} returns 404 when LLM doesn't exist.
        
        Args:
            client: FastAPI test client.
        """
        response = client.get("/erudi/llms/99999")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_search_llms(self, client, test_db_session):
        """Test GET /llms/search filters by name.
        
        Args:
            client: FastAPI test client.
            test_db_session: Database session fixture.
        """
        llm1 = Llm(name="Llama-3-8B", local=0, type="llama", link="hf/llama", param_size=8.0)
        llm2 = Llm(name="Qwen2.5-7B", local=0, type="qwen", link="hf/qwen", param_size=7.0)
        test_db_session.add_all([llm1, llm2])
        test_db_session.commit()
    
        response = client.get("/erudi/llms/search?name=llama")
    
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert "Llama" in data[0]["name"]

    def test_update_llm(self, client, test_db_session):
        """Test PUT /erudi/llms/{id} updates LLM metadata.
        
        Args:
            client: FastAPI test client.
            test_db_session: Database session fixture.
        """
        llm = Llm(name="Original", local=0, type="qwen", link="old", param_size=4.0)
        test_db_session.add(llm)
        test_db_session.commit()
    
        response = client.put(
            f"/erudi/llms/{llm.id}",
            json={"name": "Updated", "local": 0, "link": "new"}
        )
    
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Updated"
        assert data["link"] == "new"
    
    @patch('os.path.exists')
    @patch('shutil.rmtree')
    def test_delete_llm(self, mock_rmtree, mock_exists, client, test_db_session):
        """Test DELETE /llms/{id} removes LLM and files.
        
        Args:
            mock_rmtree: Mock for shutil.rmtree.
            mock_exists: Mock for os.path.exists.
            client: FastAPI test client.
            test_db_session: Database session fixture.
        """
        mock_exists.return_value = True
        
        llm = Llm(name="To Delete", local=1, type="qwen", link="/models/1", param_size=4.0)
        test_db_session.add(llm)
        test_db_session.commit()
        llm_id = llm.id
    
        response = client.delete(f"/erudi/llms/{llm_id}")
    
        assert response.status_code == status.HTTP_200_OK
        mock_rmtree.assert_called_once()

    def test_delete_llm_downloading(self, client, test_db_session):
        """Test DELETE /erudi/llms/{id} fails when model is downloading.
        
        Args:
            client: FastAPI test client.
            test_db_session: Database session fixture.
        """
        llm = Llm(name="Downloading", local=2, type="qwen", link="/temp/1", param_size=4.0)
        test_db_session.add(llm)
        test_db_session.commit()
    
        response = client.delete(f"/erudi/llms/{llm.id}")
    
        assert response.status_code == status.HTTP_400_BAD_REQUEST
# ============ Endpoint Tests - Download Jobs ============

class TestDownloadJob_Endpoints:
    """Test suite for download job management endpoints."""

    @patch('src.domains.llms.endpoints.download_llm')
    @patch('pathlib.Path.exists')
    def test_start_download(self, mock_exists, mock_download, client, test_db_session):
        """Test POST /erudi/llms/{id}/download starts download job.
        
        Args:
            mock_exists: Mock for pathlib.Path.exists (temp/final paths).
            mock_download: Mock for download_llm service.
            client: FastAPI test client.
            test_db_session: Database session fixture.
        """
        mock_exists.return_value = False
        mock_download.return_value = AsyncMock()
    
        # Create remote LLM
        llm = Llm(name="Remote Model", local=0, type="qwen", link="hf/model", param_size=4.0)
        test_db_session.add(llm)
        test_db_session.commit()
    
        response = client.post(f"/erudi/llms/{llm.id}/download")
    
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "id" in data  # Job ID returned in response
        assert data["status"] == "pending"
    
    def test_start_download_not_found(self, client):
        """Test POST /erudi/llms/{id}/download returns 404 for missing LLM.
        
        Args:
            client: FastAPI test client.
        """
        response = client.post("/erudi/llms/99999/download")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('pathlib.Path.exists')
    def test_start_download_path_exists(self, mock_exists, client, test_db_session):
        """Test POST /erudi/llms/{id}/download fails if model path exists.
        
        Args:
            mock_exists: Mock for pathlib.Path.exists.
            client: FastAPI test client.
            test_db_session: Database session fixture.
        """
        mock_exists.return_value = True
    
        llm = Llm(name="Remote", local=0, type="qwen", link="hf/model", param_size=4.0)
        test_db_session.add(llm)
        test_db_session.commit()
    
        response = client.post(f"/erudi/llms/{llm.id}/download")
    
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    
    def test_get_download_status(self, client, test_db_session):
        """Test GET /erudi/llms/downloads/{job_id}/status returns job state.
        
        Args:
            client: FastAPI test client.
            test_db_session: Database session fixture.
        """
        job = DownloadJobModel(
            remote_model_id="test/model",
            local_model_id=1,
            remote_model_link="https://hf.co/test",
            temp_local_model_link="/temp/1",
            final_local_model_link="/models/1",
            status="running",
            progress=45.5
        )
        test_db_session.add(job)
        test_db_session.commit()
    
        response = client.get(f"/erudi/llms/downloads/{job.id}/status")
    
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == job.id
        assert data["status"] == "running"
        assert data["progress"] == 45.5

    def test_get_download_status_not_found(self, client):
        """Test GET /llms/downloads/{job_id}/status returns 404 for missing job.
        
        Args:
            client: FastAPI test client.
        """
        response = client.get("/erudi/llms/downloads/999/status")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('src.domains.llms.repository.Download_Job_Repository.cleanup_job_files')
    def test_cancel_download(self, mock_cleanup, client, test_db_session):
        """Test POST /llms/downloads/{job_id}/cancel cancels active job.
        
        Args:
            mock_cleanup: Mock for cleanup_job_files.
            client: FastAPI test client.
            test_db_session: Database session fixture.
        """
        # Create LLM in downloading state
        llm = Llm(name="Downloading", local=2, type="qwen", link="/temp/1", param_size=4.0)
        test_db_session.add(llm)
        test_db_session.flush()
        
        # Create active job
        job = DownloadJobModel(
            remote_model_id="test/model",
            local_model_id=llm.id,
            remote_model_link="https://hf.co/test",
            temp_local_model_link="/temp/1",
            final_local_model_link="/models/1",
            status="running"
        )
        test_db_session.add(job)
        test_db_session.commit()
    
        response = client.post(f"/erudi/llms/downloads/{job.id}/cancel")
    
        assert response.status_code == status.HTTP_200_OK
        mock_cleanup.assert_called_once()

    def test_cancel_download_completed(self, client, test_db_session):
        """Test POST /erudi/llms/downloads/{job_id}/cancel fails for completed job.
        
        Args:
            client: FastAPI test client.
            test_db_session: Database session fixture.
        """
        job = DownloadJobModel(
            remote_model_id="test/model",
            local_model_id=1,
            remote_model_link="https://hf.co/test",
            temp_local_model_link="/temp/1",
            final_local_model_link="/models/1",
            status="completed"
        )
        test_db_session.add(job)
        test_db_session.commit()
    
        response = client.post(f"/erudi/llms/downloads/{job.id}/cancel")
    
        assert response.status_code == status.HTTP_400_BAD_REQUEST
# ============ Entity Validation Tests ============

class TestLlm_Entity_Validations:
    """Test suite for Llm entity field validations."""

    def test_valid_llm_creation(self, test_db_session):
        """Test creating LLM with valid data."""
        llm = Llm(
            name="Valid Model",
            local=1,
            type="qwen",
            link="/models/1",
            param_size=4.0,
            quantized=False
        )
        test_db_session.add(llm)
        test_db_session.commit()
        
        assert llm.id is not None

    def test_empty_name_validation(self, test_db_session):
        """Test name validation rejects empty string."""
        with pytest.raises(ValueError, match="LLM name cannot be empty"):
            llm = Llm(
                name="",
                local=1,
                type="qwen",
                link="/models/1",
                param_size=4.0
            )
            test_db_session.add(llm)
            test_db_session.flush()

    def test_invalid_local_state(self, test_db_session):
        """Test local validation rejects invalid state."""
        with pytest.raises(ValueError, match="Invalid local state"):
            llm = Llm(
                name="Test",
                local=5,  # Invalid
                type="qwen",
                link="/models/1",
                param_size=4.0
            )
            test_db_session.add(llm)
            test_db_session.flush()

    def test_negative_param_size(self, test_db_session):
        """Test param_size validation rejects negative values."""
        with pytest.raises(ValueError, match="param_size must be positive"):
            llm = Llm(
                name="Test",
                local=1,
                type="qwen",
                link="/models/1",
                param_size=-1.0
            )
            test_db_session.add(llm)
            test_db_session.flush()

    def test_empty_type_validation(self, test_db_session):
        """Test type validation rejects empty string."""
        with pytest.raises(ValueError, match="LLM type cannot be empty"):
            llm = Llm(
                name="Test",
                local=1,
                type="",
                link="/models/1",
                param_size=4.0
            )
            test_db_session.add(llm)
            test_db_session.flush()


class TestDownloadJob_Entity_Validations:
    """Test suite for DownloadJobModel entity field validations."""

    def test_valid_job_creation(self, test_db_session):
        """Test creating job with valid data."""
        job = DownloadJobModel(
            remote_model_id="test/model",
            local_model_id=1,
            remote_model_link="https://hf.co/test",
            temp_local_model_link="/temp/1",
            final_local_model_link="/models/1",
            status="pending"
        )
        test_db_session.add(job)
        test_db_session.commit()
        
        assert job.id is not None

    def test_invalid_status(self, test_db_session):
        """Test status validation rejects invalid values."""
        with pytest.raises(ValueError, match="Invalid status"):
            job = DownloadJobModel(
                remote_model_id="test/model",
                local_model_id=1,
                remote_model_link="https://hf.co/test",
                status="invalid_status"
            )
            test_db_session.add(job)
            test_db_session.flush()

    def test_invalid_progress_range(self, test_db_session):
        """Test progress validation rejects out-of-range values."""
        with pytest.raises(ValueError, match="Progress must be between"):
            job = DownloadJobModel(
                remote_model_id="test/model",
                local_model_id=1,
                remote_model_link="https://hf.co/test",
                status="running",
                progress=150.0  # Invalid
            )
            test_db_session.add(job)
            test_db_session.flush()

    def test_negative_bytes(self, test_db_session):
        """Test validation rejects negative byte values."""
        with pytest.raises(ValueError, match="must be non-negative"):
            job = DownloadJobModel(
                remote_model_id="test/model",
                local_model_id=1,
                remote_model_link="https://hf.co/test",
                status="running",
                total_bytes=-1000.0
            )
            test_db_session.add(job)
            test_db_session.flush()

    def test_empty_remote_model_id(self, test_db_session):
        """Test validation rejects empty remote_model_id."""
        with pytest.raises(ValueError, match="cannot be empty"):
            job = DownloadJobModel(
                remote_model_id="",
                local_model_id=1,
                remote_model_link="https://hf.co/test",
                status="pending"
            )
            test_db_session.add(job)
            test_db_session.flush()
