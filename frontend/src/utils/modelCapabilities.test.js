import { describe, it, expect } from "vitest";
import { canAttachImages, maxImagesForModel, modelSupportsVision } from "./modelCapabilities";

describe("canAttachImages", () => {
  it("blocks attaching only when the model explicitly cannot see images", () => {
    expect(canAttachImages({ supports_vision: false })).toBe(false);
  });

  it("allows attaching for a vision model", () => {
    expect(canAttachImages({ supports_vision: true })).toBe(true);
  });

  it("is permissive when the capability is unknown", () => {
    // null/undefined/missing model -> never wrongly block a real VLM (#133).
    expect(canAttachImages({ supports_vision: null })).toBe(true);
    expect(canAttachImages({})).toBe(true);
    expect(canAttachImages(undefined)).toBe(true);
    expect(canAttachImages(null)).toBe(true);
  });
});

describe("maxImagesForModel", () => {
  it("falls back to the default cap when the param size is unknown or invalid", () => {
    expect(maxImagesForModel(undefined)).toBe(4);
    expect(maxImagesForModel({})).toBe(4);
    expect(maxImagesForModel({ param_size: null })).toBe(4);
    expect(maxImagesForModel({ param_size: "7B" })).toBe(4);
    expect(maxImagesForModel({ param_size: 0 })).toBe(4);
    expect(maxImagesForModel({ param_size: -1 })).toBe(4);
  });

  it("caps small models (<3B) at 2 images", () => {
    expect(maxImagesForModel({ param_size: 0.5 })).toBe(2);
    expect(maxImagesForModel({ param_size: 2.9 })).toBe(2);
  });

  it("caps mid-size models (3-8B) at 4 images", () => {
    expect(maxImagesForModel({ param_size: 3 })).toBe(4);
    expect(maxImagesForModel({ param_size: 7.9 })).toBe(4);
  });

  it("caps large models (>=8B) at 6 images", () => {
    expect(maxImagesForModel({ param_size: 8 })).toBe(6);
    expect(maxImagesForModel({ param_size: 70 })).toBe(6);
  });
});

describe("modelSupportsVision", () => {
  it("is a positive signal: false for a missing model", () => {
    expect(modelSupportsVision(null)).toBe(false);
    expect(modelSupportsVision(undefined)).toBe(false);
  });

  it("affirms vision when the engine detected the installed model as a VLM", () => {
    expect(modelSupportsVision({ supports_vision: true })).toBe(true);
  });

  it("affirms vision pre-download from the catalog vision category", () => {
    expect(modelSupportsVision({ supports_vision: null, category: "vision" })).toBe(true);
  });

  it("stays false when the capability is unknown and the category is not vision", () => {
    expect(modelSupportsVision({ supports_vision: null, category: "chat" })).toBe(false);
    expect(modelSupportsVision({})).toBe(false);
    expect(modelSupportsVision({ supports_vision: false, category: "chat" })).toBe(false);
  });
});
