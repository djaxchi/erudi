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
from src.utils import vars


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

        Retrieves existing hardware profile from database. If none exists,
        performs hardware detection through engine and creates new profile.

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
            if profile:
                logger.info(f"Using cached hardware profile: backend={profile.backend_type}")
                return profile
            
            # No profile exists, detect hardware
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

        Calls engine's get_hardware_info() and get_performance_evaluation() methods
        directly and merges the results.

        Returns:
            Dict[str, Any]: Complete hardware data ready for entity creation.

        Raises:
            HardwareException: If hardware detection fails.

        Note:
            Private method. Use get_or_create_profile() from endpoints.
        """
        try:
            logger.debug("Starting hardware detection via LLM_Engine")
            
            if not vars.LLM_Engine:
                raise HardwareException("LLM_Engine not initialized")
            
            # Get basic hardware info (backend_type, cpu, memory, disk)
            basic_info = vars.LLM_Engine.get_hardware_info()
            
            # Get performance evaluation (scores, labels, accelerator details)
            performance_info = vars.LLM_Engine.get_performance_evaluation()
            
            # Merge dictionaries
            hardware_data = {**basic_info, **performance_info}
            
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
            
            if not vars.LLM_Engine:
                logger.warning("LLM_Engine not initialized, skipping warm-up")
                return False
            
            success = vars.LLM_Engine.warm_up_accelerator(duration_seconds)
            
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
        """Calculate UI-friendly scores with +20 boost.

        Applies +20 point boost to all scores for frontend display. This is
        a presentation concern to make scores more user-friendly.

        Args:
            profile: HardwareProfile entity with original scores.

        Returns:
            Dict[str, Any]: Dictionary with boosted scores and labels.

        Example:
            >>> profile = service.get_or_create_profile()
            >>> boosted = service.calculate_boosted_scores(profile)
            >>> print(boosted)
            {
                "global_inference_score": 85.0,  # Original 65 + 20
                "global_inference_label": "Excellent",
                "global_finetuning_score": 75.0,
                "global_finetuning_label": "Good",
                "cpu_score": 80.0,
                "memory_score": 90.0,
                "gpu_score": 95.0
            }
        """
        logger.debug("Calculating boosted scores")
        
        boosted = {
            # Global scores with +20 boost
            "global_inference_score": profile.global_inference_score + 20,
            "global_inference_label": self._get_label(profile.global_inference_score + 20),
            "global_finetuning_score": profile.global_finetuning_score + 20,
            "global_finetuning_label": self._get_label(profile.global_finetuning_score + 20),
            
            # Component scores with +20 boost
            "cpu_score": profile.cpu_score + 20,
            "memory_score": profile.memory_score + 20,
            "gpu_score": (profile.gpu_score + 20) if profile.gpu_score else None,
        }
        
        logger.debug(f"Boosted scores calculated: inference={boosted['global_inference_score']}")
        return boosted

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
