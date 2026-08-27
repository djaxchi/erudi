// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

// Very small models (#381): a 0.6B card must say on its face that tool use,
// knowledge-base search and multi-step reasoning are unreliable, so the user
// learns it before attaching a KB or enabling web search on it.

vi.mock("../contexts/DownloadModalContext", () => ({
  useDownloadModal: () => ({ open: vi.fn() }),
}));

import ModelCard from "./ModelCard.jsx";

const localModel = (parameters) => ({
  id: 7,
  name: "Qwen3 0.6B",
  size: "0.5 GB",
  parameters,
  lastUpdate: "2025-01-01",
  rawMetadata: "size: 0.5 GB",
});

const noteId = "small-model-note";

afterEach(cleanup);

describe("ModelCard very small model note (#381)", () => {
  it.each(["0.6B", "1.7B", "270M"])("shows the note for an installed %s model", (parameters) => {
    render(<ModelCard model={localModel(parameters)} type="local" />);
    const note = screen.getByTestId(noteId);
    expect(note.textContent).toMatch(/Very small model/);
    expect(note.textContent).toMatch(/tool use, knowledge-base search and multi-step reasoning/);
    expect(note.textContent).toMatch(/below ~4B/);
  });

  it("uses the numeric param_size when the metadata string is missing", () => {
    render(<ModelCard model={{ ...localModel(undefined), param_size: 0.5 }} type="local" />);
    expect(screen.getByTestId(noteId)).toBeTruthy();
  });

  it.each(["4B", "7B"])("does not show the note for a %s model", (parameters) => {
    render(<ModelCard model={localModel(parameters)} type="local" />);
    expect(screen.queryByTestId(noteId)).toBeNull();
  });

  it("does not show the note when the size is unknown", () => {
    render(<ModelCard model={localModel(undefined)} type="local" />);
    expect(screen.queryByTestId(noteId)).toBeNull();
    cleanup();
    render(<ModelCard model={localModel("Unknown")} type="local" />);
    expect(screen.queryByTestId(noteId)).toBeNull();
  });

  it("also flags a very small model on the base (catalog) variant", () => {
    render(<ModelCard model={localModel("0.6B")} type="base" />);
    expect(screen.getByTestId(noteId)).toBeTruthy();
  });

  it("never renders the note on the add tile", () => {
    render(<ModelCard model={{ name: "unused", parameters: "0.6B" }} type="add" />);
    expect(screen.queryByTestId(noteId)).toBeNull();
  });
});
