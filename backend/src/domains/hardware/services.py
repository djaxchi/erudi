"""Business logic layer for hardware domain.

Implements Service pattern for hardware operations. Handles hardware detection,
profile management, score calculation, and labeling logic.

Architecture:
    Endpoints → Service → Repository → Entity → Database
    
Key Responsibilities:
    - Orchestrate hardware detection through LLM_Engine
    - Manage hardware profile lifecycle (get_or_create pattern)
    - Calculate boosted scores for UI display (+20 points)
    - Generate performance labels (Excellent, Good, Fair, Poor, Weak)
    - Format performance_breakdown structure
    
Example:
    from src.domains.hardware.services import Hardware_Service
    from src.domains.hardware.repository import Hardware_Repository
    from src.database.core import SessionLocal
    
    db = SessionLocal()
    repo = Hardware_Repository(db)
    service = Hardware_Service(repo)
    
    profile = service.get_or_create_profile()
    boosted = service.calculate_boosted_scores(profile)
    db.commit()
"""
from typing import Dict, Any
from src.domains.hardware.repository import Hardware_Repository
from src.entities.HardwareProfile import HardwareProfile
from src.core.logging import logger
from src.core.exceptions import HardwareException
from src.core import config


# Recommended model size window (billions of params) per UI inference tier (#86).
# The UI shows base models whose param_size falls in [min, max] as "Models For You".
# Thresholds apply to the boosted inference score and match the windows the frontend
# used to hardcode — now a single, data-driven source of truth.
_PARAM_RANGE_TIERS = (
    (75.0, (7.0, 12.0)),
    (50.0, (4.0, 8.0)),
    (25.0, (2.0, 7.0)),
)
_PARAM_RANGE_FLOOR = (1.0, 4.0)


def recommended_param_range(inference_score: float) -> tuple[float, float]:
    """Recommended model size window (billions of params) for a boosted inference
    score — drives the hardware-fit "Models For You" filter in the UI (#86)."""
    for threshold, window in _PARAM_RANGE_TIERS:
        if inference_score >= threshold:
            return window
    return _PARAM_RANGE_FLOOR


class Hardware_Service:
    """Service layer for hardware domain business logic.

    Orchestrates hardware detection, profile management, and score calculations.
    Separates business logic from data access and API concerns.

    Attributes:
        repository: Hardware_Repository for data access operations.

    Note:
        Service methods do NOT commit. Commits are handled at endpoint level.
        Uses repository for all database operations.

    Example:
        >>> service = Hardware_Service(Hardware_Repository(db))
        >>> profile = service.get_or_create_profile()
        >>> boosted = service.calculate_boosted_scores(profile)
        >>> print(boosted["global_inference_score"])  # +20 boost
        85.0
    """

    def __init__(self, repository: Hardware_Repository):
        """Initialize service with repository.

        Args:
            repository: Hardware_Repository instance for data access.
        """
        self.repository = repository
        logger.debug("Initializing Hardware_Service")

    def get_or_create_profile(self) -> HardwareProfile:
        """Get cached hardware profile or detect new one.

        Retrieves existing hardware profile from database. If none exists or
        if the cached profile backend doesn't match the current engine,
        performs hardware detection and creates new profile.

        Returns:
            HardwareProfile: Existing or newly created profile.

        Raises:
            HardwareException: If hardware detection or profile creation fails.

        Note:
            Does NOT commit. Caller must commit transaction.

        Example:
            >>> service = Hardware_Service(repo)
            >>> profile = service.get_or_create_profile()
            >>> print(profile.backend_type)  # "mlx", "cuda", or "cpu"
        """
        try:
            logger.info("Getting or creating hardware profile")
            
            # Try to get existing profile
            profile = self.repository.get_profile()
            
            # Extract backend type from current engine name
            current_backend = config.LLM_Engine.__name__.lower().replace('_engine', '')
            
            if profile:
                if profile.backend_type == current_backend:
                    logger.info(f"Using cached hardware profile: backend={profile.backend_type}")
                    return profile
                else:
                    # No profile exists or backend mismatch, detect hardware
                    logger.info(f"Backend mismatch: cached={profile.backend_type}, current={current_backend}. Re-detecting.")
                    self.repository.delete_profile(profile)      
            else:
                logger.info("No cached profile found, detecting hardware")
            
            hardware_data = self._detect_hardware()
            
            # Create new profile
            profile = self.repository.create_profile(hardware_data)
            logger.info(f"Hardware profile created: backend={profile.backend_type}")
            
            return profile
            
        except Exception as e:
            logger.exception(f"Failed to get or create hardware profile: {e}")
            raise HardwareException(
                "Failed to retrieve hardware information",
                trace=str(e)
            )

    def _detect_hardware(self) -> Dict[str, Any]:
        """Perform hardware detection through LLM_Engine.

        Calls engine's get_flat_hardware_data() method to retrieve hardware
        specifications in flat format ready for HardwareProfile entity creation.

        Returns:
            Dict[str, Any]: Flat hardware data ready for entity creation.

        Raises:
            HardwareException: If hardware detection fails.

        Note:
            Private method. Use get_or_create_profile() from endpoints.
        """
        try:
            logger.debug("Starting hardware detection via LLM_Engine")
            
            if not config.LLM_Engine:
                raise HardwareException("LLM_Engine not initialized")
            
            # Get flat hardware data from engine
            hardware_data = config.LLM_Engine.get_flat_hardware_data()
            
            logger.debug(f"Hardware detection complete: backend={hardware_data.get('backend_type')}")
            return hardware_data
            
        except Exception as e:
            logger.exception(f"Hardware detection failed: {e}")
            raise HardwareException(
                "Failed to detect hardware",
                trace=str(e)
            )

    def warm_up(self, duration_seconds: int = 5) -> bool:
        """Warm up hardware accelerator (GPU/MPS/CUDA).

        Delegates to LLM_Engine's warm_up_accelerator() method. Useful before
        benchmarking or first inference to ensure accurate performance.

        Args:
            duration_seconds: How long to run warm-up routine.

        Returns:
            bool: True if warm-up succeeded, False otherwise.

        Raises:
            HardwareException: If warm-up fails critically.

        Example:
            >>> service = Hardware_Service(repo)
            >>> success = service.warm_up(duration_seconds=5)
            >>> if success:
            ...     print("Accelerator ready")
        """
        try:
            logger.info(f"Starting hardware warm-up: duration={duration_seconds}s")
            
            if not config.LLM_Engine:
                logger.warning("LLM_Engine not initialized, skipping warm-up")
                return False
            
            success = config.LLM_Engine.warm_up_accelerator(duration_seconds)
            
            if success:
                logger.info("Hardware warm-up completed successfully")
            else:
                logger.warning("Hardware warm-up failed or not available")
            
            return success
            
        except Exception as e:
            logger.exception(f"Hardware warm-up failed: {e}")
            raise HardwareException(
                "Failed to warm up hardware accelerator",
                trace=str(e)
            )

    def calculate_boosted_scores(self, profile: HardwareProfile) -> Dict[str, Any]:
        """Calculate UI-friendly scores with +20 boost for frontend display.

        Returns both raw scores (actual hardware capability) and boosted scores
        (UI-friendly display with +20 point boost, capped at 100). This makes
        the boost transparent while maintaining user-friendly presentation.

        Args:
            profile: HardwareProfile entity with original scores.

        Returns:
            Dict[str, Any]: Dictionary with both raw and boosted scores/labels.

        Example:
            >>> profile = service.get_or_create_profile()
            >>> scores = service.calculate_boosted_scores(profile)
            >>> print(scores)
            {
                "raw_inference_score": 65.0,
                "boosted_inference_score": 85.0,  # min(65 + 20, 100)
                "global_inference_label": "Excellent",  # Based on boosted
                ...
            }
        """
        logger.debug("Calculating raw and boosted scores")

        # Raw score (actual hardware capability)
        raw_inf = profile.global_inference_score

        # Boosted score for UI (+ 20 points, capped at 100)
        boosted_inf = min(100.0, raw_inf + 20.0)

        result = {
            # Raw score (engine output, no modification)
            "raw_inference_score": raw_inf,

            # Boosted score for UI display
            "boosted_inference_score": boosted_inf,
            "global_inference_score": boosted_inf,  # Alias for backward compat

            # Label based on boosted score
            "global_inference_label": self._get_label(boosted_inf),

            # Component scores (raw, no boost needed for internal metrics)
            "cpu_score": profile.cpu_score,
            "memory_score": profile.memory_score,
            "gpu_score": profile.gpu_score if profile.gpu_score is not None else 0.0,
        }

        # Hardware-fit model size window (billions of params) for the UI's
        # "Models For You" recommendations (#86), derived from the boosted score.
        param_min, param_max = recommended_param_range(boosted_inf)
        result["recommended_param_min"] = param_min
        result["recommended_param_max"] = param_max
        
        logger.debug(
            f"Scores calculated: raw_inf={raw_inf:.1f}, boosted_inf={boosted_inf:.1f}"
        )
        return result

    def _get_label(self, score: float) -> str:
        """Convert numeric score to performance label.

        Applies thresholds to categorize performance:
        - 80-100: Excellent
        - 60-79:  Good
        - 40-59:  Fair
        - 20-39:  Poor
        - 0-19:   Weak

        Args:
            score: Numeric performance score (0-100).

        Returns:
            str: Performance label.

        Example:
            >>> service._get_label(85.0)
            'Excellent'
            >>> service._get_label(45.0)
            'Fair'
        """
        if score >= 80:
            return "Excellent"
        elif score >= 60:
            return "Good"
        elif score >= 40:
            return "Fair"
        elif score >= 20:
            return "Poor"
        else:
            return "Weak"

    def refresh_profile(self) -> HardwareProfile:
        """Re-detect hardware and update existing profile.

        Performs fresh hardware detection and updates existing profile with
        new data. Useful for detecting hardware changes or refreshing dynamic
        fields (available_memory_gb, disk_available_gb).

        Returns:
            HardwareProfile: Updated profile entity.

        Raises:
            HardwareException: If refresh fails.

        Note:
            Does NOT commit. Caller must commit transaction.

        Example:
            >>> service = Hardware_Service(repo)
            >>> profile = service.refresh_profile()
            >>> db.commit()
        """
        try:
            logger.info("Refreshing hardware profile")
            
            # Detect current hardware state
            hardware_data = self._detect_hardware()
            
            # Get existing profile
            profile = self.repository.get_profile()
            if not profile:
                # No profile exists, create new
                logger.info("No profile to refresh, creating new")
                profile = self.repository.create_profile(hardware_data)
            else:
                # Update existing profile
                logger.info(f"Updating existing profile: id={profile.id}")
                profile = self.repository.update_profile(profile, hardware_data)
            
            logger.info("Hardware profile refreshed successfully")
            return profile
            
        except Exception as e:
            logger.exception(f"Failed to refresh hardware profile: {e}")
            raise HardwareException(
                "Failed to refresh hardware profile",
                trace=str(e)
            )
