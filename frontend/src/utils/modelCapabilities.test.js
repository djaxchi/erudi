import { describe, it, expect } from "vitest";
import { canAttachImages } from "./modelCapabilities";

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
