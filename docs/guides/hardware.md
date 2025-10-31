# 🖥️ Guide — Hardware Detection & Performance

User guide for understanding hardware detection, performance scores, and multi-backend support.

## Overview

Erudi automatically detects your hardware and optimizes performance based on available resources:

- **Apple Silicon (M1/M2/M3/M4)**: Uses Metal Performance Shaders (MPS) and unified memory
- **NVIDIA GPUs**: Uses CUDA for GPU acceleration
- **CPU Fallback**: Runs on any system when GPU is unavailable

## How Hardware Detection Works

### Automatic Backend Selection

When you start Erudi, it automatically:

1. **Checks for Apple Silicon** → Uses MLX backend if detected
2. **Checks for NVIDIA GPU** → Uses CUDA backend if available
3. **Falls back to CPU** → Uses CPU-only backend for unsupported hardware

```
Priority: MLX > CUDA > CPU
```

### What Gets Detected

**All Backends:**
- CPU model and core count
- Total and available RAM
- Disk space (total and available)
- Operating system and architecture

**MLX (Apple Silicon) Specific:**
- Chip model (e.g., "M3 Max", "M4 Pro")
- GPU core count
- Neural Engine TOPS
- Memory bandwidth
- MPS (Metal Performance Shaders) availability

**CUDA (NVIDIA) Specific:**
- GPU model name
- CUDA core count
- CUDA runtime version
- Compute capability (e.g., "8.6")
- VRAM (total and available)
- Memory bandwidth

**CPU Specific:**
- Logical core count
- Estimated memory bandwidth
- No GPU acceleration

## Performance Scores Explained

### Score Range: 0-100

Erudi calculates two main scores for your hardware:

1. **Inference Score**: How fast your system can generate text
2. **Fine-Tuning Score**: How well your system can train models

### Score Labels

| Score | Label | Meaning |
|-------|-------|---------|
| 85-100 | **Amazing** | Top-tier hardware, excellent for large models |
| 70-84 | **Excellent** | High-end hardware, great for most use cases |
| 55-69 | **Very Good** | Mid-high range, good for medium models |
| 40-54 | **Good** | Mid-range, suitable for smaller models |
| 25-39 | **Medium** | Entry-level, may struggle with large models |
| 10-24 | **Poor** | Limited capability, small models only |
| 0-9 | **Terrible** | Very limited, not recommended |

### What Affects Your Score?

**For Inference (Text Generation):**

- **GPU/CPU Power** (35-40%): More cores = faster generation
- **Memory Bandwidth** (20-30%): How fast data moves between components
- **RAM Capacity** (15-30%): Larger models need more memory
- **Storage** (10%): For loading models

**For Fine-Tuning (Training):**

- **Memory Capacity** (40-50%): Training needs significant RAM/VRAM
- **GPU/CPU Power** (25-35%): Training is compute-intensive
- **Memory Bandwidth** (5-20%): Data transfer matters for training
- **Storage** (15%): Saving checkpoints and datasets

### Boosted Scores in UI

The UI shows **boosted scores** (+20 points, max 100) to make them more user-friendly:

```
Raw score: 65/100 → UI shows: 85/100 ("Excellent")
Raw score: 82/100 → UI shows: 100/100 ("Amazing")
```

**Why?** Most modern hardware is quite capable, and the boost reflects practical real-world performance.

**Transparency**: Both raw and boosted scores are available via API for debugging.

## Viewing Hardware Information

### Training Page

Shows detailed hardware specs:

- **Available Storage**: Free disk space for models
- **Total RAM**: System memory capacity
- **CPU Model**: Processor information
- **GPU Information**:
  - MLX: Chip model, GPU cores, Neural Engine
  - CUDA: GPU name, CUDA cores, VRAM
  - CPU: "No GPU detected"
- **Fine-Tuning Rating**: Overall training capability

### Landing Page

Shows quick performance summary on startup:

- Backend type (MLX/CUDA/CPU)
- Inference score and label
- Fine-tuning score and label

### Dataset Card

Shows device used for training:

- **Apple Silicon**: "Apple M3 Max GPU (128 GB Unified Memory)"
- **NVIDIA**: "NVIDIA RTX 4090 (24 GB VRAM)"
- **CPU**: "Intel Core i9-13900K (64 GB RAM)"

## Multi-Backend Compatibility

### Same UI, Different Hardware

Erudi's UI adapts automatically to your backend:

**MLX Users See:**
```
Chip: M3 Max
GPU Cores: 40 cores
Neural Engine: 18.0 TOPS
Memory: Unified Memory
```

**CUDA Users See:**
```
GPU: NVIDIA RTX 4090
CUDA Cores: 16,384 cores
VRAM: 24 GB
Compute: 8.9
```

**CPU Users See:**
```
CPU: Intel Core i9-13900K
Cores: 24 cores
RAM: 64 GB
GPU: No GPU detected
```

### Performance Differences

Expected performance by backend (for similar-sized models):

| Backend | Relative Speed | Best For |
|---------|---------------|----------|
| **MLX (M3 Max)** | 1.0x (baseline) | Mac users, great balance |
| **CUDA (RTX 4090)** | 1.5-2.5x | Windows/Linux, maximum speed |
| **CPU (High-end)** | 0.1-0.2x | No GPU, slower but works |

## Refreshing Hardware Data

### When to Refresh

Refresh hardware detection if you:

- Upgraded RAM
- Added/removed a GPU
- Connected external GPU (eGPU)
- Notice incorrect specs

### How to Refresh

**Via API** (for developers):

```bash
curl -X POST http://localhost:8000/hardware/refresh
```

**Via UI** (coming soon):

- Settings → Hardware → Refresh

**Via App Restart**:

Hardware is re-detected on every app launch.

## Troubleshooting

### Hardware Shows "Error fetching"

**Possible Causes:**

1. Backend not running
2. Hardware detection failed
3. Permissions issue (rare)

**Solutions:**

1. Restart Erudi
2. Check backend logs for errors
3. Try refreshing hardware data

### Incorrect GPU Detected

**Example**: Shows CPU when you have a GPU

**For NVIDIA GPUs:**

1. Check CUDA is installed: `nvidia-smi`
2. Check PyTorch CUDA: `python -c "import torch; print(torch.cuda.is_available())"`
3. Reinstall CUDA drivers if needed

**For Apple Silicon:**

- Erudi should auto-detect, no drivers needed
- Make sure you're on macOS (not Rosetta)

### Low Performance Score

**Your score depends on:**

- Hardware age (older chips score lower)
- Available resources (close other apps)
- Thermal throttling (ensure good cooling)

**Improving scores:**

- Upgrade RAM (helps fine-tuning)
- Upgrade GPU (helps both inference and training)
- Close background applications
- Ensure adequate cooling

### Unified Memory vs VRAM

**Apple Silicon (MLX):**

- Uses **unified memory** (shared between CPU/GPU)
- More flexible than dedicated VRAM
- Shows as "Unified Memory" in UI

**NVIDIA (CUDA):**

- Uses **dedicated VRAM** (GPU-only memory)
- Faster than system RAM for GPU tasks
- Shows as "XX GB VRAM" in UI

**CPU:**

- Uses **system RAM** only
- Slower for ML tasks than GPU memory
- Shows as "XX GB RAM" in UI

## Understanding Backend Selection

### Why MLX for Mac?

- **Native**: Built specifically for Apple Silicon
- **Efficient**: Optimized for unified memory architecture
- **Fast**: Metal Performance Shaders acceleration
- **No drivers**: Just works on macOS

### Why CUDA for NVIDIA?

- **Mature**: Industry-standard GPU computing
- **Fast**: Dedicated VRAM and tensor cores
- **Powerful**: Supports massive models
- **Widely supported**: Excellent library ecosystem

### Why CPU Fallback?

- **Universal**: Works on any system
- **Reliable**: No driver dependencies
- **Slower**: 10-50x slower than GPU
- **Last resort**: Use only if no GPU available

## API Endpoints for Developers

### Get Training Info

```bash
curl http://localhost:8000/hardware/training_info
```

Returns full backend-specific hardware profile.

### Get Startup Info

```bash
curl http://localhost:8000/hardware/app_startup
```

Returns minimal UI data with boosted scores.

### Get Detailed Info

```bash
curl http://localhost:8000/hardware/detailed
```

Returns comprehensive diagnostics with raw/boosted comparison.

### Refresh Hardware

```bash
curl -X POST http://localhost:8000/hardware/refresh
```

Forces hardware re-detection.

## Best Practices

### For Optimal Performance

1. **Close unnecessary applications** before training
2. **Ensure adequate cooling** for sustained performance
3. **Use SSD** for faster model loading
4. **Monitor memory usage** during training
5. **Update drivers** (NVIDIA users)

### For Different Hardware Tiers

**High-End (Score 80+)**:

- Train large models (7B-13B parameters)
- Use higher batch sizes
- Fine-tune with larger datasets

**Mid-Range (Score 50-80)**:

- Train medium models (3B-7B parameters)
- Use moderate batch sizes
- Fine-tune with medium datasets

**Entry-Level (Score < 50)**:

- Use small models (1B-3B parameters)
- Use small batch sizes
- Consider quantized models (4-bit)

## FAQ

**Q: Can I use both MLX and CUDA?**  
A: No, Erudi selects one backend per session based on detection priority.

**Q: Will CPU backend damage my computer?**  
A: No, it's completely safe. Just slower than GPU.

**Q: Why is my score lower than expected?**  
A: Scores are calibrated across all hardware types. A "Good" score is still quite capable.

**Q: Can I manually select backend?**  
A: Not yet, but coming in future versions. Currently auto-detected.

**Q: Does higher score mean better models?**  
A: Higher score means faster training/inference, not better model quality. Quality depends on training data and hyperparameters.

**Q: What if I have multiple GPUs?**  
A: CUDA backend will use the primary GPU. Multi-GPU support coming soon.

## Technical Details

For developers wanting to understand the scoring algorithms, normalization factors, and backend implementation details, see:

- [Hardware Domain Reference](../reference/hardware.md)
- [Engine Architecture](../dev/architecture/engines.md)
- [Performance Evaluation](../dev/architecture/performance.md)
