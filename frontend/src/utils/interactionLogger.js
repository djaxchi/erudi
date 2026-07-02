/**
 * Pure helpers for the UI interaction tracer (see components/InteractionLogger.jsx).
 *
 * Naming convention for emitted events: "ui.<dom-event-type>" — ui.click,
 * ui.focusout, ui.change, ui.drop, ui.paste, ui.keydown. Each entry is built by
 * buildInteractionEntry() and persisted through the renderer log bridge.
 */

// Elements considered "actionable": what the user meant to interact with.
const ACTIONABLE_SELECTOR = [
  "button",
  "a",
  '[role="button"]',
  "input",
  "select",
  "textarea",
  "[aria-label]",
  "[title]",
].join(", ");

// How many parentElement hops describeTarget may climb looking for the nearest
// actionable ancestor before giving up and describing the original element.
const MAX_HOPS = 6;
const LABEL_MAX_CHARS = 60;

/** Truncate a value for logging, appending an "… [+N]" overflow marker. */
export function truncateValue(v, limit = 200) {
  const s = typeof v === "string" ? v : String(v ?? "");
  if (s.length <= limit) return s;
  return `${s.slice(0, limit)}… [+${s.length - limit}]`;
}

function isElement(node) {
  return !!node && node.nodeType === 1 && typeof node.getAttribute === "function";
}

function elementKind(el, tag) {
  const role = el.getAttribute("role");
  if (role) return role;
  if (tag === "a") return "link";
  if (tag === "input") return `input:${(el.getAttribute("type") || "text").toLowerCase()}`;
  if (tag === "button" || tag === "select" || tag === "textarea") return tag;
  return "element";
}

/**
 * Describe the nearest actionable element at or above `el`.
 * Label precedence: aria-label > title > trimmed textContent (≤60 chars) >
 * `tag#id`. Never throws — falls back to an "unknown" descriptor instead.
 * @param {Element|EventTarget|null} el - The raw event target.
 * @returns {{label: string, tag: string, kind: string}}
 */
export function describeTarget(el) {
  try {
    let node = isElement(el) ? el : null;
    let actionable = null;
    for (let hops = 0; node && hops <= MAX_HOPS; hops += 1) {
      if (typeof node.matches === "function" && node.matches(ACTIONABLE_SELECTOR)) {
        actionable = node;
        break;
      }
      node = node.parentElement;
    }
    const target = actionable || (isElement(el) ? el : null);
    if (!target) {
      return { label: "unknown", tag: "unknown", kind: "unknown" };
    }
    const tag = (target.tagName || "unknown").toLowerCase();
    const ariaLabel = (target.getAttribute("aria-label") || "").trim();
    const title = (target.getAttribute("title") || "").trim();
    const text = (target.textContent || "").replace(/\s+/g, " ").trim();
    const label =
      ariaLabel ||
      title ||
      text.slice(0, LABEL_MAX_CHARS) ||
      `${tag}${target.id ? `#${target.id}` : ""}`;
    return { label, tag, kind: elementKind(target, tag) };
  } catch {
    return { label: "unknown", tag: "unknown", kind: "unknown" };
  }
}

/**
 * Build one structured interaction entry ready for the log bridge.
 * @param {string} type - DOM event type ("click", "focusout", …).
 * @param {Element|EventTarget|null} el - The raw event target.
 * @param {string} route - Current hash route (pathname).
 * @param {Object} [extra] - Event-specific fields (value, key, files, …).
 */
export function buildInteractionEntry(type, el, route, extra = {}) {
  return {
    ts: new Date().toISOString(),
    type,
    route,
    target: describeTarget(el),
    ...extra,
  };
}
