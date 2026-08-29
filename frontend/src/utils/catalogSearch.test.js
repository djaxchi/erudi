import { describe, it, expect } from "vitest";
import { searchCatalog, normalizeSearchText } from "./catalogSearch";

const row = (name, extra = {}) => ({ name, ...extra });

const catalog = [
  row("Llama 3.1 8B Instruct", { link: "mlx-community/Llama-3.1-8B-Instruct-4bit", type: "llama" }),
  row("Qwén 2.5 7B Instruct", { link: "mlx-community/Qwen2.5-7B-Instruct-4bit", type: "qwen" }),
  row("DeepSeek R1 Distill Qwen 1.5B", {
    link: "mlx-community/DeepSeek-R1-Distill-Qwen-1.5B-4bit",
    type: "deepseek",
    category: "reasoning",
  }),
  row("Qwen3 8B", { link: "mlx-community/Qwen3-8B-4bit", type: "qwen", category: "general" }),
  row("Gemma 3 4B", {
    link: "mlx-community/gemma-3-4b-it-4bit",
    type: "gemma",
    category: "vision",
  }),
  row("Phi 4 mini", { link: "mlx-community/Phi-4-mini-instruct-4bit", tags: ["tiny", "math"] }),
];

const names = (rows) => rows.map((r) => r.name);

describe("normalizeSearchText", () => {
  it("lowercases, strips accents and collapses separators", () => {
    expect(normalizeSearchText("  Qwén_2.5-7B  Instruct ")).toBe("qwen 2.5 7b instruct");
  });

  it("never throws on non-strings", () => {
    expect(normalizeSearchText(null)).toBe("");
    expect(normalizeSearchText(undefined)).toBe("");
    expect(normalizeSearchText(42)).toBe("42");
  });
});

describe("searchCatalog", () => {
  it("returns the catalog untouched for an empty or whitespace query", () => {
    expect(searchCatalog(catalog, "")).toBe(catalog);
    expect(searchCatalog(catalog, "   ")).toBe(catalog);
    expect(searchCatalog(catalog, null)).toBe(catalog);
  });

  it("matches case- and accent-insensitively in both directions", () => {
    // "qwen" finds "Qwén"; "QWÉN" finds the plain "Qwen3".
    expect(names(searchCatalog(catalog, "qwen"))).toContain("Qwén 2.5 7B Instruct");
    expect(names(searchCatalog(catalog, "QWÉN"))).toContain("Qwen3 8B");
  });

  it("ranks name prefix matches first, then name contains, then other fields", () => {
    expect(names(searchCatalog(catalog, "qwen"))).toEqual([
      // prefix on the name
      "Qwén 2.5 7B Instruct",
      "Qwen3 8B",
      // name contains, not a prefix
      "DeepSeek R1 Distill Qwen 1.5B",
    ]);
  });

  it("keeps the catalog order inside a rank (stable)", () => {
    expect(names(searchCatalog(catalog, "instruct"))).toEqual([
      "Llama 3.1 8B Instruct",
      "Qwén 2.5 7B Instruct",
      // Phi only carries "instruct" in its repo link -> last
      "Phi 4 mini",
    ]);
  });

  it("ANDs every word of a multi-word query", () => {
    expect(names(searchCatalog(catalog, "qwen 8b"))).toEqual(["Qwen3 8B"]);
    expect(names(searchCatalog(catalog, "qwen nothingness"))).toEqual([]);
  });

  it("matches the Hugging Face repo id, with or without the owner", () => {
    expect(names(searchCatalog(catalog, "mlx-community/gemma-3-4b"))).toEqual(["Gemma 3 4B"]);
    expect(names(searchCatalog(catalog, "gemma-3-4b-it"))).toEqual(["Gemma 3 4B"]);
  });

  it("matches the family/type, the category key and the category label", () => {
    expect(names(searchCatalog(catalog, "deepseek"))).toEqual(["DeepSeek R1 Distill Qwen 1.5B"]);
    expect(names(searchCatalog(catalog, "reasoning"))).toEqual(["DeepSeek R1 Distill Qwen 1.5B"]);
    // English label of the "vision" category is "Vision & Multimodal".
    expect(names(searchCatalog(catalog, "multimodal"))).toEqual(["Gemma 3 4B"]);
  });

  it("matches tags when a row carries them", () => {
    expect(names(searchCatalog(catalog, "tiny"))).toEqual(["Phi 4 mini"]);
  });

  it("does not crash on rows with null or missing fields", () => {
    const sparse = [
      { name: null, link: null, type: null, category: null, tags: null },
      { name: "Only Name" },
      {},
      null,
    ];
    expect(() => searchCatalog(sparse, "name")).not.toThrow();
    expect(names(searchCatalog(sparse, "name"))).toEqual(["Only Name"]);
  });
});
