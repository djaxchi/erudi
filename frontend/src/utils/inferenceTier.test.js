import { describe, it, expect, afterEach } from "vitest";
import i18n from "../i18n";
import { inferenceTierKey, inferenceTierLabel } from "./inferenceTier";

// The backend's global_inference_label is an English tier name (Excellent /
// Good / Fair / Poor / Weak). Every surface that shows it maps it to the same
// translated tier name (#387); an unknown label is shown as received.

afterEach(async () => {
  await i18n.changeLanguage("en");
});

describe("inferenceTierKey", () => {
  it("maps the backend tiers case-insensitively", () => {
    expect(inferenceTierKey("Fair")).toBe("fair");
    expect(inferenceTierKey("EXCELLENT")).toBe("excellent");
    expect(inferenceTierKey("weak")).toBe("weak");
  });

  it("returns null for an unknown or absent label", () => {
    expect(inferenceTierKey("Amazing")).toBeNull();
    expect(inferenceTierKey("")).toBeNull();
    expect(inferenceTierKey(null)).toBeNull();
    expect(inferenceTierKey(undefined)).toBeNull();
  });
});

describe("inferenceTierLabel", () => {
  it("translates a known tier in the active language", async () => {
    expect(inferenceTierLabel("Fair")).toBe("Fair");
    await i18n.changeLanguage("fr");
    expect(inferenceTierLabel("Fair")).toBe("Correct");
    expect(inferenceTierLabel("Good")).toBe("Bon");
  });

  it("passes an unknown label through unchanged", async () => {
    await i18n.changeLanguage("fr");
    expect(inferenceTierLabel("Amazing")).toBe("Amazing");
  });

  it("returns null for an absent label", () => {
    expect(inferenceTierLabel(null)).toBeNull();
    expect(inferenceTierLabel("")).toBeNull();
  });
});
