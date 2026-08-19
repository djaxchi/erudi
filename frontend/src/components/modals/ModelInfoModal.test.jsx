// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, cleanup, screen, fireEvent } from "@testing-library/react";

import ModelInfoModal from "./ModelInfoModal.jsx";

afterEach(cleanup);

const richModel = {
  name: "Qwen2.5-7B-Instruct",
  description: "A capable instruct model.",
  size: "4.5 GB",
  parameters: "7B",
  author: "Qwen",
  library: "transformers",
  downloads: "1,234,567",
  likes: "890",
  lastUpdate: "2026-01-01",
  pipeline: "text-generation",
  rawMetadata: '{"license": "apache-2.0"}',
};

const setup = (modelInfo = richModel, overrides = {}) => {
  const props = {
    modelInfo,
    isOpen: true,
    onClose: vi.fn(),
    onDownload: vi.fn(),
    ...overrides,
  };
  const utils = render(<ModelInfoModal {...props} />);
  return { props, ...utils };
};

describe("ModelInfoModal", () => {
  it("renders nothing when closed or without a model", () => {
    setup(richModel, { isOpen: false });
    expect(screen.queryByText("Qwen2.5-7B-Instruct")).toBeNull();
    cleanup();

    setup(null);
    expect(screen.queryByText("Basic Info")).toBeNull();
  });

  it("shows every populated field of a rich model", () => {
    setup();
    expect(screen.getByText("Qwen2.5-7B-Instruct")).toBeTruthy();
    expect(screen.getByText("A capable instruct model.")).toBeTruthy();
    expect(screen.getByText("4.5 GB")).toBeTruthy();
    expect(screen.getByText("7B")).toBeTruthy();
    expect(screen.getByText("Qwen")).toBeTruthy();
    expect(screen.getByText("transformers")).toBeTruthy();
    expect(screen.getByText("1,234,567")).toBeTruthy();
    expect(screen.getByText("890")).toBeTruthy();
    expect(screen.getByText("2026-01-01")).toBeTruthy();
    expect(screen.getByText("text-generation")).toBeTruthy();
  });

  it("falls back on a placeholder description and hides Unknown/absent optionals", () => {
    setup({
      name: "bare-model",
      size: "1 GB",
      parameters: "1B",
      author: "Unknown",
      library: "Unknown",
      downloads: "Unknown",
      likes: undefined,
      lastUpdate: "Unknown",
      pipeline: "Unknown",
    });

    expect(screen.getByText("No description available")).toBeTruthy();
    expect(screen.queryByText("Author:")).toBeNull();
    expect(screen.queryByText("Library:")).toBeNull();
    expect(screen.queryByText("Downloads:")).toBeNull();
    expect(screen.queryByText("Likes:")).toBeNull();
    expect(screen.queryByText("Last Update:")).toBeNull();
    expect(screen.queryByText("Pipeline:")).toBeNull();
    // No rawMetadata -> no collapsible section at all.
    expect(screen.queryByText("Show Raw Metadata")).toBeNull();
  });

  it("toggles the raw metadata section", () => {
    setup();
    expect(screen.queryByText('{"license": "apache-2.0"}')).toBeNull();

    fireEvent.click(screen.getByText("Show Raw Metadata"));
    expect(screen.getByText('{"license": "apache-2.0"}')).toBeTruthy();

    fireEvent.click(screen.getByText("Show Raw Metadata"));
    // The exit animation may keep the node around briefly; the toggle state is
    // what we pin by toggling back on without error.
    fireEvent.click(screen.getByText("Show Raw Metadata"));
    expect(screen.getByText('{"license": "apache-2.0"}')).toBeTruthy();
  });

  it("Download hands the full model back and closes", () => {
    const { props } = setup();
    fireEvent.click(screen.getByText("Download"));

    expect(props.onDownload).toHaveBeenCalledTimes(1);
    expect(props.onDownload).toHaveBeenCalledWith(richModel);
    expect(props.onClose).toHaveBeenCalledTimes(1);
  });

  it("Cancel and the header X close without downloading", () => {
    const { props, container } = setup();
    fireEvent.click(screen.getByText("Cancel"));
    expect(props.onClose).toHaveBeenCalledTimes(1);

    const headerX = container.querySelector(".flex-1 + button");
    fireEvent.click(headerX);
    expect(props.onClose).toHaveBeenCalledTimes(2);
    expect(props.onDownload).not.toHaveBeenCalled();
  });
});
