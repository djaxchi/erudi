// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";

// The download modal context is a hard dependency of ModelCard (it reads
// `open` for the base-card download flow); stub it so the card renders in
// isolation.
vi.mock("../contexts/DownloadModalContext", () => ({
  useDownloadModal: () => ({ open: vi.fn() }),
}));

import ModelCard from "./ModelCard.jsx";

const localModel = {
  id: 7,
  name: "Qwen2.5-0.5B",
  size: "0.5 GB",
  parameters: "0.5B",
  lastUpdate: "2025-01-01",
  description: "A tiny local model",
  rawMetadata: "size: 0.5 GB",
};

afterEach(() => {
  cleanup();
});

describe("ModelCard installed (local) actions (#213)", () => {
  it("renders an Info action alongside Knowledge Base and Chat", () => {
    render(<ModelCard model={localModel} type="local" onInfo={vi.fn()} />);

    expect(screen.getByTitle("Info")).toBeTruthy();
    expect(screen.getByTitle("Chat")).toBeTruthy();
    expect(screen.getByTitle("Knowledge Base")).toBeTruthy();
  });

  it("calls onInfo with the model when the Info action is clicked", () => {
    const onInfo = vi.fn();
    render(<ModelCard model={localModel} type="local" onInfo={onInfo} />);

    fireEvent.click(screen.getByTitle("Info"));

    expect(onInfo).toHaveBeenCalledTimes(1);
    expect(onInfo).toHaveBeenCalledWith(localModel);
  });
});
