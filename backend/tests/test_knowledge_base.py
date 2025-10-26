"""Unit and integration tests for Knowledge Base domain.

Tests cover the complete KB workflow:
1. Repository layer (database operations)
2. Service layer (business logic)
3. API endpoints (HTTP interface)
4. Background tasks (async processing)

Architecture:
    Tests follow the 3-layer architecture (Repository -> Service -> Endpoints).
    Uses mocks for heavy operations (embeddings, FAISS indexing).
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

import os, sys
if sys.platform == "darwin":
    os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1") # Accelerate/vecLib (macOS)
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
import faiss, numpy
if sys.platform == "darwin":
    faiss.omp_set_num_threads(1)

from src.domains.knowledge_base.repository import KB_Repository
from src.domains.knowledge_base.services import KB_Service, KB_Indexer
from src.domains.knowledge_base.schemas import KnowledgeBaseCreate, KnowledgeBaseResponse

from src.entities.KnowledgeBase import KnowledgeBase
from src.entities.VectorStore import VectorStore
from src.entities.Llm import Llm
from src.entities.KBJob import KBJobModel

from src.core.exceptions import FileSystemException, FAISSException


# ============ Repository Layer Tests ============

class TestKB_Repository:
    """Test data access layer for Knowledge Base entities."""
    
    def test_create_knowledge_base(self, test_db_session):
        """Test creating new KnowledgeBase entity."""
        repo = KB_Repository()
        file_paths = ["/test/doc1.pdf", "/test/doc2.txt"]
        
        kb = repo.create_knowledge_base(test_db_session, file_paths)
        
        assert kb.id is not None
        assert kb.file_names_list == {"file_dropped_paths": file_paths}
        assert kb.index_path is None  # Not set yet
        assert kb.created_at is not None
    
    def test_get_knowledge_base_by_id(self, test_db_session):
        """Test fetching KnowledgeBase by ID."""
        repo = KB_Repository()
        
        # Create KB
        kb = repo.create_knowledge_base(test_db_session, ["/test/doc.pdf"])
        test_db_session.commit()
        
        # Fetch it back
        fetched_kb = repo.get_knowledge_base_by_id(test_db_session, kb.id)
        
        assert fetched_kb is not None
        assert fetched_kb.id == kb.id
        assert fetched_kb.file_names_list == kb.file_names_list
    
    def test_get_knowledge_base_by_id_not_found(self, test_db_session):
        """Test fetching non-existent KB returns None."""
        repo = KB_Repository()
        
        result = repo.get_knowledge_base_by_id(test_db_session, 99999)
        
        assert result is None
    
    def test_update_kb_index_path(self, test_db_session):
        """Test updating KnowledgeBase index_path."""
        repo = KB_Repository()
        
        kb = repo.create_knowledge_base(test_db_session, ["/test/doc.pdf"])
        test_db_session.commit()
        
        index_path = "/test/indexes/1.index"
        updated_kb = repo.update_kb_index_path(test_db_session, kb, index_path)
        
        assert updated_kb.index_path == index_path
    
    def test_create_vector_store(self, test_db_session):
        """Test creating VectorStore for KB."""
        repo = KB_Repository()
        
        kb = repo.create_knowledge_base(test_db_session, ["/test/doc.pdf"])
        test_db_session.commit()
        
        vector_store = repo.create_vector_store(test_db_session, kb.id)
        
        assert vector_store.id is not None
        assert vector_store.kb_id == kb.id
        assert vector_store.vectors_data == {}
    
    def test_get_vector_store_by_kb_id(self, test_db_session):
        """Test fetching VectorStore by KB ID."""
        repo = KB_Repository()
        
        kb = repo.create_knowledge_base(test_db_session, ["/test/doc.pdf"])
        vector_store = repo.create_vector_store(test_db_session, kb.id)
        test_db_session.commit()
        
        fetched_vs = repo.get_vector_store_by_kb_id(test_db_session, kb.id)
        
        assert fetched_vs is not None
        assert fetched_vs.id == vector_store.id
        assert fetched_vs.kb_id == kb.id
    
    def test_update_vector_store_data(self, test_db_session):
        """Test updating VectorStore vectors_data."""
        repo = KB_Repository()
        
        kb = repo.create_knowledge_base(test_db_session, ["/test/doc.pdf"])
        vector_store = repo.create_vector_store(test_db_session, kb.id)
        test_db_session.commit()
        
        vectors_data = {"0": "chunk 1", "1": "chunk 2"}
        updated_vs = repo.update_vector_store_data(test_db_session, vector_store, vectors_data)
        
        assert updated_vs.vectors_data == vectors_data
    
    def test_create_specialized_llm(self, test_db_session, mock_llm):
        """Test creating specialized LLM with KB attachment."""
        repo = KB_Repository()
        
        kb = repo.create_knowledge_base(test_db_session, ["/test/doc.pdf"])
        test_db_session.commit()
        
        specialized_llm = repo.create_specialized_llm(
            db=test_db_session,
            name="Test Assistant",
            description="Test description",
            base_llm=mock_llm,
            kb_id=kb.id
        )
        
        assert specialized_llm.id is not None
        assert specialized_llm.name == "Test Assistant"
        assert specialized_llm.is_attached_to_kb == 1
        assert specialized_llm.kb_id == kb.id
        assert specialized_llm.link == mock_llm.link
        assert specialized_llm.type == mock_llm.type
    
    def test_get_local_llm_by_id(self, test_db_session, mock_llm):
        """Test fetching local LLM by ID."""
        repo = KB_Repository()
        
        fetched_llm = repo.get_local_llm_by_id(test_db_session, mock_llm.id)
        
        assert fetched_llm is not None
        assert fetched_llm.id == mock_llm.id
        assert fetched_llm.local == 1
    
    def test_get_local_llm_by_id_not_local(self, test_db_session):
        """Test fetching non-local LLM returns None."""
        # Create non-local LLM
        llm = Llm(name="Remote Model", local=0, link="remote", type="test")
        test_db_session.add(llm)
        test_db_session.commit()
        
        repo = KB_Repository()
        result = repo.get_local_llm_by_id(test_db_session, llm.id)
        
        assert result is None
    
    def test_create_kb_job(self, test_db_session, mock_llm):
        """Test creating KBJob for tracking background tasks."""
        repo = KB_Repository()
        
        kb = repo.create_knowledge_base(test_db_session, ["/test/doc.pdf"])
        test_db_session.commit()
        
        kb_job = repo.create_kb_job(
            db=test_db_session,
            base_model_id=mock_llm.id,
            new_model_id=mock_llm.id,
            kb_id=kb.id,
            status="pending"
        )
        
        assert kb_job.id is not None
        assert kb_job.base_model_id == mock_llm.id
        assert kb_job.new_model_id == mock_llm.id
        assert kb_job.kb_id == kb.id
        assert kb_job.status == "pending"
    
    def test_get_kb_job_by_id(self, test_db_session, mock_llm):
        """Test fetching KBJob by ID."""
        repo = KB_Repository()
        
        kb = repo.create_knowledge_base(test_db_session, ["/test/doc.pdf"])
        kb_job = repo.create_kb_job(
            db=test_db_session,
            base_model_id=mock_llm.id,
            new_model_id=mock_llm.id,
            kb_id=kb.id,
            status="pending"
        )
        test_db_session.commit()
        
        fetched_job = repo.get_kb_job_by_id(test_db_session, kb_job.id)
        
        assert fetched_job is not None
        assert fetched_job.id == kb_job.id
    
    def test_get_kb_job_by_model_id(self, test_db_session, mock_llm):
        """Test fetching KBJob by new_model_id."""
        repo = KB_Repository()
        
        kb = repo.create_knowledge_base(test_db_session, ["/test/doc.pdf"])
        kb_job = repo.create_kb_job(
            db=test_db_session,
            base_model_id=mock_llm.id,
            new_model_id=mock_llm.id,
            kb_id=kb.id,
            status="pending"
        )
        test_db_session.commit()
        
        fetched_job = repo.get_kb_job_by_model_id(test_db_session, mock_llm.id)
        
        assert fetched_job is not None
        assert fetched_job.new_model_id == mock_llm.id or str(fetched_job.new_model_id) == str(mock_llm.id)
    
    def test_update_kb_job_status(self, test_db_session, mock_llm):
        """Test updating KBJob status."""
        repo = KB_Repository()
        
        kb = repo.create_knowledge_base(test_db_session, ["/test/doc.pdf"])
        kb_job = repo.create_kb_job(
            db=test_db_session,
            base_model_id=mock_llm.id,
            new_model_id=mock_llm.id,
            kb_id=kb.id,
            status="pending"
        )
        test_db_session.commit()
        
        updated_job = repo.update_kb_job_status(
            test_db_session, 
            kb_job, 
            "running"
        )
        
        assert updated_job.status == "running"
        assert updated_job.updated_at is not None
    
    def test_update_kb_job_status_with_error(self, test_db_session, mock_llm):
        """Test updating KBJob status with error message."""
        repo = KB_Repository()
        
        kb = repo.create_knowledge_base(test_db_session, ["/test/doc.pdf"])
        kb_job = repo.create_kb_job(
            db=test_db_session,
            base_model_id=mock_llm.id,
            new_model_id=mock_llm.id,
            kb_id=kb.id,
            status="pending"
        )
        test_db_session.commit()
        
        error_msg = "Test error"
        updated_job = repo.update_kb_job_status(
            test_db_session,
            kb_job,
            "failed",
            error_message=error_msg
        )
        
        assert updated_job.status == "failed"
        assert updated_job.error_message == error_msg


# ============ KB_Indexer Tests ============

class TestKB_Indexer:
    """Test FAISS indexing and embedding operations."""
    
    def test_create_faiss_index(self):
        """Test creating FAISS IndexIDMap."""
        indexer = KB_Indexer()
        
        index = indexer.create_faiss_index(dimension=384)
        
        assert index is not None
        assert index.d == 384
        assert index.ntotal == 0
    
    @patch('src.domains.knowledge_base.services.Embedder_Engine')
    @patch('src.domains.knowledge_base.services.chunk_by_tokens')
    def test_embed_and_index_texts(self, mock_chunk, mock_embedder_class):
        """Test embedding texts and adding to FAISS index."""
        # Setup mocks
        mock_embedder = MagicMock()
        mock_embedder_class.get_embedder.return_value = mock_embedder
        
        # Mock chunking
        mock_chunk.return_value = ["chunk 1", "chunk 2"]
        
        # Mock embeddings (384-dim vectors)
        mock_embedding = MagicMock()
        mock_embedding.detach.return_value.cpu.return_value.numpy.return_value.astype.return_value = \
            np.random.rand(384).astype('float32')
        mock_embedding.numel.return_value = 384
        mock_embedder.encode.return_value = mock_embedding
        
        indexer = KB_Indexer()
        index = indexer.create_faiss_index()
        vectors_data = {}
        texts = ["Test document 1"]
        
        result_index, result_data, next_id = indexer.embed_and_index_texts(
            texts=texts,
            index=index,
            vectors_data=vectors_data,
            start_id=0
        )
        
        assert result_index.ntotal == 2  # 2 chunks
        assert len(result_data) == 2
        assert "0" in result_data
        assert "1" in result_data
        assert next_id == 2
    
    def test_save_and_load_index(self, temp_index_dir):
        """Test saving and loading FAISS index to/from disk."""
        indexer = KB_Indexer()
        
        # Create and populate index
        index = indexer.create_faiss_index()
        vec = np.random.rand(1, 384).astype('float32')
        index.add_with_ids(vec, np.array([0]))
        
        # Save index
        index_path = os.path.join(temp_index_dir, "test.index")
        indexer.save_index(index, index_path)
        
        assert os.path.exists(index_path)
        
        # Load index
        loaded_index = indexer.load_index(index_path)
        
        assert loaded_index.ntotal == 1
        assert loaded_index.d == 384
    
    def test_load_index_not_found(self):
        """Test loading non-existent index raises FileSystemException."""
        indexer = KB_Indexer()
        
        with pytest.raises(FileSystemException):
            indexer.load_index("/nonexistent/path.index")
    
    @pytest.mark.skip(reason="FAISS search causes segfault in test environment")
    @patch('src.domains.knowledge_base.services.Embedder_Engine')
    def test_verify_index(self, mock_embedder_class, temp_index_dir):
        """Test index verification with search test."""
        # Setup mock
        mock_embedder = MagicMock()
        mock_embedder_class.get_embedder.return_value = mock_embedder
        mock_embedding = MagicMock()
        mock_embedding.detach.return_value.cpu.return_value.numpy.return_value.astype.return_value = \
            np.random.rand(384).astype('float32')
        mock_embedder.encode.return_value = mock_embedding
        
        indexer = KB_Indexer()
        
        # Create and save index
        index = indexer.create_faiss_index()
        vec = np.random.rand(1, 384).astype('float32')
        index.add_with_ids(vec, np.array([0]))
        
        index_path = os.path.join(temp_index_dir, "test.index")
        indexer.save_index(index, index_path)
        
        # Verify index
        result = indexer.verify_index(index_path)
        
        assert result is True


# ============ KB_Service Tests ============

class TestKB_Service:
    """Test business logic layer for Knowledge Base operations."""
    
    def test_get_kb_job_status_pending(self, test_db_session, mock_llm):
        """Test getting KB job status when pending."""
        repo = KB_Repository()
        kb = repo.create_knowledge_base(test_db_session, ["/test/doc.pdf"])
        kb_job = repo.create_kb_job(
            db=test_db_session,
            base_model_id=mock_llm.id,
            new_model_id=mock_llm.id,
            kb_id=kb.id,
            status="pending"
        )
        test_db_session.commit()
        
        service = KB_Service()
        status = service.get_kb_job_status(test_db_session, mock_llm.id)
        
        assert status["status"] == "pending"
        assert status["error_message"] is None
        assert "status_updated_at" in status
    
    def test_get_kb_job_status_not_found(self, test_db_session):
        """Test getting KB job status for non-existent job raises ValueError."""
        service = KB_Service()
        
        with pytest.raises(ValueError, match="KB job not found"):
            service.get_kb_job_status(test_db_session, 99999)
    
    def test_create_kb_assistant(self, test_db_session, mock_llm):
        """Test creating new KB assistant (database setup only)."""
        service = KB_Service()
        
        llm_id, kb_job_id = service.create_kb_assistant(
            db=test_db_session,
            base_llm_id=mock_llm.id,
            model_name="Test Assistant",
            description="Test description",
            file_paths=["/test/doc.pdf"]
        )
        
        assert llm_id is not None
        assert kb_job_id is not None
        
        # Verify entities created
        specialized_llm = test_db_session.query(Llm).filter(Llm.id == llm_id).first()
        assert specialized_llm is not None
        assert specialized_llm.name == "Test Assistant"
        assert specialized_llm.is_attached_to_kb == 1
        
        kb_job = test_db_session.query(KBJobModel).filter(KBJobModel.id == kb_job_id).first()
        assert kb_job is not None
        assert kb_job.status == "pending"
    
    def test_create_kb_assistant_base_llm_not_found(self, test_db_session):
        """Test creating KB assistant with invalid base LLM raises ValueError."""
        service = KB_Service()
        
        with pytest.raises(ValueError, match="not found or not local"):
            service.create_kb_assistant(
                db=test_db_session,
                base_llm_id=99999,
                model_name="Test",
                description="Test",
                file_paths=["/test/doc.pdf"]
            )
    
    def test_update_existing_kb(self, test_db_session, mock_llm_with_kb):
        """Test updating existing KB with new documents."""
        llm, kb, vector_store = mock_llm_with_kb
        
        service = KB_Service()
        
        llm_id, kb_job_id = service.update_existing_kb(
            db=test_db_session,
            base_llm_id=llm.id,
            file_paths=["/test/new_doc.pdf"]
        )
        
        assert llm_id == llm.id
        assert kb_job_id is not None
        
        # Verify job created
        kb_job = test_db_session.query(KBJobModel).filter(KBJobModel.id == kb_job_id).first()
        assert kb_job is not None
        assert kb_job.base_model_id == str(llm.id)
        assert kb_job.new_model_id == str(llm.id)  # Same for updates
        assert kb_job.status == "pending"
    
    def test_update_existing_kb_not_attached(self, test_db_session, mock_llm):
        """Test updating KB on LLM without KB raises ValueError."""
        service = KB_Service()
        
        with pytest.raises(ValueError, match="not attached to a KB"):
            service.update_existing_kb(
                db=test_db_session,
                base_llm_id=mock_llm.id,
                file_paths=["/test/doc.pdf"]
            )
    
    @patch('src.domains.knowledge_base.services.prepare_for_knowledge_base')
    @patch.object(KB_Service, '_create_index')
    def test_process_and_index_documents_create(
        self, 
        mock_create_index, 
        mock_prepare,
        test_db_session,
        mock_llm
    ):
        """Test processing documents for new KB creation."""
        # Setup mocks
        mock_prepare.return_value = ["text 1", "text 2"]
        
        # Create entities
        repo = KB_Repository()
        kb = repo.create_knowledge_base(test_db_session, ["/test/doc.pdf"])
        vector_store = repo.create_vector_store(test_db_session, kb.id)
        specialized_llm = repo.create_specialized_llm(
            db=test_db_session,
            name="Test",
            description="Test",
            base_llm=mock_llm,
            kb_id=kb.id
        )
        kb_job = repo.create_kb_job(
            db=test_db_session,
            base_model_id=mock_llm.id,
            new_model_id=specialized_llm.id,
            kb_id=kb.id,
            status="pending"
        )
        test_db_session.commit()
        
        # Mock verify_index to return True
        with patch.object(KB_Indexer, 'verify_index', return_value=True):
            service = KB_Service()
            service.process_and_index_documents(
                db=test_db_session,
                kb_job_id=kb_job.id,
                file_paths=["/test/doc.pdf"],
                is_update=False
            )
        
        # Verify job marked as completed
        test_db_session.refresh(kb_job)
        assert kb_job.status == "completed"
        
        # Verify _create_index was called
        mock_create_index.assert_called_once()
    
    @patch('src.domains.knowledge_base.services.prepare_for_knowledge_base')
    def test_process_and_index_documents_no_texts(
        self,
        mock_prepare,
        test_db_session,
        mock_llm
    ):
        """Test processing documents with no valid texts raises ValueError."""
        mock_prepare.return_value = []
        
        # Create entities
        repo = KB_Repository()
        kb = repo.create_knowledge_base(test_db_session, ["/test/doc.pdf"])
        vector_store = repo.create_vector_store(test_db_session, kb.id)
        kb_job = repo.create_kb_job(
            db=test_db_session,
            base_model_id=mock_llm.id,
            new_model_id=mock_llm.id,
            kb_id=kb.id,
            status="pending"
        )
        test_db_session.commit()
        
        service = KB_Service()
        
        with pytest.raises(ValueError, match="No valid texts"):
            service.process_and_index_documents(
                db=test_db_session,
                kb_job_id=kb_job.id,
                file_paths=["/test/doc.pdf"],
                is_update=False
            )


# ============ API Endpoint Tests ============

class TestKnowledgeBaseEndpoints:
    """Test REST API endpoints for Knowledge Base operations."""
    
    def test_get_kb_job_status_endpoint(self, client, test_db_session, mock_llm):
        """Test GET /knowledge_base/{llm_id}/status endpoint."""
        # Create job
        repo = KB_Repository()
        kb = repo.create_knowledge_base(test_db_session, ["/test/doc.pdf"])
        kb_job = repo.create_kb_job(
            db=test_db_session,
            base_model_id=mock_llm.id,
            new_model_id=mock_llm.id,
            kb_id=kb.id,
            status="running"
        )
        test_db_session.commit()
        
        response = client.get(f"/knowledge_base/{mock_llm.id}/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert "status_updated_at" in data
    
    def test_get_kb_job_status_not_found(self, client):
        """Test GET /knowledge_base/{llm_id}/status with invalid ID returns 404."""
        response = client.get("/knowledge_base/99999/status")
        
        assert response.status_code == 404
    
    @patch('src.domains.knowledge_base.services.KB_Service.create_kb_assistant')
    @patch('src.domains.knowledge_base.endpoints._run_kb_creation_task')
    def test_create_knowledge_base_endpoint_new(
        self,
        mock_bg_task,
        mock_create,
        client,
        test_db_session,
        mock_llm
    ):
        """Test POST /knowledge_base/create for new KB assistant."""
        # Mock service
        mock_create.return_value = (42, 1)  # (llm_id, kb_job_id)
        
        payload = {
            "paths": ["/test/doc.pdf"],
            "selectedModel": mock_llm.id,
            "modelName": "Test Assistant",
            "description": "Test description"
        }
        
        response = client.post("/knowledge_base/create", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "Knowledge Base Assistant is being created" in data["msg"]
        assert data["model_id"] == 42
    
    def test_create_knowledge_base_invalid_payload(self, client):
        """Test POST /knowledge_base/create with invalid payload returns 400."""
        payload = {
            "paths": [],  # Empty paths
            "selectedModel": 1,
            "modelName": "Test"
        }
        
        response = client.post("/knowledge_base/create", json=payload)
        
        assert response.status_code == 400
    
    def test_create_knowledge_base_base_llm_not_found(self, client):
        """Test POST /knowledge_base/create with invalid base LLM returns 404."""
        payload = {
            "paths": ["/test/doc.pdf"],
            "selectedModel": 99999,  # Non-existent
            "modelName": "Test Assistant"
        }
        
        response = client.post("/knowledge_base/create", json=payload)
        
        assert response.status_code == 404
    
    @patch('src.domains.knowledge_base.services.KB_Service.update_existing_kb')
    @patch('src.domains.knowledge_base.endpoints._run_kb_update_task')
    def test_create_knowledge_base_endpoint_update(
        self,
        mock_bg_task,
        mock_update,
        client,
        test_db_session,
        mock_llm_with_kb
    ):
        """Test POST /knowledge_base/create for updating existing KB."""
        llm, kb, vector_store = mock_llm_with_kb
        
        # Mock service
        mock_update.return_value = (llm.id, 1)  # (llm_id, kb_job_id)
        
        payload = {
            "paths": ["/test/new_doc.pdf"],
            "selectedModel": llm.id,
            "modelName": "Updated Assistant",
            "description": "Updated description"
        }
        
        response = client.post("/knowledge_base/create", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "updated" in data["msg"].lower()
        assert data["model_id"] == llm.id


# ============ Entity Model Tests ============

class TestKnowledgeBaseEntity:
    """Test KnowledgeBase entity properties and methods."""
    
    def test_file_paths_property(self):
        """Test file_paths property extraction."""
        kb = KnowledgeBase(
            file_names_list={"file_dropped_paths": ["/doc1.pdf", "/doc2.txt"]}
        )
        
        assert kb.file_paths == ["/doc1.pdf", "/doc2.txt"]
    
    def test_file_count_property(self):
        """Test file_count property."""
        kb = KnowledgeBase(
            file_names_list={"file_dropped_paths": ["/doc1.pdf", "/doc2.txt", "/doc3.pdf"]}
        )
        
        assert kb.file_count == 3
    
    def test_index_exists_property(self, tmp_path):
        """Test index_exists property.
        
        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        kb_no_index = KnowledgeBase(file_names_list={})
        
        # Create temp index file
        index_file = tmp_path / "test.index"
        index_file.write_text("fake index")
        
        kb_with_index = KnowledgeBase(
            file_names_list={},
            index_path=str(index_file)
        )
        
        assert kb_no_index.index_exists is False
        assert kb_with_index.index_exists is True
    
    def test_add_file_path(self):
        """Test add_file_path method."""
        kb = KnowledgeBase(
            file_names_list={"file_dropped_paths": ["/doc1.pdf"]}
        )
        
        kb.add_file_path("/doc2.pdf")
        
        assert "/doc2.pdf" in kb.file_paths
        assert kb.file_count == 2
    
    def test_remove_file_path(self):
        """Test remove_file_path method."""
        kb = KnowledgeBase(
            file_names_list={"file_dropped_paths": ["/doc1.pdf", "/doc2.pdf"]}
        )
        
        kb.remove_file_path("/doc1.pdf")
        
        assert "/doc1.pdf" not in kb.file_paths
        assert kb.file_count == 1


class TestVectorStoreEntity:
    """Test VectorStore entity properties and methods."""
    
    def test_vector_count_property(self):
        """Test vector_count property."""
        vs = VectorStore(
            kb_id=1,
            vectors_data={"0": "chunk1", "1": "chunk2", "2": "chunk3"}
        )
        
        assert vs.vector_count == 3
    
    def test_get_chunk(self):
        """Test get_chunk method."""
        vs = VectorStore(
            kb_id=1,
            vectors_data={"0": "test chunk"}
        )
        
        chunk = vs.get_chunk(0)
        
        assert chunk == "test chunk"
    
    def test_add_vector(self):
        """Test add_vector method."""
        vs = VectorStore(kb_id=1, vectors_data={})
        
        vs.add_vector(0, "new chunk")
        
        assert vs.get_chunk(0) == "new chunk"
        assert vs.vector_count == 1
    
    def test_remove_vector(self):
        """Test remove_vector method."""
        vs = VectorStore(
            kb_id=1,
            vectors_data={"0": "chunk1", "1": "chunk2"}
        )
        
        vs.remove_vector(0)
        
        assert vs.get_chunk(0) is None
        assert vs.vector_count == 1
    
    def test_get_all_chunks(self):
        """Test get_all_chunks method."""
        vs = VectorStore(
            kb_id=1,
            vectors_data={"0": "chunk1", "1": "chunk2"}
        )
        
        chunks = vs.get_all_chunks()
        
        assert "chunk1" in chunks.values()
        assert "chunk2" in chunks.values()
        assert len(chunks) == 2
    
    def test_clear_vectors(self):
        """Test clear_vectors method."""
        vs = VectorStore(
            kb_id=1,
            vectors_data={"0": "chunk1", "1": "chunk2"}
        )
        
        vs.clear_vectors()
        
        assert vs.vector_count == 0
        assert vs.vectors_data == {}
