import { describe, it, expect } from "vitest";
import { splitByBase, recommendModels } from "./modelCatalog";

const m = (name, is_base, param_size) => ({ name, is_base, param_size });

describe("splitByBase", () => {
  it("splits remote models on the backend is_base flag", () => {
    const { base, community } = splitByBase([m("A", true, 7), m("B", false, 3), m("C", true, 12)]);
    expect(base.map((x) => x.name)).toEqual(["A", "C"]);
    expect(community.map((x) => x.name)).toEqual(["B"]);
  });

  it("treats missing/falsey is_base as community (never crashes)", () => {
    const { base, community } = splitByBase([m("A"), m("B", undefined, 1)]);
    expect(base).toEqual([]);
    expect(community).toHaveLength(2);
  });
});

describe("recommendModels", () => {
  const base = [
    m("S", true, 1),
    m("M", true, 4),
    m("L", true, 8),
    m("XL", true, 12),
    m("XXL", true, 70),
  ];

  it("returns in-window base models, largest first", () => {
    expect(recommendModels(base, { min: 4, max: 8 }, 3).map((x) => x.name)).toEqual(["L", "M"]);
  });

  it("caps the result at the limit", () => {
    expect(recommendModels(base, { min: 1, max: 70 }, 2).map((x) => x.name)).toEqual(["XXL", "XL"]);
  });

  it("falls back to the smallest base models when nothing fits the window", () => {
    expect(recommendModels(base, { min: 100, max: 200 }, 2).map((x) => x.name)).toEqual(["S", "M"]);
  });

  it("falls back to the first N base models when the range is missing", () => {
    expect(recommendModels(base, null, 2).map((x) => x.name)).toEqual(["S", "M"]);
  });
});
