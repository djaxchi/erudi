// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import GradientBox from "./GradientBox";

afterEach(cleanup);

describe("GradientBox", () => {
  it("renders its children and forwards clicks", () => {
    const onClick = vi.fn();
    render(<GradientBox onClick={onClick}>Hello</GradientBox>);
    fireEvent.click(screen.getByText("Hello"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("uses the default content wrapper unless one is provided", () => {
    const { rerender } = render(<GradientBox>Body</GradientBox>);
    expect(screen.getByText("Body").className).toContain("p-8");
    rerender(<GradientBox contentClassName="custom-wrap">Body</GradientBox>);
    const wrapper = screen.getByText("Body");
    expect(wrapper.className).toContain("custom-wrap");
    expect(wrapper.className).not.toContain("p-8");
  });

  it("merges extra classes and spreads extra props onto the root", () => {
    const { container } = render(
      <GradientBox className="h-full" data-testid="box">
        X
      </GradientBox>
    );
    const root = container.firstChild;
    expect(root.className).toContain("h-full");
    expect(root.getAttribute("data-testid")).toBe("box");
  });
});
