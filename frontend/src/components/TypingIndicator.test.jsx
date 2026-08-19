// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, afterEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import TypingIndicator from "./TypingIndicator";

afterEach(cleanup);

describe("TypingIndicator", () => {
  it("renders three staggered bouncing dots", () => {
    const { container } = render(<TypingIndicator />);
    const dots = container.querySelectorAll("span");
    expect(dots.length).toBe(3);
    expect(dots[0].style.animationDelay).toBe("0s");
    expect(dots[1].style.animationDelay).toBe("0.15s");
    expect(dots[2].style.animationDelay).toBe("0.3s");
  });

  it("applies size and color customization", () => {
    const { container } = render(
      <TypingIndicator size={10} colorClass="bg-emerald-400" className="mt-2" />
    );
    const dot = container.querySelector("span");
    expect(dot.style.width).toBe("10px");
    expect(dot.className).toContain("bg-emerald-400");
    expect(container.firstChild.className).toContain("mt-2");
  });
});
