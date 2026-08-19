// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import ExploreModelCard from "./ExploreModelCard";

const baseModel = {
  id: 1,
  name: "Qwen2.5 7B Instruct",
  category: "code",
  param_size: 7,
  quantized: true,
  downloads: "123456",
  likes: "2000000",
};

afterEach(cleanup);

describe("ExploreModelCard", () => {
  it("shows the name, category label and formatted metrics", () => {
    render(<ExploreModelCard model={baseModel} range={{ min: 2, max: 8 }} />);
    expect(screen.getByText("Qwen2.5 7B Instruct")).toBeTruthy();
    expect(screen.getByText("Code")).toBeTruthy();
    expect(screen.getByText("7B")).toBeTruthy();
    expect(screen.getByText("123k")).toBeTruthy(); // downloads
    expect(screen.getByText("2M")).toBeTruthy(); // likes
  });

  it("formats sub-billion sizes in millions and >=10B without decimals", () => {
    render(<ExploreModelCard model={{ ...baseModel, param_size: 0.27 }} />);
    expect(screen.getByText("270M")).toBeTruthy();
    render(<ExploreModelCard model={{ ...baseModel, param_size: 14 }} />);
    expect(screen.getByText("14B")).toBeTruthy();
  });

  it("says 'Size unknown' instead of implying a value", () => {
    render(<ExploreModelCard model={{ ...baseModel, param_size: undefined }} />);
    expect(screen.getByText("Size unknown")).toBeTruthy();
  });

  it("formats ten-million-plus counts without a decimal", () => {
    render(<ExploreModelCard model={{ ...baseModel, downloads: "12345678", likes: "512" }} />);
    expect(screen.getByText("12M")).toBeTruthy();
    expect(screen.getByText("512")).toBeTruthy();
  });

  it("marks gated models", () => {
    render(<ExploreModelCard model={{ ...baseModel, gated: true }} />);
    expect(screen.getByText("gated")).toBeTruthy();
  });

  it("badges team-tested models", () => {
    render(<ExploreModelCard model={{ ...baseModel, name: "Qwen3 0.6B" }} />);
    expect(screen.getByTitle(/Tested by the Erudi team/)).toBeTruthy();
  });

  it("shows the vision icon for multimodal models", () => {
    render(<ExploreModelCard model={{ ...baseModel, category: "vision" }} />);
    expect(screen.getByTitle("Supports image input (vision)")).toBeTruthy();
    expect(screen.getByText("Vision & Multimodal")).toBeTruthy();
  });

  it("fires onInfo and onDownload with the model", () => {
    const onInfo = vi.fn();
    const onDownload = vi.fn();
    render(<ExploreModelCard model={baseModel} onInfo={onInfo} onDownload={onDownload} />);
    fireEvent.click(screen.getByText("Details"));
    expect(onInfo).toHaveBeenCalledWith(baseModel);
    fireEvent.click(screen.getByText("Download"));
    expect(onDownload).toHaveBeenCalledWith(baseModel);
  });

  it("disables download for models that cannot run on this hardware", () => {
    const onDownload = vi.fn();
    render(<ExploreModelCard model={{ ...baseModel, runnable: false }} onDownload={onDownload} />);
    expect(screen.getByText("Not supported on your hardware")).toBeTruthy();
    const button = screen.getByText("Download");
    expect(button.disabled).toBe(true);
    fireEvent.click(button);
    expect(onDownload).not.toHaveBeenCalled();
  });
});
