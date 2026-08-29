import { describe, it, expect, beforeEach, afterEach } from "vitest";
import i18n from "../i18n";
import { displayModelSize, parseSizeGb } from "./modelSize";

// The size line on installed cards and in the details modal comes from the
// backend's metadata string ("Size: ~0.7 GB"), which is English regardless of
// the app language (#387). It is now rendered through the locale formatter:
// the measured `artifact_size_bytes` first, then the parsed metadata string,
// then the footprint estimate from the parameter count.

beforeEach(async () => {
  await i18n.changeLanguage("fr");
});
afterEach(async () => {
  await i18n.changeLanguage("en");
});

describe("parseSizeGb", () => {
  it("reads a precise and an approximate size", () => {
    expect(parseSizeGb("4.5 GB")).toEqual({ minGb: 4.5, maxGb: 4.5, approximate: false });
    expect(parseSizeGb("~0.7 GB")).toEqual({ minGb: 0.7, maxGb: 0.7, approximate: true });
    expect(parseSizeGb("  ~13.5GB ")).toEqual({ minGb: 13.5, maxGb: 13.5, approximate: true });
  });

  it("reads a range estimate", () => {
    expect(parseSizeGb("~3.0-4.0 GB")).toEqual({ minGb: 3, maxGb: 4, approximate: true });
  });

  it("returns null for anything else", () => {
    expect(parseSizeGb("Unknown")).toBeNull();
    expect(parseSizeGb("Inconnu")).toBeNull();
    expect(parseSizeGb("")).toBeNull();
    expect(parseSizeGb(undefined)).toBeNull();
    expect(parseSizeGb(42)).toBeNull();
    expect(parseSizeGb("700 MB")).toBeNull();
  });
});

describe("displayModelSize", () => {
  it("prefers the measured artifact size, in the catalog's decimal GB", () => {
    // 4 700 000 000 bytes = 4.7 GB (decimal, like the backend's measurement).
    expect(displayModelSize({ artifact_size_bytes: 4_700_000_000, size: "~4.0 GB" })).toBe(
      "4,7 Go"
    );
  });

  it("ignores a non-positive or absent artifact size", () => {
    expect(displayModelSize({ artifact_size_bytes: 0, size: "~0.7 GB" })).toBe("~0,7 Go");
    expect(displayModelSize({ artifact_size_bytes: null, size: "~0.7 GB" })).toBe("~0,7 Go");
    expect(displayModelSize({ artifact_size_bytes: "big", size: "~0.7 GB" })).toBe("~0,7 Go");
  });

  it("re-formats the metadata string, keeping the approximation marker", () => {
    expect(displayModelSize({ size: "4.5 GB" })).toBe("4,5 Go");
    expect(displayModelSize({ size: "~0.7 GB" })).toBe("~0,7 Go");
    expect(displayModelSize({ size: "~3.0-4.0 GB" })).toBe("~3-4 Go");
  });

  it("falls back to the footprint estimate from the parameter count", () => {
    // 7B, 4-bit: ~0.6 GB per billion params.
    expect(displayModelSize({ size: "Unknown", param_size: 7 })).toBe("~4,2 Go");
    expect(displayModelSize({ param_size: 1, quantized: false })).toBe("~2 Go");
  });

  it("returns null when nothing is known", () => {
    expect(displayModelSize({ size: "Unknown" })).toBeNull();
    expect(displayModelSize({})).toBeNull();
    expect(displayModelSize(null)).toBeNull();
  });

  it("follows the active language", async () => {
    await i18n.changeLanguage("en");
    expect(displayModelSize({ size: "~0.7 GB" })).toBe("~0.7 GB");
    expect(displayModelSize({ artifact_size_bytes: 4_700_000_000 })).toBe("4.7 GB");
  });
});
