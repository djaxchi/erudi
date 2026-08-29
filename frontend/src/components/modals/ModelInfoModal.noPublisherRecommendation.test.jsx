// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, cleanup, screen } from "@testing-library/react";

import ModelInfoModal from "./ModelInfoModal.jsx";

// The details view says when the model's publisher gives no sampling
// recommendation (#388, `sampling_defaults.source === "none"`); it shows
// nothing when one exists or when the block is absent (a Hugging Face search
// result has no resolved defaults yet).

afterEach(cleanup);

const NOTE =
  "This model's publisher gives no sampling recommendation; Erudi applies neutral defaults.";

const base = {
  name: "Llama 3.2 1B Instruct",
  description: "Meta's small instruct model.",
  size: "0.8 GB",
  parameters: "1B",
  author: "meta-llama",
};

const setup = (modelInfo) =>
  render(<ModelInfoModal modelInfo={modelInfo} isOpen onClose={vi.fn()} onDownload={vi.fn()} />);

describe("ModelInfoModal publisher recommendation note", () => {
  it("shows the note when the resolved source is none", () => {
    setup({ ...base, sampling_defaults: { source: "none", temperature: 0.2 } });
    const note = screen.getByTestId("no-publisher-recommendation");
    expect(note.textContent).toBe(NOTE);
  });

  it("shows nothing when a recommendation exists", () => {
    setup({ ...base, sampling_defaults: { source: "model_card", temperature: 0.15 } });
    expect(screen.queryByTestId("no-publisher-recommendation")).toBeNull();
    expect(screen.queryByText(NOTE)).toBeNull();
  });

  it("shows nothing without a resolved block (Hugging Face search result)", () => {
    setup(base);
    expect(screen.queryByTestId("no-publisher-recommendation")).toBeNull();
  });
});
