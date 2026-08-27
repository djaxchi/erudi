/**
 * Tiny translation lookup for the Electron main process (#385).
 *
 * The native menu and dialogs cannot use react-i18next, but their strings
 * must come from the same catalogs as the renderer: this reads the `main`
 * namespace of the bundled locales, falls back to English for any hole and
 * supports the same `{{name}}` interpolation. No i18next dependency so the
 * main bundle stays small and the lookup is synchronous.
 */
import en from "../locales/en/main.json";
import fr from "../locales/fr/main.json";
import es from "../locales/es/main.json";
import zh from "../locales/zh/main.json";
import { DEFAULT_LANGUAGE, normalizeLanguage } from "./languages";

const CATALOGS = { en, fr, es, zh };

function lookup(catalog, key) {
  return key
    .split(".")
    .reduce(
      (node, part) => (node === null || node === undefined ? undefined : node[part]),
      catalog
    );
}

function interpolate(template, vars) {
  return template.replace(/\{\{\s*(\w+)\s*\}\}/g, (match, name) =>
    Object.prototype.hasOwnProperty.call(vars, name) ? String(vars[name]) : match
  );
}

/**
 * Build a translator bound to a mutable language. `t(key, vars)` resolves in
 * the current language, then English, and returns the key itself as a last
 * resort so a hole is visible rather than blank.
 */
export function createMainTranslator(initialLanguage = DEFAULT_LANGUAGE) {
  let language = normalizeLanguage(initialLanguage) || DEFAULT_LANGUAGE;

  return {
    get language() {
      return language;
    },
    setLanguage(code) {
      const next = normalizeLanguage(code);
      if (next && next !== language) {
        language = next;
        return true;
      }
      return false;
    },
    t(key, vars = {}) {
      const value = lookup(CATALOGS[language], key);
      const resolved =
        typeof value === "string" && value !== "" ? value : lookup(CATALOGS[DEFAULT_LANGUAGE], key);
      if (typeof resolved !== "string" || resolved === "") return key;
      return interpolate(resolved, vars);
    },
  };
}
