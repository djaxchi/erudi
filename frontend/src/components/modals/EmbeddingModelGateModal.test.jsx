// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, afterEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import EmbeddingModelGateModal from "./EmbeddingModelGateModal";
import { GATE } from "../../utils/embeddingGate";

afterEach(cleanup);

// The gate must cover only the KB content area (its positioned parent), never
// the whole window: the sidebar stays usable while a download runs, so the
// user can go do something else and come back (#146 follow-up).
describe("EmbeddingModelGateModal overlay scoping", () => {
  it.each([GATE.PROMPT, GATE.DOWNLOADING, GATE.DONE, GATE.ERROR])(
    "scopes the overlay to its container (absolute, not fixed) in state %s",
    (state) => {
      const { container } = render(
        <EmbeddingModelGateModal
          state={state}
          error={null}
          onDownload={() => {}}
          onLeave={() => {}}
          onClose={() => {}}
        />
      );
      const overlay = container.firstChild;
      expect(overlay.className).toContain("absolute");
      expect(overlay.className).not.toContain("fixed");
    }
  );
});
