/**
 * Hardware-fit logic for the explore panel (#122 redesign).
 *
 * The startup benchmark gives a recommended parameter window [min, max] for the
 * user's machine. Here we judge each model against it so the UI can show, per
 * card, whether it fits comfortably, fits tight, or needs more memory — and draw
 * a gauge positioned against the user's budget. Pure + framework-free for tests
 * (the only side effect is reading the active translation for the labels).
 */
import i18n from "../i18n";

/**
 * Tiers, ordered best→worst, with the translation key of their user-facing copy
 * and the token color they map to. `fitForModel` resolves the key at call time
 * so a language switch is reflected on the next render.
 */
export const FIT_META = {
  ideal: { labelKey: "models:fit.labels.ideal", color: "var(--fit-good)", tone: "good" },
  good: { labelKey: "models:fit.labels.good", color: "var(--fit-good)", tone: "good" },
  tight: { labelKey: "models:fit.labels.tight", color: "var(--fit-tight)", tone: "tight" },
  heavy: { labelKey: "models:fit.labels.heavy", color: "var(--fit-heavy)", tone: "heavy" },
  unknown: { labelKey: null, color: "var(--ink-faint)", tone: "unknown" },
};

const fitLabel = (tier) => (FIT_META[tier].labelKey ? i18n.t(FIT_META[tier].labelKey) : "");

const clamp = (n, lo, hi) => Math.min(hi, Math.max(lo, n));

/**
 * Size buckets for the catalog filter, by billions of parameters. `labelKey` is
 * the translation key of the chip label (components resolve it with `t`).
 */
export const SIZE_BUCKETS = [
  { key: "any", labelKey: "models:sizeBuckets.any", test: () => true },
  { key: "tiny", labelKey: "models:sizeBuckets.tiny", test: (p) => p > 0 && p < 2 },
  { key: "small", labelKey: "models:sizeBuckets.small", test: (p) => p >= 2 && p <= 8 },
  { key: "medium", labelKey: "models:sizeBuckets.medium", test: (p) => p > 8 && p <= 32 },
  { key: "large", labelKey: "models:sizeBuckets.large", test: (p) => p > 32 },
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
    if (fitOnly && fitForCatalogModel(m, range).tier === "heavy") {
      return false;
    }
    return true;
  });
}

/**
 * GB of weights per billion parameters at 4-bit, overhead included. The same
 * coefficient the backend uses to turn usable memory into the recommended
 * parameter window (`_GB_PER_BILLION_PARAMS_Q4`), which is what lets a measured
 * size be judged against that window.
 */
export const GB_PER_BILLION_PARAMS_Q4 = 0.6;

// The backend measures and labels sizes in decimal GB (1e9 bytes) so a model
// does not "shrink" between the catalog and its installed card.
export const BYTES_PER_GB = 1_000_000_000;

/**
 * Rough on-device footprint in GB. Catalog models are 4-bit quants (~0.6 GB per
 * billion params incl. overhead); a non-quantized model is ~2 GB/B (fp16).
 */
export function estimateFootprintGb(paramSize, quantized = true) {
  if (!paramSize || paramSize <= 0) {
    return null;
  }
  return paramSize * (quantized === false ? 2.0 : GB_PER_BILLION_PARAMS_Q4);
}

/** The measured download size in decimal GB, or null when it is not a positive number. */
export function measuredSizeGb(model) {
  const bytes = model?.artifact_size_bytes;
  if (typeof bytes !== "number" || !Number.isFinite(bytes) || bytes <= 0) {
    return null;
  }
  return bytes / BYTES_PER_GB;
}

/**
 * The footprint a card shows: the measured `artifact_size_bytes` when the
 * backend has it (#397), else the parameter-count estimate. `measured` tells the
 * caller whether to present the number as exact or approximate. Null when
 * neither is known.
 */
export function modelFootprintGb(model) {
  const measured = measuredSizeGb(model);
  if (measured !== null) {
    return { gb: measured, measured: true };
  }
  const estimate = estimateFootprintGb(model?.param_size, model?.quantized);
  return estimate ? { gb: estimate, measured: false } : null;
}

/**
 * Classify a model against the recommended window.
 * @param {number} paramSize - billions of params
 * @param {{min:number, max:number}|null} range - recommended window from the benchmark
 * @returns {{tier:string, fraction:number, tickFraction:number, label:string} & FIT_META[tier]}
 */
export function fitForModel(paramSize, range) {
  const hasRange =
    range && typeof range.min === "number" && typeof range.max === "number" && range.max > 0;

  if (!paramSize || paramSize <= 0 || !hasRange) {
    return {
      tier: "unknown",
      fraction: 0,
      tickFraction: 0.5,
      ...FIT_META.unknown,
      label: fitLabel("unknown"),
    };
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
  return { tier, fraction, tickFraction: 0.5, ...FIT_META[tier], label: fitLabel(tier) };
}

/**
 * Classify a catalog model against the window, from the number its card shows:
 * the measured download size when the backend has it (#397), converted back to
 * the 4-bit parameter count that much weight represents — the window itself is
 * derived from usable memory with the same coefficient — else the nominal
 * parameter count. One number drives the size label, the fill and the verdict,
 * so a 3B model whose weights really take 3.1 GB is judged as the 5B-class
 * model it costs to run.
 */
export function fitForCatalogModel(model, range) {
  const measured = measuredSizeGb(model);
  const paramSize = measured === null ? model?.param_size : measured / GB_PER_BILLION_PARAMS_Q4;
  return fitForModel(paramSize, range);
}

/**
 * Whether a model is an instruction-tuned / chat model — the variant users
 * actually want, since most don't know the IT-vs-base distinction (#182). Trusts
 * the backend `conversational` flag; falls back to the name heuristic only when
 * the flag is absent (pre-#182 rows, before the next catalog resync).
 */
export const isChatReady = (model) => {
  // Trust an explicit backend boolean; fall back to the name only when unknown
  // (null/undefined on pre-#182 rows, before the next catalog resync).
  if (typeof model.conversational === "boolean") {
    return model.conversational;
  }
  return /instruct|chat/i.test(model.name || "");
};

/**
 * Order models best-fit first for the "Recommended for your machine" rail and the
 * catalog lists: conversational (chat) models first — non-chat ones still appear
 * but below — then ideal → good → tight → heavy, then larger-within-tier first.
 */
const TIER_RANK = { ideal: 0, good: 1, tight: 2, heavy: 3, unknown: 4 };
export function rankByFit(models, range) {
  return [...models]
    .map((m) => ({ m, fit: fitForCatalogModel(m, range) }))
    .sort((a, b) => {
      // Chat models lead: a newcomer's default should be something made for chat.
      const c = Number(isChatReady(b.m)) - Number(isChatReady(a.m));
      if (c !== 0) {
        return c;
      }
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
      // Only chat models — and now via the backend flag, so suffix-less chat models
      // (DeepSeek-V3, GLM-4.5, gpt-oss, Qwen3-0.6B) are no longer excluded (#182).
      isChatReady(m) &&
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
    if (best && fitForCatalogModel(best, range).tier !== "heavy") {
      picks.push(best);
      chosen.add(best.id ?? best.link);
    }
    if (picks.length >= count) {
      break;
    }
  }

  if (picks.length < count) {
    const filler = rankByFit(pool, range).filter(
      (m) => !chosen.has(m.id ?? m.link) && fitForCatalogModel(m, range).tier !== "heavy"
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
