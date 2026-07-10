import { describe, it, expect } from "vitest";
import { isKbAssistant, hasMissingWeights, findBaseModelName } from "./modelWeights";

// Orphan-model helpers (#225/#208) gate delete/rebind UI. Their contract has two
// deliberately asymmetric rules that a regression would quietly break:
//  - "unknown" weight state (undefined/null) must NEVER mark a model as missing,
//    so remote rows and older backends are not wrongly blocked;
//  - an assistant's base is found by matching `link` against OTHER local rows
//    that are not themselves assistants.

describe("isKbAssistant", () => {
  it("is true when explicitly flagged", () => {
    expect(isKbAssistant({ is_attached_to_kb: true })).toBe(true);
  });

  it("is true when a kb_id is present (including 0)", () => {
    expect(isKbAssistant({ kb_id: 42 })).toBe(true);
    expect(isKbAssistant({ kb_id: 0 })).toBe(true); // 0 is a valid id, not "absent"
  });

  it("is false for a plain installed model", () => {
    expect(isKbAssistant({ id: 1, link: "org/model" })).toBe(false);
    expect(isKbAssistant({ kb_id: null })).toBe(false);
    expect(isKbAssistant({ kb_id: undefined })).toBe(false);
    expect(isKbAssistant({ is_attached_to_kb: false })).toBe(false);
  });

  it("is false for a nullish model", () => {
    expect(isKbAssistant(null)).toBe(false);
    expect(isKbAssistant(undefined)).toBe(false);
  });
});

describe("hasMissingWeights", () => {
  it("is true ONLY on an explicit weights_available === false", () => {
    expect(hasMissingWeights({ weights_available: false })).toBe(true);
  });

  it("treats unknown weight state as present (never blocks)", () => {
    expect(hasMissingWeights({ weights_available: undefined })).toBe(false);
    expect(hasMissingWeights({ weights_available: null })).toBe(false);
    expect(hasMissingWeights({})).toBe(false);
    expect(hasMissingWeights({ weights_available: true })).toBe(false);
  });

  it("does not treat a falsy-but-not-false value as missing", () => {
    // Guard against a `!model.weights_available` regression: 0/"" are not `false`.
    expect(hasMissingWeights({ weights_available: 0 })).toBe(false);
    expect(hasMissingWeights({ weights_available: "" })).toBe(false);
  });

  it("is false for a nullish model", () => {
    expect(hasMissingWeights(null)).toBe(false);
    expect(hasMissingWeights(undefined)).toBe(false);
  });
});

describe("findBaseModelName", () => {
  const assistant = { id: 5, link: "org/base-model", kb_id: 9 };

  it("returns the name of the non-assistant local row sharing the link", () => {
    const locals = [
      { id: 1, name: "Base Model", link: "org/base-model" },
      { id: 5, name: "My Assistant", link: "org/base-model", kb_id: 9 },
    ];
    expect(findBaseModelName(assistant, locals)).toBe("Base Model");
  });

  it("returns null when the base has been deleted (orphan)", () => {
    const locals = [{ id: 5, name: "My Assistant", link: "org/base-model", kb_id: 9 }];
    expect(findBaseModelName(assistant, locals)).toBeNull();
  });

  it("does not match the assistant against itself", () => {
    // Only the assistant row is present; matching self would wrongly report a base.
    const locals = [assistant];
    expect(findBaseModelName(assistant, locals)).toBeNull();
  });

  it("does not treat another assistant with the same link as the base", () => {
    const locals = [
      { id: 5, name: "My Assistant", link: "org/base-model", kb_id: 9 },
      { id: 6, name: "Other Assistant", link: "org/base-model", kb_id: 10 },
    ];
    expect(findBaseModelName(assistant, locals)).toBeNull();
  });

  it("returns null for invalid inputs", () => {
    expect(findBaseModelName(null, [{ id: 1, link: "x" }])).toBeNull();
    expect(findBaseModelName(assistant, null)).toBeNull();
    expect(findBaseModelName(assistant, undefined)).toBeNull();
  });
});
