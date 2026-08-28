/**
 * Hole-proof guard for the translation catalogs (#385).
 *
 * `en` is the source of truth. For every namespace and every other language
 * this fails when:
 *   - a key present in `en` is missing (the UI would silently fall back);
 *   - a key exists that `en` does not have (dead or misspelled key);
 *   - a value is an empty string or not a string (a leaf must be copy);
 *   - a `{{placeholder}}` used in `en` is absent from the translation.
 * It also pins the namespace list and the language list so a new file cannot
 * be forgotten in resources.js.
 */
import { describe, it, expect } from "vitest";
import { NAMESPACES, resources } from "../i18n/resources";
import { SUPPORTED_LANGUAGES } from "../i18n/languages";

const SOURCE = "en";

function flatten(obj, prefix = "", out = {}) {
  for (const [key, value] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (value !== null && typeof value === "object" && !Array.isArray(value)) {
      flatten(value, path, out);
    } else {
      out[path] = value;
    }
  }
  return out;
}

function placeholders(value) {
  return new Set(Array.from(String(value).matchAll(/\{\{\s*(\w+)\s*\}\}/g), (m) => m[1]));
}

describe("translation catalogs", () => {
  it("bundle every supported language", () => {
    expect(Object.keys(resources).sort()).toEqual([...SUPPORTED_LANGUAGES].sort());
  });

  it("bundle every namespace for every language", () => {
    for (const lang of SUPPORTED_LANGUAGES) {
      expect(Object.keys(resources[lang]).sort(), lang).toEqual([...NAMESPACES].sort());
    }
  });

  for (const ns of NAMESPACES) {
    describe(`namespace "${ns}"`, () => {
      const source = flatten(resources[SOURCE][ns]);

      it("has only non-empty string leaves in en", () => {
        const bad = Object.entries(source)
          .filter(([, v]) => typeof v !== "string" || v.trim() === "")
          .map(([k]) => k);
        expect(bad).toEqual([]);
      });

      for (const lang of SUPPORTED_LANGUAGES.filter((l) => l !== SOURCE)) {
        describe(lang, () => {
          const target = flatten(resources[lang][ns]);

          it("has every key en has", () => {
            const missing = Object.keys(source).filter((k) => !(k in target));
            expect(missing).toEqual([]);
          });

          it("has no key en does not have", () => {
            const extra = Object.keys(target).filter((k) => !(k in source));
            expect(extra).toEqual([]);
          });

          it("has only non-empty string leaves", () => {
            const bad = Object.entries(target)
              .filter(([, v]) => typeof v !== "string" || v.trim() === "")
              .map(([k]) => k);
            expect(bad).toEqual([]);
          });

          it("keeps every {{placeholder}} of the English source", () => {
            const broken = Object.entries(source)
              .filter(([k, v]) => {
                if (!(k in target)) return false;
                const expected = placeholders(v);
                const actual = placeholders(target[k]);
                return [...expected].some((p) => !actual.has(p));
              })
              .map(([k]) => k);
            expect(broken).toEqual([]);
          });
        });
      }
    });
  }
});
