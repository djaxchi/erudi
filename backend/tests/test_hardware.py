"""Tests for hardware service layer.

Tests hardware detection, profile management, and score calculations
through the service layer.
"""
import pytest
from unittest.mock import Mock, patch
from src.domains.hardware.services import Hardware_Service, PROFILING_LOGIC_VERSION
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
        mock_profile.profiling_version = PROFILING_LOGIC_VERSION
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
    
    def test_get_or_create_profile_reprofiles_when_logic_version_changed(
        self, service, mock_repository
    ):
        """A profile produced by superseded profiling logic must be redone.

        The profile is written once at first boot and read forever after, so
        without this #365 -- a 448 GB/s card profiled at 13 GB/s because NVML
        was read for the idle clock -- would keep serving the stored 13 on every
        machine that had already run the app.
        """
        stale = Mock(spec=HardwareProfile)
        stale.backend_type = "cuda"
        stale.profiling_version = PROFILING_LOGIC_VERSION - 1
        mock_repository.get_profile.return_value = stale

        fresh_data = {"backend_type": "cuda", "memory_bandwidth_gbs": 448.0}
        fresh = Mock(spec=HardwareProfile)
        mock_repository.create_profile.return_value = fresh

        mock_engine = Mock()
        mock_engine.__name__ = "CUDA_Engine"
        mock_engine.get_flat_hardware_data.return_value = fresh_data

        with patch.object(config, "LLM_Engine", mock_engine):
            result = service.get_or_create_profile()

        assert result == fresh
        mock_repository.delete_profile.assert_called_once_with(stale)
        mock_repository.create_profile.assert_called_once()

    def test_get_or_create_profile_reprofiles_when_version_is_null(
        self, service, mock_repository
    ):
        """NULL is what every pre-existing row carries, so it must count as stale."""
        legacy = Mock(spec=HardwareProfile)
        legacy.backend_type = "cuda"
        legacy.profiling_version = None
        mock_repository.get_profile.return_value = legacy

        fresh = Mock(spec=HardwareProfile)
        mock_repository.create_profile.return_value = fresh

        mock_engine = Mock()
        mock_engine.__name__ = "CUDA_Engine"
        mock_engine.get_flat_hardware_data.return_value = {"backend_type": "cuda"}

        with patch.object(config, "LLM_Engine", mock_engine):
            result = service.get_or_create_profile()

        assert result == fresh
        mock_repository.delete_profile.assert_called_once_with(legacy)

    def test_detect_hardware_stamps_the_profiling_version(self, service):
        """Whatever the engine reports gets tagged with the logic that read it."""
        mock_engine = Mock()
        mock_engine.get_flat_hardware_data.return_value = {"backend_type": "cuda"}

        with patch.object(config, "LLM_Engine", mock_engine):
            data = service._detect_hardware()

        assert data["profiling_version"] == PROFILING_LOGIC_VERSION

    def test_calculate_boosted_scores_adds_20_points(self, service):
        """Test that the boosted score correctly adds 20 points."""
        mock_profile = Mock(spec=HardwareProfile)
        mock_profile.global_inference_score = 65.0
        mock_profile.cpu_score = 40.0
        mock_profile.memory_score = 60.0
        mock_profile.gpu_score = 70.0
        mock_profile.backend_type = "cpu"
        mock_profile.total_memory_gb = 16.0
        mock_profile.unified_memory = False
        mock_profile.memory_bandwidth_gbs = None

        result = service.calculate_boosted_scores(mock_profile)

        assert result["raw_inference_score"] == 65.0
        assert result["boosted_inference_score"] == 85.0  # 65 + 20

    def test_calculate_boosted_scores_caps_at_100(self, service):
        """Test that the boosted score is capped at 100."""
        mock_profile = Mock(spec=HardwareProfile)
        mock_profile.global_inference_score = 85.0
        mock_profile.cpu_score = 40.0
        mock_profile.memory_score = 60.0
        mock_profile.gpu_score = 70.0
        mock_profile.backend_type = "cpu"
        mock_profile.total_memory_gb = 16.0
        mock_profile.unified_memory = False
        mock_profile.memory_bandwidth_gbs = None

        result = service.calculate_boosted_scores(mock_profile)

        assert result["boosted_inference_score"] == 100.0  # min(85 + 20, 100)

    def test_calculate_boosted_scores_includes_recommended_param_range(self, service):
        """Boosted scores carry the hardware-fit model size window (#86), now
        derived from real usable memory (#199) rather than the score."""
        mock_profile = Mock(spec=HardwareProfile)
        mock_profile.global_inference_score = 65.0
        mock_profile.cpu_score = 40.0
        mock_profile.memory_score = 60.0
        mock_profile.gpu_score = 70.0
        mock_profile.backend_type = "cuda"
        mock_profile.vram_total_gb = 16.0
        mock_profile.unified_memory = False
        mock_profile.memory_bandwidth_gbs = None
        mock_profile.total_memory_gb = 32.0

        result = service.calculate_boosted_scores(mock_profile)

        # (16 - 1.5) / 0.6 = 24.2 max; min = max*0.5 capped at the 8B floor so
        # the 7-14B models stay in "Models For You".
        assert result["recommended_param_min"] == 8.0
        assert result["recommended_param_max"] == 24.2


class TestRecommendedParamRange:
    """The hardware-fit model size window (#199 Part 2).

    Two independent physical constraints, whichever binds first: how much fits
    in memory, and how fast bandwidth can stream it. The old score-tier lookup
    collapsed both into one 0-100 bucket, so a 16GB and a 48GB machine landed on
    the same 7-12B. Capacity alone was no better: it promised ~17B on a 16GB Mac
    where 12B measurably lags.

    Rows below pin real machines so the calibration is checkable without owning
    the hardware.
    """

    @staticmethod
    def _profile(**overrides):
        defaults = dict(backend_type="cpu", vram_total_gb=None, unified_memory=False,
                        total_memory_gb=16.0, memory_bandwidth_gbs=None)
        defaults.update(overrides)
        return Mock(spec=HardwareProfile, **defaults)

    # ---- capacity-bound machines: bandwidth is ample, memory decides ----

    def test_cuda_5060ti_is_memory_bound(self):
        from src.domains.hardware.services import recommended_param_range
        # 16GB VRAM, 448 GB/s. mem (16-1.5)/0.6 = 24.2; bw 448/(0.6*20) = 37.3.
        # Memory binds. Validated against this machine's real behaviour.
        profile = self._profile(backend_type="cuda", vram_total_gb=16.0,
                                memory_bandwidth_gbs=448.0)
        assert recommended_param_range(profile) == (8.0, 24.2)

    def test_cuda_48gb_is_memory_bound_and_floor_is_capped(self):
        from src.domains.hardware.services import recommended_param_range
        # mem (48-1.5)/0.6 = 77.5; bw 900/12 = 75 -> 75. An uncapped max/2 floor
        # would ask for 37B minimum and empty "Models For You" on the best
        # machines, so the floor caps at 8B.
        profile = self._profile(backend_type="cuda", vram_total_gb=48.0,
                                memory_bandwidth_gbs=900.0)
        assert recommended_param_range(profile) == (8.0, 75.0)

    # ---- bandwidth-bound machines: it fits, but it would crawl ----

    def test_cuda_slow_memory_is_bandwidth_bound(self):
        from src.domains.hardware.services import recommended_param_range
        # Same 16GB as the 5060 Ti but 200 GB/s: bw 200/12 = 16.7 < mem 24.2.
        # Same capacity, smaller recommendation. This is the dimension a
        # capacity-only window cannot see.
        profile = self._profile(backend_type="cuda", vram_total_gb=16.0,
                                memory_bandwidth_gbs=200.0)
        assert recommended_param_range(profile) == (8.0, 16.7)

    def test_mlx_m4_16gb_matches_measured_behaviour(self):
        from src.domains.hardware.services import recommended_param_range
        # usable = 16*0.75 - 4 (fixed OS share) = 8; mem (8-1.5)/0.6 = 10.8;
        # bw 120/12 = 10 -> 10. Capacity-only gave 8.8-17.5B on this machine,
        # where 8B is comfortable and 12B measurably lags.
        profile = self._profile(backend_type="mlx", unified_memory=True,
                                total_memory_gb=16.0, memory_bandwidth_gbs=120.0)
        assert recommended_param_range(profile) == (5.0, 10.0)

    def test_mlx_large_unified_memory_stays_generous(self):
        from src.domains.hardware.services import recommended_param_range
        # usable = 48*0.75 - 4 = 32; mem (32-1.5)/0.6 = 50.8; bw 400/12 = 33.3.
        # The fixed OS reserve must not punish big machines.
        profile = self._profile(backend_type="mlx", unified_memory=True,
                                total_memory_gb=48.0, memory_bandwidth_gbs=400.0)
        assert recommended_param_range(profile) == (8.0, 33.3)

    # ---- unknown bandwidth degrades to capacity, never to zero ----

    def test_unknown_bandwidth_falls_back_to_capacity_only(self):
        from src.domains.hardware.services import recommended_param_range
        # memory_bandwidth_gbs is nullable and CPU fallback paths leave it unset.
        # 16GB CPU: usable 8, (8-1.5)/0.6 = 10.8.
        profile = self._profile(backend_type="cpu", total_memory_gb=16.0,
                                memory_bandwidth_gbs=None)
        assert recommended_param_range(profile) == (5.4, 10.8)

    def test_zero_bandwidth_is_treated_as_unknown(self):
        from src.domains.hardware.services import recommended_param_range
        # A 0 reading must not collapse the window to the 1B floor.
        profile = self._profile(backend_type="cpu", total_memory_gb=16.0,
                                memory_bandwidth_gbs=0.0)
        assert recommended_param_range(profile) == (5.4, 10.8)

    def test_cpu_small_laptop(self):
        from src.domains.hardware.services import recommended_param_range
        # 8GB laptop: usable 4, (4-1.5)/0.6 = 4.2; bw 50/12 = 4.2.
        profile = self._profile(backend_type="cpu", total_memory_gb=8.0,
                                memory_bandwidth_gbs=50.0)
        min_p, max_p = recommended_param_range(profile)
        assert (min_p, max_p) == (2.1, 4.2)

    # ---- guards ----

    def test_floor_never_goes_below_one_billion(self):
        from src.domains.hardware.services import recommended_param_range
        profile = self._profile(backend_type="cpu", total_memory_gb=1.0)
        min_p, max_p = recommended_param_range(profile)
        assert min_p >= 1.0
        assert max_p >= 1.0

    def test_min_never_exceeds_max(self):
        from src.domains.hardware.services import recommended_param_range
        # Bandwidth-starved machine: the 8B floor cap must not invert the window.
        profile = self._profile(backend_type="cuda", vram_total_gb=16.0,
                                memory_bandwidth_gbs=10.0)
        min_p, max_p = recommended_param_range(profile)
        assert min_p <= max_p

    def test_ceiling_is_capped(self):
        from src.domains.hardware.services import recommended_param_range
        profile = self._profile(backend_type="cuda", vram_total_gb=1000.0,
                                memory_bandwidth_gbs=10000.0)
        _, max_p = recommended_param_range(profile)
        assert max_p == 120.0
        assert max_p == 120.0


class TestBuildBackendSpecificSchema:
    """/hardware/detailed schema construction from the entity, per backend (#165)."""

    SCORES = {
        "raw_inference_score": 17.6,
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
