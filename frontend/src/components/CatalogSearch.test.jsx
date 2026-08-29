// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import CatalogSearch from "./CatalogSearch";

afterEach(cleanup);

const input = () => screen.getByRole("searchbox", { name: "Search the catalog" });

describe("CatalogSearch (#380)", () => {
  it("renders a labelled search box with the catalog placeholder and no clear button when empty", () => {
    render(<CatalogSearch value="" onChange={() => {}} />);
    expect(input().getAttribute("placeholder")).toMatch(/Filter the catalog/);
    expect(screen.queryByRole("button", { name: "Clear" })).toBeNull();
  });

  it("forwards every keystroke to onChange", () => {
    const onChange = vi.fn();
    render(<CatalogSearch value="" onChange={onChange} />);
    fireEvent.change(input(), { target: { value: "qwen" } });
    expect(onChange).toHaveBeenCalledWith("qwen");
  });

  it("Escape clears the query and keeps the focus in the box", () => {
    const onChange = vi.fn();
    render(<CatalogSearch value="qwen" onChange={onChange} />);
    input().focus();
    fireEvent.keyDown(input(), { key: "Escape" });
    expect(onChange).toHaveBeenCalledWith("");
    expect(document.activeElement).toBe(input());
  });

  it("the clear button empties the query and returns the focus to the box", () => {
    const onChange = vi.fn();
    render(<CatalogSearch value="qwen" onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(onChange).toHaveBeenCalledWith("");
    expect(document.activeElement).toBe(input());
  });
});
