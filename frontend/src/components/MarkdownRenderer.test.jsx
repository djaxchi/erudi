// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, afterEach } from "vitest";
import { render, cleanup } from "@testing-library/react";

import MarkdownRenderer from "./MarkdownRenderer.jsx";

// Local models (Qwen3 in particular) routinely emit inline TeX between single
// dollars — "$ 3 - 1 = 2 $", "$ \frac{14}{2} = 7 $" — so single-dollar math
// must render (#303). Single-dollar parsing is a known currency footgun:
// remark-math's default happily turns "I have $5 and $10" into math("5 and ").
// The DELIBERATE configuration here: single-dollar math stays enabled, but a
// span whose opening "$" is immediately followed by a digit is treated as
// currency and kept as literal text. Trade-off (documented): math that starts
// with a bare digit right after the dollar ("$3x+1$") stays literal — models
// pad their math ("$ 3x+1 $") or open with a symbol, both of which render.

const renderMarkdown = (content) => render(<MarkdownRenderer content={content} />);

afterEach(() => {
  cleanup();
});

describe("MarkdownRenderer math support (#303)", () => {
  it("renders single-dollar inline math as a katex element", () => {
    const { container } = renderMarkdown("The square is $x^2$ here.");

    expect(container.querySelector(".katex")).toBeTruthy();
    // The raw TeX source must no longer be visible.
    expect(container.textContent).not.toContain("$x^2$");
  });

  it("renders Qwen-style space-padded math", () => {
    const { container } = renderMarkdown("So $ \\frac{14}{2} = 7 $ apples.");

    expect(container.querySelector(".katex")).toBeTruthy();
    // The dollar-delimited raw source is gone (KaTeX keeps the TeX source in a
    // visually-hidden MathML annotation, so match the delimiters, not the TeX).
    expect(container.textContent).not.toContain("$ \\frac{14}{2} = 7 $");
  });

  it("renders double-dollar display math", () => {
    const { container } = renderMarkdown("$$\nE = mc^2\n$$");

    expect(container.querySelector(".katex")).toBeTruthy();
  });

  it("does not mangle dollar amounts", () => {
    const { container } = renderMarkdown("I have $5 and $10 in my pocket.");

    expect(container.querySelector(".katex")).toBeNull();
    expect(container.textContent).toContain("$5 and $10");
  });

  it("does not mangle thousand-separated prices or ranges", () => {
    const { container } = renderMarkdown("It costs $20,000 and $30,000, or $5-$10 per unit.");

    expect(container.querySelector(".katex")).toBeNull();
    expect(container.textContent).toContain("$20,000 and $30,000");
    expect(container.textContent).toContain("$5-$10");
  });

  it("keeps plain markdown rendering intact", () => {
    const { container } = renderMarkdown("Some **bold** text and `inline code`.");

    expect(container.querySelector("strong").textContent).toBe("bold");
    expect(container.querySelector("code").textContent).toBe("inline code");
  });
});
