// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import MarkdownRenderer from "./MarkdownRenderer";

// Custom element renderers: links open safely in a new tab, GFM tables get a
// horizontal-scroll wrapper, and lists keep their bullet/number styling.

afterEach(() => {
  cleanup();
});

describe("MarkdownRenderer custom elements", () => {
  it("renders links with target=_blank and rel=noreferrer", () => {
    render(<MarkdownRenderer content="See [the docs](https://example.com/docs)." />);

    const link = screen.getByRole("link", { name: "the docs" });
    expect(link.getAttribute("href")).toBe("https://example.com/docs");
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toBe("noreferrer");
  });

  it("renders GFM tables with header and data cells inside a scroll wrapper", () => {
    const table = ["| Model | Size |", "| --- | --- |", "| Gemma | 270M |"].join("\n");
    const { container } = render(<MarkdownRenderer content={table} />);

    const header = screen.getByRole("columnheader", { name: "Model" });
    expect(header.tagName).toBe("TH");
    const cell = screen.getByRole("cell", { name: "Gemma" });
    expect(cell.tagName).toBe("TD");
    // The table is wrapped for horizontal overflow.
    expect(container.querySelector(".overflow-x-auto table")).toBeTruthy();
  });

  it("renders unordered and ordered lists with their list styling", () => {
    const { container } = render(
      <MarkdownRenderer content={"- alpha\n- beta\n\n1. first\n2. second"} />
    );

    expect(container.querySelector("ul.list-disc")).toBeTruthy();
    expect(container.querySelector("ol.list-decimal")).toBeTruthy();
    expect(screen.getByText("alpha")).toBeTruthy();
    expect(screen.getByText("second")).toBeTruthy();
  });
});
