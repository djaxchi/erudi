import { describe, it, expect } from "vitest";
import { conversationPath } from "./routes";

describe("conversationPath", () => {
  it("builds the plural /erudi/conversations/:id path", () => {
    expect(conversationPath(42)).toBe("/erudi/conversations/42");
    expect(conversationPath("abc")).toBe("/erudi/conversations/abc");
  });
});
