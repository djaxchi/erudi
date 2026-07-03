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
 * Transform app_startup endpoint response to UI format.
 *
 * @param {Object} data - API response from /hardware/app_startup
 * @returns {Object} UI-friendly hardware object with boosted scores
 */
export function transformAppStartupInfo(data) {
  if (!data) {
    return {
      backend_type: "unknown",
      global_inference_score: 0,
      global_inference_label: "Unknown",
      raw_inference_score: 0,
      recommended_param_min: null,
      recommended_param_max: null,
    };
  }

  return {
    backend_type: data.backend_type,
    // Boosted score for UI display
    global_inference_score: data.global_inference_score,
    global_inference_label: data.global_inference_label,
    // Raw score for transparency
    raw_inference_score: data.raw_inference_score,
    // Hardware-fit model size window (billions of params) for "Models For You" (#86)
    recommended_param_min: data.recommended_param_min,
    recommended_param_max: data.recommended_param_max,
  };
}
