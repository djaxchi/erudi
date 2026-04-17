"""Tests for hardware service layer.

Tests hardware detection, profile management, and score calculations
through the service layer.
"""
import pytest
from unittest.mock import Mock, patch
from src.domains.hardware.services import Hardware_Service
from src.domains.hardware.repository import Hardware_Repository
from src.entities.HardwareProfile import HardwareProfile
from src.core import config


class TestHardwareService:
    """Test Hardware_Service business logic."""
    
    @pytest.fixture
    def mock_repository(self):
        """Create mock repository for testing."""
        return Mock(spec=Hardware_Repository)
    
    @pytest.fixture
    def service(self, mock_repository):
        """Create service instance with mock repository."""
        return Hardware_Service(mock_repository)
    
    def test_detect_hardware_calls_engine_flat_method(self, service):
        """Test that _detect_hardware calls get_flat_hardware_data."""
        mock_data = {
            "backend_type": "cpu",
            "cpu_model": "Test CPU",
            "total_memory_gb": 16.0,
            "available_memory_gb": 8.0,
            "disk_total_gb": 500.0,
            "disk_available_gb": 250.0,
            "global_inference_score": 50.0,
            "global_inference_label": "Medium",
            "global_finetuning_score": 45.0,
            "global_finetuning_label": "Medium",
            "cpu_score": 40.0,
            "memory_score": 60.0,
            "gpu_score": 0.0,
            "system_platform": "Linux",
            "performance_breakdown": {},
        }
        
        # Create a mock engine class
        mock_engine = Mock()
        mock_engine.get_flat_hardware_data.return_value = mock_data
        
        with patch.object(config, 'LLM_Engine', mock_engine):
            result = service._detect_hardware()
            
            assert result == mock_data
            assert result["backend_type"] == "cpu"
            mock_engine.get_flat_hardware_data.assert_called_once()
    
    def test_get_or_create_profile_returns_cached_when_backend_matches(self, service, mock_repository):
        """Test that cached profile is returned when backend matches."""
        # Setup mock profile
        mock_profile = Mock(spec=HardwareProfile)
        mock_profile.backend_type = "mlx"
        mock_repository.get_profile.return_value = mock_profile
        
        # Mock current engine with __name__
        mock_engine = Mock()
        mock_engine.__name__ = "MLX_Engine"
        
        with patch.object(config, 'LLM_Engine', mock_engine):
            result = service.get_or_create_profile()
            
            assert result == mock_profile
            mock_repository.get_profile.assert_called_once()
            mock_repository.create_profile.assert_not_called()
    
    def test_get_or_create_profile_detects_when_backend_mismatch(self, service, mock_repository):
        """Test that new profile is created when backend doesn't match."""
        # Setup mock profile with different backend
        old_profile = Mock(spec=HardwareProfile)
        old_profile.backend_type = "cpu"
        mock_repository.get_profile.return_value = old_profile
        
        # Mock detection
        new_data = {
            "backend_type": "mlx",
            "cpu_model": "Apple M3",
            "total_memory_gb": 64.0,
            "available_memory_gb": 32.0,
            "disk_total_gb": 1000.0,
            "disk_available_gb": 500.0,
            "global_inference_score": 85.0,
            "global_inference_label": "Excellent",
            "global_finetuning_score": 80.0,
            "global_finetuning_label": "Good",
            "cpu_score": 75.0,
            "memory_score": 90.0,
            "gpu_score": 85.0,
            "system_platform": "Darwin",
            "performance_breakdown": {},
        }
        
        new_profile = Mock(spec=HardwareProfile)
        new_profile.backend_type = "mlx"
        mock_repository.create_profile.return_value = new_profile
        
        mock_engine = Mock()
        mock_engine.__name__ = "MLX_Engine"
        mock_engine.get_flat_hardware_data.return_value = new_data
        
        with patch.object(config, 'LLM_Engine', mock_engine):
            result = service.get_or_create_profile()
            
            assert result == new_profile
            mock_repository.create_profile.assert_called_once_with(new_data)
    
    def test_get_or_create_profile_creates_when_none_exists(self, service, mock_repository):
        """Test that profile is created when none exists in database."""
        mock_repository.get_profile.return_value = None
        
        mock_data = {
            "backend_type": "cuda",
            "cpu_model": "Intel Xeon",
            "total_memory_gb": 128.0,
            "available_memory_gb": 64.0,
            "disk_total_gb": 2000.0,
            "disk_available_gb": 1000.0,
            "global_inference_score": 90.0,
            "global_inference_label": "Excellent",
            "global_finetuning_score": 88.0,
            "global_finetuning_label": "Excellent",
            "cpu_score": 70.0,
            "memory_score": 85.0,
            "gpu_score": 95.0,
            "system_platform": "Linux",
            "performance_breakdown": {},
        }
        
        new_profile = Mock(spec=HardwareProfile)
        new_profile.backend_type = "cuda"
        mock_repository.create_profile.return_value = new_profile
        
        mock_engine = Mock()
        mock_engine.__name__ = "CUDA_Engine"
        mock_engine.get_flat_hardware_data.return_value = mock_data
        
        with patch.object(config, 'LLM_Engine', mock_engine):
            result = service.get_or_create_profile()
            
            assert result == new_profile
            mock_repository.create_profile.assert_called_once_with(mock_data)
    
    def test_calculate_boosted_scores_adds_20_points(self, service):
        """Test that boosted scores correctly add 20 points."""
        mock_profile = Mock(spec=HardwareProfile)
        mock_profile.global_inference_score = 65.0
        mock_profile.global_finetuning_score = 55.0
        mock_profile.cpu_score = 40.0
        mock_profile.memory_score = 60.0
        mock_profile.gpu_score = 70.0
        
        result = service.calculate_boosted_scores(mock_profile)
        
        assert result["raw_inference_score"] == 65.0
        assert result["boosted_inference_score"] == 85.0  # 65 + 20
        assert result["raw_finetuning_score"] == 55.0
        assert result["boosted_finetuning_score"] == 75.0  # 55 + 20
    
    def test_calculate_boosted_scores_caps_at_100(self, service):
        """Test that boosted scores are capped at 100."""
        mock_profile = Mock(spec=HardwareProfile)
        mock_profile.global_inference_score = 85.0
        mock_profile.global_finetuning_score = 90.0
        mock_profile.cpu_score = 40.0
        mock_profile.memory_score = 60.0
        mock_profile.gpu_score = 70.0
        
        result = service.calculate_boosted_scores(mock_profile)
        
        assert result["boosted_inference_score"] == 100.0  # min(85 + 20, 100)
        assert result["boosted_finetuning_score"] == 100.0  # min(90 + 20, 100)
