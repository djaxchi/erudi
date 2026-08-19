// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import CatalogFilters from "./CatalogFilters";

afterEach(cleanup);

describe("CatalogFilters", () => {
  it("renders every size bucket", () => {
    render(<CatalogFilters value={{ size: "any", fitOnly: false }} onChange={() => {}} />);
    for (const label of ["Any size", "Under 2B", "2–8B", "8–32B", "32B+"]) {
      expect(screen.getByText(label)).toBeTruthy();
    }
  });

  it("selects a size bucket, preserving the rest of the filter state", () => {
    const onChange = vi.fn();
    render(<CatalogFilters value={{ size: "any", fitOnly: true }} onChange={onChange} />);
    fireEvent.click(screen.getByText("Under 2B"));
    expect(onChange).toHaveBeenCalledWith({ size: "tiny", fitOnly: true });
  });

  it("highlights the active bucket", () => {
    render(<CatalogFilters value={{ size: "small", fitOnly: false }} onChange={() => {}} />);
    expect(screen.getByText("2–8B").className).toContain("border-[var(--fit-good)]");
    expect(screen.getByText("Any size").className).toContain("border-white/10");
  });

  it("offers the fit toggle only when a hardware range exists, and flips it", () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <CatalogFilters value={{ size: "any", fitOnly: false }} onChange={onChange} />
    );
    expect(screen.queryByText("Fits my machine")).toBeNull();
    rerender(
      <CatalogFilters value={{ size: "any", fitOnly: false }} onChange={onChange} hasRange />
    );
    fireEvent.click(screen.getByText("Fits my machine"));
    expect(onChange).toHaveBeenCalledWith({ size: "any", fitOnly: true });
  });
});
