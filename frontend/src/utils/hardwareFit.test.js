import { describe, it, expect } from "vitest";
import {
  fitForModel,
  estimateFootprintGb,
  rankByFit,
  pickFlagships,
  applyCatalogFilters,
} from "./hardwareFit";

const range = { min: 4, max: 8 };

describe("fitForModel", () => {
  it("classifies within the window as ideal", () => {
    expect(fitForModel(7, range).tier).toBe("ideal");
    expect(fitForModel(4, range).tier).toBe("ideal");
    expect(fitForModel(8, range).tier).toBe("ideal");
  });

  it("classifies below the window as good (headroom)", () => {
    expect(fitForModel(1.5, range).tier).toBe("good");
  });

  it("keeps a model marginally over the ceiling ideal (soft sweet-spot)", () => {
    expect(fitForModel(8.03, range).tier).toBe("ideal"); // within the 12% grace band
  });

  it("classifies clearly over as tight, far over as heavy", () => {
    expect(fitForModel(13, range).tier).toBe("tight"); // > 8.96, <= 15.2
    expect(fitForModel(30, range).tier).toBe("heavy");
  });

  it("places the tick at the ceiling and scales the fill 0..2x", () => {
    const f = fitForModel(8, range);
    expect(f.tickFraction).toBe(0.5);
    expect(f.fraction).toBeCloseTo(0.5, 5); // 8 / (8*2)
  });

  it("returns unknown without a param size or a range", () => {
    expect(fitForModel(undefined, range).tier).toBe("unknown");
    expect(fitForModel(7, null).tier).toBe("unknown");
  });
});

describe("estimateFootprintGb", () => {
  it("estimates ~0.6 GB/B for quantized, ~2 GB/B otherwise", () => {
    expect(estimateFootprintGb(7, true)).toBeCloseTo(4.2, 5);
    expect(estimateFootprintGb(7, false)).toBeCloseTo(14, 5);
    expect(estimateFootprintGb(0)).toBeNull();
  });
});

describe("rankByFit", () => {
  it("orders ideal first, then larger-within-tier", () => {
    const models = [
      { name: "huge", param_size: 70 },
      { name: "ideal-small", param_size: 4 },
      { name: "ideal-big", param_size: 8 },
      { name: "tight", param_size: 12 },
    ];
    expect(rankByFit(models, range).map((m) => m.name)).toEqual([
      "ideal-big",
      "ideal-small",
      "tight",
      "huge",
    ]);
  });
});

describe("pickFlagships", () => {
  const M = (name, type, param_size, category = "general") => ({
    name,
    type,
    param_size,
    category,
    link: name,
    runnable: true,
  });

  it("picks one instruct model per flagship family, in family order, that fits", () => {
    const models = [
      M("Llama 3.1 8B Instruct", "llama", 8),
      M("Llama 3.2 3B Instruct", "llama", 3),
      M("Qwen2.5 7B Instruct", "qwen", 7.6),
      M("Gemma 2 2B Instruct", "gemma", 2.6),
      M("Mistral 7B Instruct v0.2", "mistral", 7.2),
    ];
    const picks = pickFlagships(models, { min: 4, max: 8 }, 3);
    expect(picks.map((m) => m.type)).toEqual(["llama", "qwen", "gemma"]);
    // largest fitting Llama instruct chosen
    expect(picks[0].name).toBe("Llama 3.1 8B Instruct");
  });

  it("excludes base (non-instruct) models", () => {
    const models = [
      M("Meta Llama 3 8B", "llama", 8), // base — no Instruct/Chat in name
      M("Qwen2.5 7B Instruct", "qwen", 7.6),
    ];
    const picks = pickFlagships(models, { min: 4, max: 8 }, 3);
    expect(picks.every((m) => /instruct|chat/i.test(m.name))).toBe(true);
    expect(picks.find((m) => m.name === "Meta Llama 3 8B")).toBeUndefined();
  });

  it("never recommends a model that needs more memory", () => {
    const models = [M("Llama 3.3 70B Instruct", "llama", 70)];
    expect(pickFlagships(models, { min: 4, max: 8 }, 3)).toHaveLength(0);
  });

  it("never recommends a model whose size is unmeasured (#201)", () => {
    const models = [
      M("Mystery Instruct", "llama", null),
      M("Mystery Instruct 2", "qwen", undefined),
    ];
    expect(pickFlagships(models, { min: 4, max: 8 }, 3)).toHaveLength(0);
  });
});

describe("applyCatalogFilters", () => {
  const models = [
    { name: "tiny", param_size: 1 },
    { name: "mid", param_size: 7 },
    { name: "big", param_size: 14 },
    { name: "huge", param_size: 70 },
  ];

  it("filters by size bucket", () => {
    expect(applyCatalogFilters(models, { size: "small" }, null).map((m) => m.name)).toEqual([
      "mid",
    ]);
    expect(applyCatalogFilters(models, { size: "large" }, null).map((m) => m.name)).toEqual([
      "huge",
    ]);
  });

  it("'fits my machine' drops models that need more memory", () => {
    const kept = applyCatalogFilters(models, { size: "any", fitOnly: true }, { min: 4, max: 8 });
    expect(kept.map((m) => m.name)).not.toContain("huge"); // 70B is heavy
    expect(kept.map((m) => m.name)).toContain("mid");
  });
});
