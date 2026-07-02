import { describe, it, expect } from "vitest";
import { getDisplayContent } from "./messageContent";

// #136 — stored message content can carry internal attachment markers
// ([image], [image_path:<path>]) that must never leak into what the user
// reads or copies. getDisplayContent is the single source of truth for the
// readable text, shared by the chat display and the copy button.

describe("getDisplayContent", () => {
  it("strips [image_path:…] and [image] markers and keeps the readable text", () => {
    expect(getDisplayContent("[image_path:/a/b.png][image]Describe the picture")).toBe(
      "Describe the picture"
    );
  });

  it("trims whitespace left behind by removed markers", () => {
    expect(getDisplayContent("What is this? [image_path:/tmp/photo 1.jpg]")).toBe("What is this?");
  });

  it("returns content without markers unchanged", () => {
    expect(getDisplayContent("Plain question about Paris")).toBe("Plain question about Paris");
  });

  it("keeps the error-message formatting used by the chat display", () => {
    expect(getDisplayContent("[ERROR_MESSAGE_SYSTEM] Something broke")).toBe("❌ Something broke");
  });
});
