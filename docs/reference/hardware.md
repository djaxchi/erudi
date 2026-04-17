# Hardware Domain

Backend-agnostic hardware detection and performance evaluation for MLX (Apple Silicon), CUDA (NVIDIA), and CPU fallback.

## Overview

The hardware domain provides comprehensive hardware detection and performance scoring across all supported backends:

- **MLX**: Apple Silicon (M1/M2/M3/M4) with unified memory and Neural Engine
- **CUDA**: NVIDIA GPUs with dedicated VRAM and CUDA cores
- **CPU**: CPU-only fallback for unsupported hardware

### Architecture

```
Endpoints → Service → Repository → Entity → Database
                ↓
            Engine (MLX/CUDA/CPU)
```

**Key Features:**

- Discriminated unions for type-safe backend-specific fields
- Raw and boosted scores for transparency
- Typed performance breakdown
- Hardware refresh endpoint
- Frontend utility for multi-backend support

## API Endpoints

### GET /hardware/training_info

Get full backend-specific hardware profile for training page UI.

**Response:** Returns complete hardware information via discriminated union.

```json
{
  "hardware": {
    "backend_type": "mlx",
    "mlx_chip_model": "M3 Max",
    "mlx_gpu_cores": 40,
    "cpu_model": "Apple M3 Max",
    "total_memory_gb": 128.0,
    "available_memory_gb": 120.5,
    "disk_total_gb": 1000.0,
    "disk_available_gb": 750.0,
    "raw_inference_score": 85.0,
    "raw_finetuning_score": 80.0,
    "global_inference_label": "Excellent",
    "global_finetuning_label": "Excellent",
    "cpu_score": 75.0,
    "memory_score": 90.0,
    "gpu_score": 95.0,
    "mps_available": true,
    "neural_engine_tops": 18.0,
    "unified_memory": true,
    "estimated_tflops": 14.0,
    "memory_bandwidth_gbs": 400.0,
    "architecture": "3nm",
    "system_platform": "Darwin"
  },
  "performance_breakdown": {
    "compute_score": 95.0,
    "memory_bandwidth_score": 92.0,
    "memory_capacity_score": 88.0,
    "cpu_performance_score": 75.0,
    "disk_score": 75.0
  }
}
```

**Backend-Specific Fields:**

| Backend | Unique Fields |
|---------|--------------|
| **MLX** | `mlx_chip_model`, `mlx_gpu_cores`, `mps_available`, `neural_engine_tops` |
| **CUDA** | `gpu_name`, `cuda_cores`, `cuda_version`, `compute_capability`, `vram_total_gb`, `vram_available_gb` |
| **CPU** | `compute_units`, `cpu_performance_units`, `accelerator_available` |

### GET /hardware/app_startup

Get minimal performance scores for application startup dashboard.

**Response:** Returns boosted scores (+20 points, capped at 100) alongside raw scores.

```json
{
  "backend_type": "cuda",
  "global_finetuning_score": 95.0,
  "global_finetuning_label": "Excellent",
  "global_inference_score": 100.0,
  "global_inference_label": "Excellent",
  "raw_finetuning_score": 75.0,
  "raw_inference_score": 82.0
}
```

**Score Boosting Logic:**

- Boosted = `min(100, raw + 20)`
- Purpose: More user-friendly display without losing transparency
- Raw scores always included for comparison

### GET /hardware/detailed

Get comprehensive hardware diagnostics with full data.

**Response:** Complete backend-specific profile plus raw/boosted comparison.

```json
{
  "hardware": { /* Full backend-specific schema */ },
  "performance_breakdown": { /* Typed breakdown */ },
  "boosted_inference_score": 85.0,
  "boosted_finetuning_score": 75.0
}
```

**Use Cases:**

- Debugging hardware detection issues
- Comparing raw vs boosted scores
- Analyzing performance breakdown components

### POST /hardware/refresh

Force hardware re-detection and update cached profile.

**Request:** No body required.

**Response:**

```json
{
  "message": "Hardware profile refreshed successfully",
  "backend_type": "mlx"
}
```

**When to Use:**

- After hardware changes (RAM upgrade, new GPU)
- To refresh dynamic fields (available_memory_gb, disk_available_gb)
- Troubleshooting stale hardware data

## Schemas

### Discriminated Unions

All endpoint responses use discriminated unions based on `backend_type` for type safety.

```python
from typing import Union, Literal
from pydantic import BaseModel, Field

class BaseHardwareInfo(BaseModel):
    backend_type: Literal["mlx", "cuda", "cpu"]
    cpu_model: str
    total_memory_gb: float
    # ... common fields

class MLXHardwareInfo(BaseHardwareInfo):
    backend_type: Literal["mlx"] = "mlx"
    mlx_chip_model: str
    mlx_gpu_cores: int
    # ... MLX-specific fields

# Union type for endpoints
HardwareUnion = Union[MLXHardwareInfo, CUDAHardwareInfo, CPUHardwareInfo]
```

### PerformanceBreakdown

Typed performance metrics (replaces `Dict[str, Any]`):

```python
class PerformanceBreakdown(BaseModel):
    compute_score: float  # GPU/CPU compute capability (0-100)
    memory_bandwidth_score: float  # Memory bandwidth (0-100)
    memory_capacity_score: float  # Memory capacity (0-100)
    cpu_performance_score: float  # CPU performance (0-100)
    disk_score: Optional[float]  # Disk storage (0-100)
```

## Scoring Methodology

### Inference Score

**Weights by Backend:**

| Component | MLX | CUDA | CPU |
|-----------|-----|------|-----|
| GPU Compute | 35% | 40% | 0% |
| Memory Bandwidth | 30% | 30% | 20% |
| Memory Capacity | 20% | 15% | 30% |
| Neural Engine | 10% | 0% | 0% |
| CPU | 5% | 5% | 40% |
| Disk | 0% | 10% | 10% |

### Fine-Tuning Score

**Weights by Backend:**

| Component | MLX | CUDA | CPU |
|-----------|-----|------|-----|
| Memory Capacity | 40% | 45% | 50% |
| GPU Compute | 25% | 35% | 0% |
| Memory Bandwidth | 20% | 15% | 5% |
| Neural Engine | 10% | 0% | 0% |
| CPU | 5% | 5% | 30% |
| Disk | 0% | 0% | 15% |

### Normalization Factors

**MLX (Apple Silicon):**
- GPU Cores: 40 cores = 100 points
- Memory: 128GB = 100 points
- Bandwidth: 400 GB/s = 100 points
- Neural Engine: 38 TOPS = 100 points

**CUDA (NVIDIA):**
- CUDA Cores: 10,240 cores = 100 points
- Memory: 48GB VRAM = 100 points
- Bandwidth: 800 GB/s = 100 points
- TFLOPS: 40 TFLOPS = 100 points

**CPU (Fallback):**
- CPU Cores: 64 cores = 100 points
- Memory: 128GB = 100 points
- Bandwidth: 100 GB/s (estimated) = 100 points
- Disk: 500GB available = 100 points

### Label Mapping

| Score Range | Label |
|-------------|-------|
| 85-100 | Amazing |
| 70-84 | Excellent |
| 55-69 | Very Good |
| 40-54 | Good |
| 25-39 | Medium |
| 10-24 | Poor |
| 0-9 | Terrible |

## Frontend Integration

### Transform Utility

Use `hardwareTransform.js` to handle discriminated union responses:

```javascript
import { transformTrainingInfo, transformAppStartupInfo } from '../utils/hardwareTransform';

// Training info endpoint
const response = await fetch('/hardware/training_info');
const data = await response.json();
const hw = transformTrainingInfo(data);

// Backend-specific rendering
if (hw.is_mlx) {
  console.log(`Chip: ${hw.chip_model}`);
  console.log(`GPU Cores: ${hw.gpu_cores}`);
} else if (hw.is_cuda) {
  console.log(`GPU: ${hw.gpu_model}`);
  console.log(`CUDA Cores: ${hw.cuda_cores}`);
  console.log(`VRAM: ${hw.gpu_vram_total}`);
} else {
  console.log(`CPU Only: ${hw.cpu_model}`);
}
```

### Component Usage

**Training Page:**

```jsx
import { transformTrainingInfo } from '../utils/hardwareTransform';

const [hw, setHw] = useState({});

useEffect(() => {
  fetch(`${API_BASE_URL}/hardware/training_info`)
    .then(res => res.json())
    .then(data => setHw(transformTrainingInfo(data)))
    .catch(err => setHw(getErrorHardwareData()));
}, []);

// Render with backend-aware logic
<HardwareInfo hw={hw} />
```

**App Startup:**

```jsx
import { transformAppStartupInfo } from '../utils/hardwareTransform';

const fetchHardware = async () => {
  const res = await fetch('/hardware/app_startup');
  const data = await res.json();
  const transformed = transformAppStartupInfo(data);
  
  // Access raw and boosted scores
  console.log(`Raw: ${transformed.raw_inference_score}`);
  console.log(`Boosted: ${transformed.global_inference_score}`);
};
```

## Service Layer

### Hardware_Service

Business logic for hardware operations.

**Key Methods:**

```python
from src.domains.hardware.services import Hardware_Service

service = Hardware_Service(repository)

# Get or create profile (cached)
profile = service.get_or_create_profile()

# Calculate raw + boosted scores
scores = service.calculate_boosted_scores(profile)
# Returns: {
#   "raw_inference_score": 65.0,
#   "boosted_inference_score": 85.0,
#   "global_inference_label": "Excellent",
#   ...
# }

# Warm up accelerator before benchmarking
success = service.warm_up(duration_seconds=5)

# Force hardware refresh
profile = service.refresh_profile()
db.commit()
```

## Engine Integration

### Hardware Detection Methods

All engines (MLX/CUDA/CPU) implement:

```python
@classmethod
def get_hardware_info(cls) -> Dict[str, Any]:
    """Get system hardware information."""
    
@classmethod
def warm_up_accelerator(cls, duration_seconds: float) -> bool:
    """Warm up GPU/accelerator."""
    
@classmethod
def get_performance_evaluation(cls) -> Dict[str, Any]:
    """Calculate performance scores."""
```

### CPU_Engine Enhancements

**Hardware Detection:**

- Uses `psutil` for memory/disk info
- Uses `cpuinfo` for enhanced CPU model detection
- Estimates memory bandwidth: `1.5 GB/s per core`

**Performance Scoring:**

```python
# Inference weights
INF_WEIGHTS = {
    "cpu": 0.40,
    "memory_capacity": 0.30,
    "memory_bandwidth": 0.20,
    "disk": 0.10
}

# Fine-tuning weights
FT_WEIGHTS = {
    "memory_capacity": 0.50,
    "cpu": 0.30,
    "disk": 0.15,
    "memory_bandwidth": 0.05
}
```

## Database Entity

### HardwareProfile

Singleton entity (always `id=1`) with backend-agnostic columns:

```python
class HardwareProfile(Base):
    __tablename__ = "hardware_profiles"
    
    id = Column(Integer, primary_key=True)
    backend_type = Column(String)  # Discriminator
    
    # Common fields
    cpu_model = Column(String)
    total_memory_gb = Column(Float)
    available_memory_gb = Column(Float)
    
    # MLX-specific (nullable)
    mlx_chip_model = Column(String, nullable=True)
    mlx_gpu_cores = Column(Integer, nullable=True)
    neural_engine_tops = Column(Float, nullable=True)
    
    # CUDA-specific (nullable)
    cuda_cores = Column(Integer, nullable=True)
    cuda_version = Column(String, nullable=True)
    compute_capability = Column(String, nullable=True)
    vram_total_gb = Column(Float, nullable=True)
    
    # CPU-specific (nullable)
    compute_units = Column(Integer, nullable=True)
    cpu_performance_units = Column(Integer, nullable=True)
    
    # Performance scores (raw, no boost)
    global_inference_score = Column(Float)
    global_finetuning_score = Column(Float)
    
    # Performance breakdown (JSON)
    performance_breakdown = Column(JSON, nullable=True)
```

## Migration Guide

### From Old API Structure

**Old Response (Flat):**

```json
{
  "backend_type": "mlx",
  "chip_model": "M3 Max",
  "gpu_cores": 40,
  "global_finetuning_score": 95.0
}
```

**New Response (Nested):**

```json
{
  "hardware": {
    "backend_type": "mlx",
    "mlx_chip_model": "M3 Max",
    "mlx_gpu_cores": 40,
    "raw_finetuning_score": 75.0
  },
  "performance_breakdown": { /* ... */ }
}
```

**Frontend Migration:**

```javascript
// OLD
const hw = await fetch('/hardware/training_info').then(r => r.json());
console.log(hw.chip_model);

// NEW (use transform utility)
import { transformTrainingInfo } from '../utils/hardwareTransform';
const data = await fetch('/hardware/training_info').then(r => r.json());
const hw = transformTrainingInfo(data);
console.log(hw.chip_model);  // Still works!
```

## Troubleshooting

### Issue: Stale Hardware Data

**Solution:** Use refresh endpoint

```bash
curl -X POST http://localhost:8000/hardware/refresh
```

### Issue: Frontend Shows "Error fetching"

**Causes:**

1. Backend not running
2. Network error
3. Schema validation failed

**Debug:**

```javascript
fetch('/hardware/training_info')
  .then(r => {
    console.log('Status:', r.status);
    return r.json();
  })
  .then(data => {
    console.log('Raw data:', data);
    const transformed = transformTrainingInfo(data);
    console.log('Transformed:', transformed);
  })
  .catch(err => console.error('Error:', err));
```

### Issue: Missing Backend-Specific Fields

**Check backend_type discriminator:**

```javascript
if (hw.backend_type === "mlx") {
  // MLX-specific fields available
  console.log(hw.mlx_chip_model);
} else if (hw.backend_type === "cuda") {
  // CUDA-specific fields available
  console.log(hw.cuda_cores);
}
```

## Code Reference

::: src.domains.hardware.endpoints

::: src.domains.hardware.schemas

::: src.domains.hardware.services

