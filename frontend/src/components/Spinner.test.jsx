// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, afterEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import SpinnerDots from "./Spinner";

afterEach(cleanup);

describe("SpinnerDots", () => {
  it("renders eight dots inside a spinning container", () => {
    const { container } = render(<SpinnerDots />);
    const wrapper = container.firstChild;
    expect(wrapper.className).toContain("animate-spin");
    expect(wrapper.style.width).toBe("30px");
    expect(wrapper.children.length).toBe(8);
  });

  it("applies custom size, dot size and color", () => {
    const { container } = render(<SpinnerDots size={40} dotSize={8} colorClass="bg-red-500" />);
    const wrapper = container.firstChild;
    expect(wrapper.style.width).toBe("40px");
    const dot = wrapper.children[0];
    expect(dot.className).toContain("bg-red-500");
    expect(dot.style.width).toBe("8px");
  });
});
