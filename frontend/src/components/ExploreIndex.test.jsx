// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import ExploreIndex from "./ExploreIndex";

const models = [
  { id: 1, name: "A", category: "code" },
  { id: 2, name: "B", category: "code" },
  { id: 3, name: "C", category: "general" },
];

afterEach(cleanup);

describe("ExploreIndex", () => {
  it("shows a loading note while the catalog builds", () => {
    render(<ExploreIndex models={[]} loading onJump={() => {}} />);
    expect(screen.getByText("Building catalog...")).toBeTruthy();
    expect(screen.queryByText("Search Hugging Face")).toBeNull();
  });

  it("lists category rows with live counts and jumps to their section", () => {
    const onJump = vi.fn();
    render(<ExploreIndex models={models} onJump={onJump} />);
    const codeRow = screen.getByText("Code").closest("button");
    expect(codeRow.textContent).toContain("2");
    fireEvent.click(codeRow);
    expect(onJump).toHaveBeenCalledWith("cat-code");
    fireEvent.click(screen.getByText("Search Hugging Face"));
    expect(onJump).toHaveBeenCalledWith("explore-search");
  });

  it("shows the recommended row only when available", () => {
    const onJump = vi.fn();
    const { rerender } = render(<ExploreIndex models={models} onJump={onJump} />);
    expect(screen.queryByText("Recommended for you")).toBeNull();
    rerender(<ExploreIndex models={models} hasRecommended onJump={onJump} />);
    fireEvent.click(screen.getByText("Recommended for you"));
    expect(onJump).toHaveBeenCalledWith("explore-recommended");
  });

  it("shows the community row only when there are community models", () => {
    const onJump = vi.fn();
    const { rerender } = render(
      <ExploreIndex models={models} communityCount={0} onJump={onJump} />
    );
    expect(screen.queryByText("Community")).toBeNull();
    rerender(<ExploreIndex models={models} communityCount={5} onJump={onJump} />);
    fireEvent.click(screen.getByText("Community"));
    expect(onJump).toHaveBeenCalledWith("explore-community");
  });
});
