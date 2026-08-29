/**
 * i18next bootstrap for the renderer (#385).
 *
 * Importing this module initializes i18next synchronously (inline resources,
 * no backend, no remote loading) in the language resolved from the local
 * mirror or the OS locale, so the boot screen and every component rendered
 * afterwards already speak the right language. English is the fallback for
 * any key a language lacks — and `locales.test.js` makes such holes a test
 * failure rather than a silent English leak.
 *
 * `setAppLanguage` is the single entry point for changing the language at
 * runtime: it switches i18next, mirrors the code in localStorage for the
 * next boot, tags the document and tells the main process (native menu and
 * dialogs) over IPC.
 */
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { DEFAULT_NAMESPACE, NAMESPACES, resources } from "./resources";
import {
  DEFAULT_LANGUAGE,
  LANGUAGE_STORAGE_KEY,
  SUPPORTED_LANGUAGES,
  normalizeLanguage,
  resolveInitialLanguage,
} from "./languages";

function localStorageOrNull() {
  try {
    return typeof window !== "undefined" ? window.localStorage : null;
  } catch {
    return null;
  }
}

function navigatorLanguageOrNull() {
  return typeof navigator !== "undefined" ? navigator.language : null;
}

export function detectInitialLanguage() {
  return resolveInitialLanguage({
    storage: localStorageOrNull(),
    navigatorLanguage: navigatorLanguageOrNull(),
  });
}

function mirrorLanguage(code, { persist }) {
  if (persist) {
    try {
      localStorageOrNull()?.setItem(LANGUAGE_STORAGE_KEY, code);
    } catch {
      // Storage may be unavailable (private mode, blocked site data): the
      // choice still applies for this session and is persisted server-side.
    }
  }
  if (typeof document !== "undefined" && document.documentElement) {
    document.documentElement.lang = code;
  }
  if (typeof window !== "undefined") {
    window.languageAPI?.set?.(code);
  }
}

/** True when a previous run already mirrored a choice on this machine. */
export function hasStoredLanguage() {
  try {
    return normalizeLanguage(localStorageOrNull()?.getItem(LANGUAGE_STORAGE_KEY)) !== null;
  } catch {
    return false;
  }
}

/**
 * Switch the interface language everywhere (renderer, document, main
 * process) and remember it for the next boot. Unknown codes are ignored and
 * the current language is returned unchanged.
 */
export async function setAppLanguage(code) {
  const next = normalizeLanguage(code);
  if (!next) return i18n.language;
  if (next !== i18n.language) {
    await i18n.changeLanguage(next);
  }
  mirrorLanguage(next, { persist: true });
  return next;
}

if (!i18n.isInitialized) {
  i18n.use(initReactI18next).init({
    resources,
    lng: detectInitialLanguage(),
    fallbackLng: DEFAULT_LANGUAGE,
    supportedLngs: SUPPORTED_LANGUAGES,
    ns: NAMESPACES,
    defaultNS: DEFAULT_NAMESPACE,
    // Empty strings are holes, not translations: fall through to English.
    returnEmptyString: false,
    returnNull: false,
    interpolation: { escapeValue: false },
    react: { useSuspense: false },
  });
  // Boot: tag the document and tell main which language we resolved, but do
  // NOT write the mirror yet — an absent mirror is how the app knows this is
  // the first launch on this machine (see App.jsx's backend sync).
  mirrorLanguage(i18n.language, { persist: false });
}

export default i18n;
