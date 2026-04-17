/**
 * Hardware data transformation utilities.
 *
 * Handles backend-agnostic hardware data from API endpoints,
 * transforming discriminated union responses into UI-friendly format.
 *
 * Supports:
 * - MLX (Apple Silicon)
 * - CUDA (NVIDIA GPUs)
 * - CPU (fallback)
 */

/**
 * Transform training_info endpoint response to UI format.
 *
 * @param {Object} data - API response from /hardware/training_info
 * @returns {Object} UI-friendly hardware object
 */
export function transformTrainingInfo(data) {
  if (!data || !data.hardware) {
    return getErrorHardwareData();
  }

  const hw = data.hardware;
  const backend = hw.backend_type;

  // Common fields (available for all backends)
  const result = {
    backend_type: backend,
    storage_path: "coming soon...", // Not yet implemented in backend
    ram_available: `${hw.available_memory_gb} GB`,
    total_ram_gb: `${hw.total_memory_gb} GB`,
    disk_available: `${hw.disk_available_gb} GB`,
    cpu_model: hw.cpu_model,

    // Performance scores (raw scores from engine)
    global_finetuning_score: `${hw.raw_finetuning_score}/100`,
    global_finetuning_label: hw.global_finetuning_label,
    global_inference_score: `${hw.raw_inference_score}/100`,
    global_inference_label: hw.global_inference_label,
    cpu_score: `${hw.cpu_score}/100`,
    memory_score: `${hw.memory_score}/100`,

    // Backend flags
    is_mlx: backend === "mlx",
    is_cuda: backend === "cuda",
    is_cpu: backend === "cpu",
  };

  // Backend-specific fields
  if (backend === "mlx") {
    // Apple Silicon specific
    result.gpu_model = `Apple ${hw.mlx_chip_model} GPU`;
    result.chip_model = hw.mlx_chip_model;
    result.gpu_cores = `${hw.mlx_gpu_cores} cores`;
    result.estimated_gpu_tflops = hw.estimated_tflops ? `${hw.estimated_tflops} TFLOPS` : "N/A";
    result.memory_bandwidth_gbs = hw.memory_bandwidth_gbs
      ? `${hw.memory_bandwidth_gbs} GB/s`
      : "N/A";
    result.neural_engine_tops = `${hw.neural_engine_tops} TOPS`;
    result.architecture = hw.architecture || "Unknown";
    result.is_apple_silicon = true;
    result.mps_available = hw.mps_available;
    result.unified_memory = hw.unified_memory;
    result.gpu_vram_total = "Unified Memory";
    result.gpu_eval_score = `${hw.gpu_score}/100`;
  } else if (backend === "cuda") {
    // NVIDIA GPU specific
    result.gpu_model = hw.gpu_name;
    result.chip_model = hw.gpu_name;
    result.gpu_cores = `${hw.cuda_cores} CUDA cores`;
    result.cuda_cores = hw.cuda_cores;
    result.compute_capability = hw.compute_capability;
    result.cuda_version = hw.cuda_version;
    result.estimated_gpu_tflops = `${hw.estimated_tflops} TFLOPS`;
    result.memory_bandwidth_gbs = hw.memory_bandwidth_gbs
      ? `${hw.memory_bandwidth_gbs} GB/s`
      : "N/A";
    result.neural_engine_tops = "N/A";
    result.architecture = hw.architecture || "Unknown";
    result.is_apple_silicon = false;
    result.mps_available = false;
    result.unified_memory = false;
    result.gpu_vram_total = `${hw.vram_total_gb} GB`;
    result.vram_available = `${hw.vram_available_gb} GB`;
    result.gpu_eval_score = `${hw.gpu_score}/100`;
  } else {
    // CPU fallback (no GPU)
    result.gpu_model = "CPU Only (No GPU detected)";
    result.chip_model = "CPU Only";
    result.gpu_cores = "N/A";
    result.estimated_gpu_tflops = "N/A";
    result.memory_bandwidth_gbs = hw.memory_bandwidth_gbs
      ? `${hw.memory_bandwidth_gbs} GB/s`
      : "N/A";
    result.neural_engine_tops = "N/A";
    result.architecture = hw.architecture || "Unknown";
    result.is_apple_silicon = false;
    result.mps_available = false;
    result.unified_memory = false;
    result.gpu_vram_total = "No GPU";
    result.gpu_eval_score = "0/100";
    result.compute_units = hw.compute_units;
    result.cpu_performance_units = hw.cpu_performance_units;
  }

  return result;
}

/**
 * Transform app_startup endpoint response to UI format.
 *
 * @param {Object} data - API response from /hardware/app_startup
 * @returns {Object} UI-friendly hardware object with boosted scores
 */
export function transformAppStartupInfo(data) {
  if (!data) {
    return {
      backend_type: "unknown",
      global_finetuning_score: 0,
      global_finetuning_label: "Unknown",
      global_inference_score: 0,
      global_inference_label: "Unknown",
      raw_finetuning_score: 0,
      raw_inference_score: 0,
    };
  }

  return {
    backend_type: data.backend_type,
    // Boosted scores for UI display
    global_finetuning_score: data.global_finetuning_score,
    global_finetuning_label: data.global_finetuning_label,
    global_inference_score: data.global_inference_score,
    global_inference_label: data.global_inference_label,
    // Raw scores for transparency
    raw_finetuning_score: data.raw_finetuning_score,
    raw_inference_score: data.raw_inference_score,
  };
}

/**
 * Get default error hardware data.
 *
 * @returns {Object} Error state hardware object
 */
function getErrorHardwareData() {
  return {
    backend_type: "unknown",
    storage_path: "Error fetching",
    ram_available: "Error fetching",
    total_ram_gb: "Error fetching",
    disk_available: "Error fetching",
    cpu_model: "Error fetching",
    gpu_model: "Error fetching",
    chip_model: "Error fetching",
    gpu_cores: "Error fetching",
    estimated_gpu_tflops: "Error fetching",
    memory_bandwidth_gbs: "Error fetching",
    neural_engine_tops: "Error fetching",
    architecture: "Error fetching",
    is_apple_silicon: false,
    is_mlx: false,
    is_cuda: false,
    is_cpu: false,
    mps_available: false,
    unified_memory: false,
    gpu_vram_total: "Error fetching",
    global_finetuning_score: "Error fetching",
    global_finetuning_label: "Error fetching",
    global_inference_score: "Error fetching",
    global_inference_label: "Error fetching",
    cpu_score: "Error fetching",
    gpu_eval_score: "Error fetching",
    memory_score: "Error fetching",
  };
}
