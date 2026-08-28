// Per-model sampling defaults (#388).
//
// The backend resolves, per catalog row, the sampling a fresh conversation or
// arena panel should start from (`sampling_defaults`: curated profile > the
// base repo's generation_config.json > fallback) and the ceiling of the
// max-tokens field (`max_tokens_cap` = min(model context window, engine
// window)). The UI seeds its sliders from that block and never hard-codes a
// per-model value itself.
//
// The fallback mirrors the backend's constants (src/database/generation_hints.py):
// 0.2 / 0.95 / 1024, validated by the #129 eval campaign, and the API's own
// max_tokens upper bound as the cap.
export const FALLBACK_SAMPLING = Object.freeze({
  temperature: 0.2,
  topP: 0.95,
  maxTokens: 1024,
  maxTokensCap: 32768,
});

const numberOr = (value, fallback) =>
  typeof value === "number" && Number.isFinite(value) ? value : fallback;

/**
 * The sampling a panel should start from for `model` (a `/llms/local` row or
 * null), in the UI's camelCase shape. Always a fresh object; falls back per
 * key so a partial block never yields NaN sliders.
 */
export function defaultsFor(model) {
  const block = model?.sampling_defaults;
  if (!block || typeof block !== "object") {
    return { ...FALLBACK_SAMPLING };
  }
  const maxTokensCap = Math.max(
    1,
    Math.trunc(numberOr(block.max_tokens_cap, FALLBACK_SAMPLING.maxTokensCap))
  );
  const maxTokens = Math.max(
    1,
    Math.trunc(numberOr(block.max_tokens, FALLBACK_SAMPLING.maxTokens))
  );
  return {
    temperature: numberOr(block.temperature, FALLBACK_SAMPLING.temperature),
    topP: numberOr(block.top_p, FALLBACK_SAMPLING.topP),
    maxTokens: Math.min(maxTokens, maxTokensCap),
    maxTokensCap,
  };
}
