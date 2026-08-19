// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import ModelCarousel from "./ModelCarousel";

const makeModels = (n) =>
  Array.from({ length: n }, (_, i) => ({ id: i + 1, name: `Model ${i + 1}`, param_size: 2 }));

afterEach(cleanup);

describe("ModelCarousel", () => {
  it("renders nothing for an empty section", () => {
    const { container } = render(<ModelCarousel label="Code" models={[]} />);
    expect(container.innerHTML).toBe("");
  });

  it("shows the label and a zero-padded count", () => {
    render(<ModelCarousel label="Code" models={makeModels(4)} />);
    expect(screen.getByText("Code")).toBeTruthy();
    expect(screen.getByText("04")).toBeTruthy();
    expect(screen.queryByText("See all")).toBeNull(); // 4 models cannot expand
  });

  it("expands to the full grid via 'See all' and collapses back", () => {
    render(<ModelCarousel label="Code" models={makeModels(5)} />);
    fireEvent.click(screen.getByText("See all"));
    expect(screen.getByText("Show less")).toBeTruthy();
    expect(screen.getByText("Model 5")).toBeTruthy();
    fireEvent.click(screen.getByText("Show less"));
    expect(screen.getByText("See all")).toBeTruthy();
  });

  it("propagates download clicks from the cards", () => {
    const onDownload = vi.fn();
    const models = makeModels(2);
    render(<ModelCarousel label="Code" models={models} onDownload={onDownload} />);
    fireEvent.click(screen.getAllByText("Download")[0]);
    expect(onDownload).toHaveBeenCalledWith(models[0]);
  });
});
