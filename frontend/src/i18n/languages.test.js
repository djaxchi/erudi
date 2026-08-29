import { describe, it, expect } from "vitest";
import {
  SUPPORTED_LANGUAGES,
  LANGUAGE_NAMES,
  DEFAULT_LANGUAGE,
  LANGUAGE_STORAGE_KEY,
  normalizeLanguage,
  resolveInitialLanguage,
} from "./languages";

describe("languages", () => {
  it("ships exactly the four supported codes, English first", () => {
    expect(SUPPORTED_LANGUAGES).toEqual(["en", "fr", "es", "zh"]);
    expect(DEFAULT_LANGUAGE).toBe("en");
  });

  it("names every language in its own language", () => {
    expect(LANGUAGE_NAMES).toEqual({
      en: "English",
      fr: "Français",
      es: "Español",
      zh: "中文",
    });
  });

  it("normalizes BCP-47 tags to a supported code", () => {
    expect(normalizeLanguage("fr-FR")).toBe("fr");
    expect(normalizeLanguage("es-419")).toBe("es");
    expect(normalizeLanguage("zh-Hans-CN")).toBe("zh");
    expect(normalizeLanguage("EN_us")).toBe("en");
    expect(normalizeLanguage("en")).toBe("en");
  });

  it("returns null for unsupported or malformed tags", () => {
    expect(normalizeLanguage("de-DE")).toBeNull();
    expect(normalizeLanguage("")).toBeNull();
    expect(normalizeLanguage(undefined)).toBeNull();
    expect(normalizeLanguage(42)).toBeNull();
  });

  it("prefers the stored choice over the OS locale", () => {
    const storage = { getItem: (k) => (k === LANGUAGE_STORAGE_KEY ? "zh" : null) };
    expect(resolveInitialLanguage({ storage, navigatorLanguage: "fr-FR" })).toBe("zh");
  });

  it("derives from the OS locale when nothing is stored", () => {
    const storage = { getItem: () => null };
    expect(resolveInitialLanguage({ storage, navigatorLanguage: "es-MX" })).toBe("es");
  });

  it("falls back to English when neither is usable", () => {
    const storage = { getItem: () => "klingon" };
    expect(resolveInitialLanguage({ storage, navigatorLanguage: "de-DE" })).toBe("en");
    expect(resolveInitialLanguage({ storage: null, navigatorLanguage: undefined })).toBe("en");
  });

  it("survives a storage that throws (private mode, blocked site data)", () => {
    const storage = {
      getItem: () => {
        throw new Error("blocked");
      },
    };
    expect(resolveInitialLanguage({ storage, navigatorLanguage: "fr" })).toBe("fr");
  });
});
