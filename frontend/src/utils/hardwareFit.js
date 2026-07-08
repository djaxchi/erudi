/**
 * Hardware-fit logic for the explore panel (#122 redesign).
 *
 * The startup benchmark gives a recommended parameter window [min, max] for the
 * user's machine. Here we judge each model against it so the UI can show, per
 * card, whether it fits comfortably, fits tight, or needs more memory — and draw
 * a gauge positioned against the user's budget. Pure + framework-free for tests.
 */

/** Tiers, ordered best→worst, with user-facing copy and the token color they map to. */
export const FIT_META = {
  ideal: { label: "Ideal fit", color: "var(--fit-good)", tone: "good" },
  good: { label: "Runs easily", color: "var(--fit-good)", tone: "good" },
  tight: { label: "Tight fit", color: "var(--fit-tight)", tone: "tight" },
  heavy: { label: "Needs more memory", color: "var(--fit-heavy)", tone: "heavy" },
  unknown: { label: "", color: "var(--ink-faint)", tone: "unknown" },
};

const clamp = (n, lo, hi) => Math.min(hi, Math.max(lo, n));

/** Size buckets for the catalog filter, by billions of parameters. */
export const SIZE_BUCKETS = [
  { key: "any", label: "Any size", test: () => true },
  { key: "tiny", label: "Under 2B", test: (p) => p > 0 && p < 2 },
  { key: "small", label: "2–8B", test: (p) => p >= 2 && p <= 8 },
  { key: "medium", label: "8–32B", test: (p) => p > 8 && p <= 32 },
  { key: "large", label: "32B+", test: (p) => p > 32 },
];

/**
 * Apply the catalog filters: a size bucket and an optional "only what fits this
 * machine" toggle (drops models the benchmark says need more memory).
 */
export function applyCatalogFilters(models, { size = "any", fitOnly = false } = {}, range) {
  const bucket = SIZE_BUCKETS.find((b) => b.key === size) || SIZE_BUCKETS[0];
  return models.filter((m) => {
    const p = m.param_size || 0;
    if (!bucket.test(p)) {
      return false;
    }
    if (fitOnly && fitForModel(p, range).tier === "heavy") {
      return false;
    }
    return true;
  });
}

/**
 * Rough on-device footprint in GB. Catalog models are 4-bit quants (~0.6 GB per
 * billion params incl. overhead); a non-quantized model is ~2 GB/B (fp16).
 */
export function estimateFootprintGb(paramSize, quantized = true) {
  if (!paramSize || paramSize <= 0) {
    return null;
  }
  return paramSize * (quantized === false ? 2.0 : 0.6);
}

/**
 * Classify a model against the recommended window.
 * @param {number} paramSize - billions of params
 * @param {{min:number, max:number}|null} range - recommended window from the benchmark
 * @returns {{tier:string, fraction:number, tickFraction:number} & FIT_META[tier]}
 */
export function fitForModel(paramSize, range) {
  const hasRange =
    range && typeof range.min === "number" && typeof range.max === "number" && range.max > 0;

  if (!paramSize || paramSize <= 0 || !hasRange) {
    return { tier: "unknown", fraction: 0, tickFraction: 0.5, ...FIT_META.unknown };
  }

  // The recommended max is a soft sweet-spot ceiling, not a hard limit: a model
  // marginally above it (8.03B vs an 8B window) still fits ideally. Grace bands
  // keep the 8.0-vs-8.03 boundary from flipping mint↔amber jarringly.
  const { min, max } = range;
  let tier;
  if (paramSize <= max * 1.12) {
    tier = paramSize >= min ? "ideal" : "good";
  } else if (paramSize <= max * 1.9) {
    tier = "tight";
  } else {
    tier = "heavy";
  }

  // Gauge runs 0 → 2× the comfortable ceiling; the tick sits at the ceiling (0.5).
  const fraction = clamp(paramSize / (max * 2), 0.03, 1);
  return { tier, fraction, tickFraction: 0.5, ...FIT_META[tier] };
}

/**
 * Order models best-fit first for the "Recommended for your machine" rail:
 * ideal → good → tight → heavy, then larger-within-tier first (more capable).
 */
const TIER_RANK = { ideal: 0, good: 1, tight: 2, heavy: 3, unknown: 4 };
export function rankByFit(models, range) {
  return [...models]
    .map((m) => ({ m, fit: fitForModel(m.param_size, range) }))
    .sort((a, b) => {
      const t = TIER_RANK[a.fit.tier] - TIER_RANK[b.fit.tier];
      return t !== 0 ? t : (b.m.param_size || 0) - (a.m.param_size || 0);
    })
    .map((x) => x.m);
}

// Families a newcomer recognizes — recommendations lead with these, in order.
const FLAGSHIP_FAMILIES = [
  "llama",
  "qwen",
  "gemma",
  "mistral",
  "phi",
  "deepseek",
  "granite",
  "glm",
];

const isInstruct = (model) => /instruct|chat/i.test(model.name || "");

/**
 * The flagship picks for the recommendation rail: one well-known, chat-ready model
 * per family (Llama, Qwen, Gemma…), each the most capable that still runs on this
 * machine — never a raw base model (newcomers don't know base vs instruct), never
 * one that needs more memory. Falls back to fill the count from any flagship family.
 */
export function pickFlagships(models, range, count = 3) {
  const pool = models.filter(
    (m) =>
      m.runnable !== false &&
      (m.category || "general") === "general" &&
      isInstruct(m) &&
      // Never recommend a model whose size we couldn't measure (#201): its fit is
      // unknowable, so it can't earn a "runs on your machine" flagship slot.
      typeof m.param_size === "number" &&
      m.param_size > 0
  );
  const picks = [];
  const chosen = new Set();

  for (const family of FLAGSHIP_FAMILIES) {
    const inFamily = pool.filter((m) => (m.type || "").toLowerCase() === family);
    const best = rankByFit(inFamily, range)[0];
    if (best && fitForModel(best.param_size, range).tier !== "heavy") {
      picks.push(best);
      chosen.add(best.id ?? best.link);
    }
    if (picks.length >= count) {
      break;
    }
  }

  if (picks.length < count) {
    const filler = rankByFit(pool, range).filter(
      (m) => !chosen.has(m.id ?? m.link) && fitForModel(m.param_size, range).tier !== "heavy"
    );
    for (const m of filler) {
      if (picks.length >= count) {
        break;
      }
      picks.push(m);
    }
  }
  return picks.slice(0, count);
}
