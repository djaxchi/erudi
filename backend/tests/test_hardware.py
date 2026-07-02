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

    def test_calculate_boosted_scores_includes_recommended_param_range(self, service):
        """Boosted scores carry the hardware-fit model size window (#86)."""
        mock_profile = Mock(spec=HardwareProfile)
        mock_profile.global_inference_score = 65.0   # boosted 85 -> top tier (>= 75)
        mock_profile.global_finetuning_score = 55.0
        mock_profile.cpu_score = 40.0
        mock_profile.memory_score = 60.0
        mock_profile.gpu_score = 70.0

        result = service.calculate_boosted_scores(mock_profile)

        assert result["recommended_param_min"] == 7.0
        assert result["recommended_param_max"] == 12.0


@pytest.mark.parametrize("score,expected", [
    (100.0, (7.0, 12.0)),
    (75.0, (7.0, 12.0)),   # tier boundary
    (74.9, (4.0, 8.0)),
    (50.0, (4.0, 8.0)),
    (25.0, (2.0, 7.0)),
    (24.9, (1.0, 4.0)),
    (0.0, (1.0, 4.0)),
])
def test_recommended_param_range_tiers(score, expected):
    """The hardware-fit model size window per boosted inference score (#86)."""
    from src.domains.hardware.services import recommended_param_range
    assert recommended_param_range(score) == expected


class TestBuildBackendSpecificSchema:
    """/hardware/detailed schema construction from the entity, per backend (#165)."""

    SCORES = {
        "raw_inference_score": 17.6,
        "raw_finetuning_score": 10.0,
        "cpu_score": 50.0,
        "memory_score": 60.0,
        "gpu_score": 70.0,
    }

    @staticmethod
    def _profile(**overrides):
        common = dict(
            backend_type="cpu",
            cpu_model="Test CPU",
            total_memory_gb=16.0,
            available_memory_gb=8.0,
            disk_total_gb=512.0,
            disk_available_gb=256.0,
            global_inference_score=40.0,
            global_inference_label="Medium",
            global_finetuning_score=20.0,
            global_finetuning_label="Poor",
            cpu_score=50.0,
            memory_score=60.0,
            architecture="x86_64",
            system_platform="Windows",
        )
        common.update(overrides)
        return HardwareProfile(**common)

    def test_cpu_branch_reads_the_real_entity_column(self):
        """The entity has no compute_units column — the CPU branch must build
        from cpu_performance_units (Float in the entity, int in the schema).
        Regression: this raised AttributeError on every CPU install (#165)."""
        from src.domains.hardware.endpoints import _build_backend_specific_schema

        profile = self._profile(cpu_performance_units=12.0)
        info = _build_backend_specific_schema(profile, self.SCORES)

        assert info.backend_type == "cpu"
        assert info.compute_units == 12
        assert info.cpu_performance_units == 12
        assert info.gpu_score == 0.0

    def test_cpu_branch_defaults_to_one_unit_when_unset(self):
        from src.domains.hardware.endpoints import _build_backend_specific_schema

        info = _build_backend_specific_schema(
            self._profile(cpu_performance_units=None), self.SCORES
        )
        assert info.compute_units == 1
        assert info.cpu_performance_units == 1

    def test_mlx_branch_builds_from_entity_columns(self):
        from src.domains.hardware.endpoints import _build_backend_specific_schema

        profile = self._profile(
            backend_type="mlx",
            mlx_chip_model="M3 Max",
            mlx_gpu_cores=40,
            mps_available=True,
            neural_engine_tops=35.0,
        )
        info = _build_backend_specific_schema(profile, self.SCORES)
        assert info.backend_type == "mlx"
        assert info.mlx_gpu_cores == 40

    def test_cuda_branch_builds_from_entity_columns(self):
        from src.domains.hardware.endpoints import _build_backend_specific_schema

        profile = self._profile(
            backend_type="cuda",
            gpu_name="RTX 4090",
            cuda_cores=16384,
            cuda_version="12.1",
            compute_capability="8.9",
            vram_total_gb=24.0,
            vram_available_gb=20.0,
            estimated_tflops=82.6,
        )
        info = _build_backend_specific_schema(profile, self.SCORES)
        assert info.backend_type == "cuda"
        assert info.cuda_cores == 16384
