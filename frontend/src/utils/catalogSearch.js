/**
 * Client-side search over the bundled model catalog (#380).
 *
 * The catalog ships with the app (snapshot), so searching it must work fully
 * offline — this is a pure, synchronous filter the Models page runs as the user
 * types, distinct from the Hugging Face search that needs the network. Matching
 * is case- and accent-insensitive, every word of the query must match (AND), and
 * hits are ranked so the model someone is actually typing the name of comes
 * first: name prefix, then name contains, then a match through the repo id,
 * family, category or tags.
 */
import i18n from "../i18n";
import { CATEGORY_META } from "./modelCatalog";

/**
 * Lowercase, strip diacritics, and turn the separators people type
 * interchangeably (`-`, `_`) into spaces, so "qwen2.5-7b" finds "Qwen2.5 7B".
 */
export function normalizeSearchText(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[-_]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

const tokenize = (query) => normalizeSearchText(query).split(" ").filter(Boolean);

// Everything a row can be found by besides its name. The category is matched
// on its key ("vision") and on its label in the active language
// ("Vision & Multimodal"), because the label is what the page shows.
function secondaryText(model) {
  const parts = [model.link, model.type, model.author, model.metadata?.model_id, model.category];
  const meta = model.category ? CATEGORY_META[model.category] : null;
  if (meta) parts.push(i18n.t(meta.labelKey));
  const tags = model.tags;
  if (Array.isArray(tags)) parts.push(...tags);
  else if (tags) parts.push(tags);
  return normalizeSearchText(parts.filter((p) => p !== null && p !== undefined).join(" "));
}

const RANK_NAME_PREFIX = 0;
const RANK_NAME_CONTAINS = 1;
const RANK_OTHER = 2;

/**
 * Filter and rank `models` for `query`. An empty query returns the input array
 * itself (same reference) so callers can tell "no search" from "no match". Rows
 * that are not objects, or whose fields are null, never throw — they simply do
 * not match.
 */
export function searchCatalog(models, query) {
  const tokens = tokenize(query);
  if (tokens.length === 0) return models;
  const phrase = tokens.join(" ");

  const hits = [];
  (models || []).forEach((model, index) => {
    if (!model || typeof model !== "object") return;
    const name = normalizeSearchText(model.name);
    const other = secondaryText(model);
    const haystack = `${name} ${other}`;
    if (!tokens.every((token) => haystack.includes(token))) return;

    let rank = RANK_OTHER;
    if (name.startsWith(phrase)) rank = RANK_NAME_PREFIX;
    else if (tokens.every((token) => name.includes(token))) rank = RANK_NAME_CONTAINS;
    hits.push({ model, rank, index });
  });

  return hits.sort((a, b) => a.rank - b.rank || a.index - b.index).map((h) => h.model);
}
