import { describe, it, expect } from "vitest";
import { applyCatalogFilters, pickFlagships } from "./hardwareFit";

// Complements hardwareFit.test.js: the size-bucket filters of the catalog and
// the flagship filler path (fewer family picks than requested -> the rail is
// topped up from the ranked, still-runnable pool).

const range = { min: 1, max: 8 };

const model = (name, paramSize, extra = {}) => ({
  id: name,
  name,
  param_size: paramSize,
  conversational: true,
  runnable: true,
  category: "general",
  ...extra,
});

describe("applyCatalogFilters size buckets", () => {
  const catalog = [model("Tiny", 0.5), model("Small", 4), model("Medium", 14), model("Large", 70)];

  it("keeps only sub-2B models for the tiny bucket", () => {
    expect(applyCatalogFilters(catalog, { size: "tiny" }, range).map((m) => m.name)).toEqual([
      "Tiny",
    ]);
  });

  it("keeps only 8-32B models for the medium bucket", () => {
    expect(applyCatalogFilters(catalog, { size: "medium" }, range).map((m) => m.name)).toEqual([
      "Medium",
    ]);
  });

  it("falls back to the any bucket for an unknown size key", () => {
    expect(applyCatalogFilters(catalog, { size: "nope" }, range)).toHaveLength(4);
  });
});

describe("pickFlagships filler", () => {
  it("tops up the rail from the ranked pool when flagship families run short", () => {
    // Only one known family (qwen) -> the third slot must be filled by the
    // non-family model that still fits, never by the too-heavy one.
    const models = [
      model("Qwen3 4B", 4, { type: "qwen" }),
      model("HouseModel 2B", 2, { type: "acme" }),
      model("HouseModel 70B", 70, { type: "acme" }),
    ];

    const picks = pickFlagships(models, range, 2);

    expect(picks.map((m) => m.name)).toEqual(["Qwen3 4B", "HouseModel 2B"]);
    expect(picks.map((m) => m.name)).not.toContain("HouseModel 70B");
  });
});
