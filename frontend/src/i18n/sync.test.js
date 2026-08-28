// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import i18n, { setAppLanguage } from "./index";
import { LANGUAGE_STORAGE_KEY } from "./languages";
import { syncLanguageWithBackend } from "./sync";

function memoryStorage(initial = {}) {
  const store = new Map(Object.entries(initial));
  return {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
    clear: () => store.clear(),
  };
}

function installStorage(initial) {
  Object.defineProperty(window, "localStorage", {
    value: memoryStorage(initial),
    configurable: true,
    writable: true,
  });
}

describe("syncLanguageWithBackend", () => {
  beforeEach(async () => {
    installStorage();
    await i18n.changeLanguage("en");
  });

  afterEach(async () => {
    await i18n.changeLanguage("en");
  });

  it("first launch: pushes the OS-derived language to the backend and mirrors it", async () => {
    await i18n.changeLanguage("fr"); // what the boot resolved from navigator.language
    const client = {
      get: vi.fn().mockResolvedValue({ web_search_enabled: false, language: "en" }),
      put: vi.fn().mockResolvedValue({ web_search_enabled: false, language: "fr" }),
    };

    const result = await syncLanguageWithBackend(client);

    expect(client.get).toHaveBeenCalledWith("/user_settings/");
    expect(client.put).toHaveBeenCalledWith("/user_settings/", { language: "fr" });
    expect(result).toBe("fr");
    expect(i18n.language).toBe("fr");
    expect(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe("fr");
  });

  it("first launch: does not PUT when the backend already matches", async () => {
    const client = {
      get: vi.fn().mockResolvedValue({ web_search_enabled: false, language: "en" }),
      put: vi.fn(),
    };

    await syncLanguageWithBackend(client);

    expect(client.put).not.toHaveBeenCalled();
    expect(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe("en");
  });

  it("later launches: the persisted backend value wins over the local mirror", async () => {
    installStorage({ [LANGUAGE_STORAGE_KEY]: "fr" });
    await setAppLanguage("fr");
    const client = {
      get: vi.fn().mockResolvedValue({ web_search_enabled: true, language: "zh" }),
      put: vi.fn(),
    };

    const result = await syncLanguageWithBackend(client);

    expect(result).toBe("zh");
    expect(i18n.language).toBe("zh");
    expect(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe("zh");
    expect(client.put).not.toHaveBeenCalled();
  });

  it("keeps the current language when the backend call fails", async () => {
    await i18n.changeLanguage("es");
    const client = { get: vi.fn().mockRejectedValue(new Error("boom")), put: vi.fn() };

    const result = await syncLanguageWithBackend(client);

    expect(result).toBe("es");
    expect(i18n.language).toBe("es");
  });

  it("ignores an unknown code coming from the backend", async () => {
    installStorage({ [LANGUAGE_STORAGE_KEY]: "en" });
    const client = { get: vi.fn().mockResolvedValue({ language: "klingon" }), put: vi.fn() };

    const result = await syncLanguageWithBackend(client);

    expect(result).toBe("en");
    expect(i18n.language).toBe("en");
  });
});
