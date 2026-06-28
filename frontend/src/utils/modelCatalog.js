/**
 * Pure helpers for the model catalog UI (#86).
 *
 * Framework-free so they can be unit-tested in isolation; LandingPage wires them
 * to the fetched remote catalog and the hardware evaluation. These replace a
 * hand-maintained `baseModelNames` list and a name-regex param parser that broke
 * the moment the catalog became auto-discovered.
 */

/**
 * Split the remote catalog into curated base (foundation) vs derived/community
 * models, using the backend `is_base` flag. Anything without a truthy flag is
 * treated as community, so a missing field never empties the page.
 */
export function splitByBase(models) {
  const base = [];
  const community = [];
  for (const model of models) {
    (model.is_base ? base : community).push(model);
  }
  return { base, community };
}

/**
 * Capability categories (#122), mirrored from the backend catalog_classify keys.
 * `order` drives section order; `collapsed` marks sections hidden by default
 * (Safety = moderation classifiers, not chat models).
 */
export const CATEGORY_META = {
  general: { label: "General", order: 0 },
  reasoning: { label: "Reasoning", order: 1 },
  code: { label: "Code", order: 2 },
  vision: { label: "Vision & Multimodal", order: 3 },
  math: { label: "Math", order: 4 },
  medical: { label: "Medical", order: 5 },
  function: { label: "Function Calling", order: 6 },
  safety: { label: "Safety & Moderation", order: 7, collapsed: true },
};

const _catMeta = (cat) => CATEGORY_META[cat] || CATEGORY_META.general;

/**
 * Group models by capability category into an ordered array of
 * { category, label, collapsed, models }. Unknown/missing categories fall back
 * to "general", so a stray value never drops a model. Empty categories are
 * omitted (callers render only what exists).
 */
export function groupByCategory(models) {
  const groups = {};
  for (const model of models) {
    const cat = CATEGORY_META[model.category] ? model.category : "general";
    (groups[cat] = groups[cat] || []).push(model);
  }
  return Object.keys(groups)
    .sort((a, b) => _catMeta(a).order - _catMeta(b).order)
    .map((cat) => ({
      category: cat,
      label: _catMeta(cat).label,
      collapsed: Boolean(_catMeta(cat).collapsed),
      models: groups[cat],
    }));
}

/**
 * Recommend base models that fit the hardware's param-size window
 * ({ min, max } billions of params, from /hardware/app_startup). Largest that
 * fits first; falls back to the smallest base models when none fit, or the first
 * N when no range is available.
 */
export function recommendModels(baseModels, range, limit = 3) {
  if (!range || typeof range.min !== "number" || typeof range.max !== "number") {
    return baseModels.slice(0, limit);
  }

  const fits = baseModels
    .filter(
      (model) =>
        typeof model.param_size === "number" &&
        model.param_size >= range.min &&
        model.param_size <= range.max
    )
    .sort((a, b) => b.param_size - a.param_size);

  if (fits.length > 0) {
    return fits.slice(0, limit);
  }

  // Nothing in-window (e.g. very weak hardware): the smallest base models are the
  // least likely to overwhelm it.
  return [...baseModels]
    .sort((a, b) => (a.param_size ?? Infinity) - (b.param_size ?? Infinity))
    .slice(0, limit);
}
