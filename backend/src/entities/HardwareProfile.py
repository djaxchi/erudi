"""SQLAlchemy entity for backend-agnostic hardware profile.

Stores comprehensive hardware specifications and performance scores for all backends
(MLX, CUDA, CPU). Uses discriminated fields with backend_type to determine which
fields are populated. All backend-specific fields are nullable.

Architecture:
    - Common fields: Populated for all backends (CPU, memory, scores)
    - MLX-specific: chip_model, mlx_gpu_cores, mps_available, neural_engine_tops
    - CUDA-specific: cuda_cores, cuda_version, compute_capability, vram_*
    - CPU-only: Minimal fields (no GPU/accelerator)

Example:
    from src.entities.HardwareProfile import HardwareProfile

    # MLX backend
    hw_mlx = HardwareProfile(
        backend_type="mlx",
        cpu_model="Apple M3 Max",
        total_memory_gb=128.0,
        mlx_chip_model="M3 Max",
        mlx_gpu_cores=40,
        mps_available=True,
        unified_memory=True
    )

    # CUDA backend
    hw_cuda = HardwareProfile(
        backend_type="cuda",
        cpu_model="Intel Xeon",
        total_memory_gb=64.0,
        cuda_cores=10752,
        cuda_version="12.1",
        vram_total_gb=24.0
    )
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, Float
from sqlalchemy.schema import CheckConstraint
from sqlalchemy.sql import func
from src.database.core import Base


class HardwareProfile(Base):
    """SQLAlchemy model for backend-agnostic hardware profile (singleton).

    Comprehensive hardware specifications supporting MLX (Apple Silicon), CUDA (NVIDIA),
    and CPU backends. Backend-specific fields are nullable and populated based on
    backend_type discriminator.

    Table Design:
        - Singleton pattern: Only one row in database (id=1)
        - backend_type determines which optional fields are populated
        - Frontend checks backend_type to render appropriate UI

    Common Attributes (All Backends):
        id: Primary key (singleton, always 1).
        backend_type: Backend discriminator ("mlx", "cuda", "cpu").
        cpu_model: CPU model string.
        total_memory_gb: Total system memory in GB.
        available_memory_gb: Currently available memory in GB.
        disk_total_gb: Total disk space in GB.
        disk_available_gb: Available disk space in GB.
        global_inference_score: Inference performance score (0-100).
        global_inference_label: Inference label (Poor/Medium/Good/Very Good).
        cpu_score: CPU-specific score (0-100).
        memory_score: Memory-specific score (0-100).
        system_platform: OS platform (Darwin/Linux/Windows).

    Common Accelerator Attributes (MLX & CUDA):
        gpu_name: Accelerator name (Apple GPU / NVIDIA GPU model).
        estimated_tflops: Estimated peak TFLOPS (FP32).
        memory_bandwidth_gbs: Memory bandwidth in GB/s.
        architecture: Architecture identifier (3nm/5nm for MLX, Ampere/Ada for CUDA).
        gpu_score: GPU/accelerator performance score (0-100).

    MLX-Specific Attributes (Apple Silicon):
        mlx_chip_model: Apple chip model (M1/M2/M3/M4 + variant).
        mlx_gpu_cores: Number of GPU cores (8-76).
        mps_available: Metal Performance Shaders availability.
        neural_engine_tops: Neural Engine performance (TOPS).
        unified_memory: Unified memory architecture flag.

    CUDA-Specific Attributes (NVIDIA):
        cuda_cores: Number of CUDA cores.
        cuda_version: CUDA runtime version (e.g., "12.1").
        compute_capability: Compute capability (e.g., "8.6").
        vram_total_gb: Total dedicated VRAM in GB.
        vram_available_gb: Available VRAM in GB.

    Performance Tracking:
        cpu_performance_units: CPU performance metric (computed).
        performance_breakdown: Detailed JSON with component scores.
        created_at: Profile creation timestamp.
        updated_at: Last update timestamp.

    Constraints:
        - backend_type must be "mlx", "cuda", or "cpu"
        - Singleton enforced at application level (id=1)

    Example:
        >>> # MLX profile
        >>> hw = HardwareProfile(
        ...     backend_type="mlx",
        ...     cpu_model="Apple M3 Max",
        ...     mlx_chip_model="M3 Max",
        ...     mlx_gpu_cores=40,
        ...     unified_memory=True
        ... )
        >>> db.add(hw)
        >>> db.commit()
    """
    __tablename__ = "hardware_profiles"

    # Primary key (singleton)
    id = Column(Integer, primary_key=True, index=True)
    
    # ============================================================================
    # COMMON FIELDS (All Backends)
    # ============================================================================
    
    # Backend discriminator
    backend_type = Column(String, nullable=False)  # "mlx", "cuda", "cpu"
    
    # CPU information
    cpu_model = Column(String, nullable=False)
    
    # Memory information (system RAM)
    total_memory_gb = Column(Float, nullable=False)
    available_memory_gb = Column(Float, nullable=False)
    
    # Storage information
    disk_total_gb = Column(Float, nullable=False)
    disk_available_gb = Column(Float, nullable=False)
    
    # Performance scores (0-100)
    global_inference_score = Column(Float, nullable=False)
    global_inference_label = Column(String, nullable=False)
    cpu_score = Column(Float, nullable=False)
    memory_score = Column(Float, nullable=False)
    
    # System platform
    system_platform = Column(String, nullable=True)
    
    # ============================================================================
    # COMMON ACCELERATOR FIELDS (MLX & CUDA)
    # ============================================================================
    
    gpu_name = Column(String, nullable=True)  # GPU/Accelerator name
    estimated_tflops = Column(Float, nullable=True)  # Estimated TFLOPS
    memory_bandwidth_gbs = Column(Float, nullable=True)  # Memory bandwidth
    architecture = Column(String, nullable=True)  # Architecture identifier
    gpu_score = Column(Float, nullable=True)  # GPU score (0-100)
    
    # ============================================================================
    # MLX-SPECIFIC FIELDS (Apple Silicon)
    # ============================================================================
    
    mlx_chip_model = Column(String, nullable=True)  # M1/M2/M3/M4 + variant
    mlx_gpu_cores = Column(Integer, nullable=True)  # GPU cores (8-76)
    mps_available = Column(Boolean, nullable=True)  # Metal Performance Shaders
    neural_engine_tops = Column(Float, nullable=True)  # Neural Engine TOPS
    unified_memory = Column(Boolean, nullable=True)  # Unified memory architecture
    
    # ============================================================================
    # CUDA-SPECIFIC FIELDS (NVIDIA)
    # ============================================================================
    
    cuda_cores = Column(Integer, nullable=True)  # CUDA cores
    cuda_version = Column(String, nullable=True)  # CUDA runtime version
    compute_capability = Column(String, nullable=True)  # Compute capability
    vram_total_gb = Column(Float, nullable=True)  # Total dedicated VRAM
    vram_available_gb = Column(Float, nullable=True)  # Available VRAM
    
    # ============================================================================
    # PERFORMANCE METRICS
    # ============================================================================
    
    cpu_performance_units = Column(Float, nullable=True)  # CPU performance metric
    performance_breakdown = Column(JSON, nullable=True)  # Detailed breakdown
    
    # ============================================================================
    # TIMESTAMPS
    # ============================================================================
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # ============================================================================
    # CONSTRAINTS
    # ============================================================================
    
    __table_args__ = (
        CheckConstraint(
            backend_type.in_(["mlx", "cuda", "cpu"]),
            name="valid_backend_type"
        ),
    )
