// Models the Erudi team has dev-tested end to end — plain chat AND Knowledge
// Base retrieval — on real hardware. They are pinned to the top of the browse
// list and carry a "Tested by the team" badge to steer users toward known-good
// picks.
//
// Keyed by catalog DISPLAY NAME on purpose: the name is stable across the
// per-platform snapshots (MLX on Apple Silicon, GGUF elsewhere), whereas the
// local database id and the HuggingFace link differ per platform/quant.
export const TESTED_MODEL_NAMES = new Set([
  "Qwen3 0.6B",
  "Gemma 2 2B Instruct",
  "Qwen3 4B Instruct 2507",
  "Gemma 3 4B Instruct",
  "Phi 3.5 Vision Instruct",
  "Qwen2.5 7B Instruct",
  "Llama 3.1 8B Instruct",
  "Qwen2.5 VL 7B Instruct",
]);

export function isTestedModel(model) {
  return !!model && TESTED_MODEL_NAMES.has(model.name);
}
