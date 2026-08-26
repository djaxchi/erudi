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
 * Key a model by the Hugging Face repo it came from, lowercased.
 *
 * This is what joins an installed model back to its catalog row (#348). The two
 * are distinct database rows and nothing else connects them: the local row's
 * `link` is a directory on disk, and its `link` field cannot match the catalog's
 * repo id. Both, however, carry `Model ID: <owner>/<repo>` in their metadata,
 * written from the repo the download was started against.
 *
 * Falls back to the catalog row's own `link` (a repo id for remote rows), then
 * to the display name, so a row with no parsed metadata still keys on something
 * stable rather than collapsing every such row onto one key.
 */
const isRepoId = (value) => /^[^/\\:]+\/[^/\\:]+$/.test(String(value).trim());

export function modelRepoKey(model) {
  if (!model) return null;
  const fromMetadata = model.metadata?.model_id;
  if (fromMetadata) return String(fromMetadata).trim().toLowerCase();
  // A local row's link is a filesystem path, never a repo id — only a remote
  // row's owner/name link is usable as a key.
  if (model.link && isRepoId(model.link)) return String(model.link).trim().toLowerCase();
  return model.name ? `name:${String(model.name).trim().toLowerCase()}` : null;
}

/**
 * The set of repo keys the user already has on disk, for marking catalog cards.
 * KB assistants are included deliberately: they run the weights of a base that
 * IS installed, so the base's catalog card should read as installed too.
 */
export function installedRepoKeys(localModels) {
  const keys = new Set();
  for (const model of localModels || []) {
    const key = modelRepoKey(model);
    if (key) keys.add(key);
  }
  return keys;
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
