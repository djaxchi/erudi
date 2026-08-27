/**
 * The interface languages Erudi ships translations for (#385).
 *
 * This module is dependency-free on purpose: it is shared by the renderer
 * (i18next bootstrap, Settings page) and the Electron main process (native
 * menu + dialogs), and the backend mirrors the list in
 * `src/entities/UserSettings.py`.
 */

export const SUPPORTED_LANGUAGES = ["en", "fr", "es", "zh"];

export const DEFAULT_LANGUAGE = "en";

/** Language names shown in their own language, never translated. */
export const LANGUAGE_NAMES = {
  en: "English",
  fr: "Français",
  es: "Español",
  zh: "中文",
};

/** localStorage key mirroring the persisted choice for the boot screen. */
export const LANGUAGE_STORAGE_KEY = "erudi.language";

/**
 * Map any BCP-47 tag ("fr-FR", "zh-Hans-CN", "EN_us") to a supported code.
 * Returns null when the primary subtag is not one we ship.
 */
export function normalizeLanguage(tag) {
  if (typeof tag !== "string" || !tag) return null;
  const primary = tag.trim().toLowerCase().split(/[-_]/)[0];
  return SUPPORTED_LANGUAGES.includes(primary) ? primary : null;
}

/**
 * Pick the language to boot in: the stored mirror first (a previously
 * persisted choice), then the OS locale, then English.
 */
export function resolveInitialLanguage({ storage, navigatorLanguage } = {}) {
  let stored = null;
  try {
    stored = storage?.getItem?.(LANGUAGE_STORAGE_KEY) ?? null;
  } catch {
    stored = null;
  }
  return normalizeLanguage(stored) || normalizeLanguage(navigatorLanguage) || DEFAULT_LANGUAGE;
}
