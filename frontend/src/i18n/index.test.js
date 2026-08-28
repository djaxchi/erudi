// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import i18n, { setAppLanguage, hasStoredLanguage } from "./index";
import { LANGUAGE_STORAGE_KEY } from "./languages";

// Node 22+ ships an experimental `localStorage` global that shadows jsdom's
// (and lacks `clear` without --localstorage-file), so the tests install a
// plain in-memory Storage on window.
function memoryStorage() {
  const store = new Map();
  return {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
    clear: () => store.clear(),
  };
}

describe("i18n bootstrap", () => {
  beforeEach(async () => {
    Object.defineProperty(window, "localStorage", {
      value: memoryStorage(),
      configurable: true,
      writable: true,
    });
    delete window.languageAPI;
    await i18n.changeLanguage("en");
  });

  afterEach(() => {
    delete window.languageAPI;
  });

  it("is initialized synchronously with English as fallback", () => {
    expect(i18n.isInitialized).toBe(true);
    expect(i18n.options.fallbackLng).toEqual(["en"]);
    expect(i18n.t("common:actions.cancel")).toBe("Cancel");
  });

  it("does not treat the boot-resolved language as a stored choice", () => {
    expect(hasStoredLanguage()).toBe(false);
  });

  it("setAppLanguage switches, mirrors, tags the document and notifies main", async () => {
    const set = vi.fn();
    window.languageAPI = { set };

    const applied = await setAppLanguage("fr-FR");

    expect(applied).toBe("fr");
    expect(i18n.language).toBe("fr");
    expect(i18n.t("common:actions.cancel")).toBe("Annuler");
    expect(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe("fr");
    expect(document.documentElement.lang).toBe("fr");
    expect(set).toHaveBeenCalledWith("fr");
    expect(hasStoredLanguage()).toBe(true);
  });

  it("ignores unknown codes and keeps the current language", async () => {
    const applied = await setAppLanguage("de");
    expect(applied).toBe("en");
    expect(i18n.language).toBe("en");
    expect(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBeNull();
  });

  it("falls back to English for a key a language lacks", async () => {
    await setAppLanguage("zh");
    // A key that only exists in the English catalog is served in English
    // rather than echoing the key back (the locales test flags the hole).
    i18n.addResource("en", "common", "__probe", "probe");
    expect(i18n.t("common:__probe")).toBe("probe");
  });
});
