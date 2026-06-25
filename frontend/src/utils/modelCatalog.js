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
