// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";

import TraceStrip, { formatToolArgs, buildRows } from "./TraceStrip.jsx";

afterEach(() => {
  cleanup();
});

// ── Pure formatting rules (design SS4: NEVER raw JSON) ──────────────────────
describe("formatToolArgs", () => {
  it("renders a single-key object as just the value", () => {
    expect(formatToolArgs({ expression: "1240 + 1378 + 1456" })).toBe("1240 + 1378 + 1456");
  });

  it("renders a {raw} payload as the raw string, unparsed", () => {
    expect(formatToolArgs({ raw: '{"expr": "2+' })).toBe('{"expr": "2+');
  });

  it("renders multiple keys as k=v pairs", () => {
    expect(formatToolArgs({ a: 1, b: "two" })).toBe("a=1, b=two");
  });

  it("renders an empty object as an empty string", () => {
    expect(formatToolArgs({})).toBe("");
  });

  it("is defensive about non-objects", () => {
    expect(formatToolArgs(null)).toBe("");
    expect(formatToolArgs(undefined)).toBe("");
    expect(formatToolArgs([1, 2])).toBe("");
  });
});

describe("buildRows", () => {
  it("merges consecutive thinking events into one block", () => {
    const { rows, steps } = buildRows([
      { t: "thinking", text: "Let me " },
      { t: "thinking", text: "think." },
    ]);
    expect(rows).toEqual([{ kind: "thinking", text: "Let me think." }]);
    expect(steps).toBe(1);
  });

  it("counts steps as thinking blocks + tool calls (not tool results)", () => {
    const { steps } = buildRows([
      { t: "thinking", text: "hmm" },
      { t: "tool_call", name: "calc", args: { x: "2+2" } },
      { t: "tool_result", name: "calc", text: "4" },
    ]);
    expect(steps).toBe(2);
  });

  it("lifts a truncated marker into a flag and ignores unknown events", () => {
    const { truncated, rows } = buildRows([
      { t: "truncated" },
      { t: "thinking", text: "a" },
      { t: "mystery", text: "ignored" },
    ]);
    expect(truncated).toBe(true);
    expect(rows).toEqual([{ kind: "thinking", text: "a" }]);
  });
});

// ── Rendering ───────────────────────────────────────────────────────────────
const TRACE = [
  { t: "thinking", text: "I should add the numbers." },
  { t: "tool_call", name: "calculator", args: { expression: "2 + 2" } },
  { t: "tool_result", name: "calculator", text: "4" },
];

describe("TraceStrip rendering", () => {
  it("renders nothing when there are no trace rows", () => {
    const { container } = render(<TraceStrip events={[]} live={false} />);
    expect(container.firstChild).toBeNull();
  });

  it("is collapsed by default for persisted replay (live=false)", () => {
    render(<TraceStrip events={TRACE} live={false} />);
    // Summary counts thinking block (1) + tool call (1) = 2 steps.
    expect(screen.getByRole("button").textContent).toMatch(/Reasoning.*2 steps/);
    // Rows are hidden until expanded.
    expect(screen.queryByText(/I should add the numbers\./)).toBeNull();
  });

  it("expands on click and NEVER shows raw JSON for tool calls", () => {
    const { container } = render(<TraceStrip events={TRACE} live={false} />);
    fireEvent.click(screen.getByRole("button"));

    expect(screen.getByText(/I should add the numbers\./)).toBeTruthy();
    // Tool call is formatted name(pretty args), result is "-> text".
    expect(container.textContent).toContain("calculator(2 + 2)");
    expect(container.textContent).toContain("4");
    // No braces and no arg-key names leaked into the DOM.
    expect(container.textContent).not.toContain("{");
    expect(container.textContent).not.toContain("}");
    expect(container.textContent).not.toContain("expression");
  });

  it("renders a {raw} tool_call payload as the raw string", () => {
    render(
      <TraceStrip
        events={[{ t: "tool_call", name: "search", args: { raw: "partial frag" } }]}
        live={false}
      />
    );
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText(/search\(partial frag\)/)).toBeTruthy();
  });

  it("shows the (earlier steps elided) note when truncated", () => {
    render(<TraceStrip events={[{ t: "truncated" }, ...TRACE]} live={false} />);
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText(/earlier steps elided/)).toBeTruthy();
  });

  it("is expanded by default for a live turn (live=true)", () => {
    render(<TraceStrip events={TRACE} live={true} />);
    expect(screen.getByText(/I should add the numbers\./)).toBeTruthy();
  });

  it("auto-collapses on the live -> not-live transition (first answer event)", () => {
    const { rerender } = render(<TraceStrip events={TRACE} live={true} />);
    expect(screen.getByText(/I should add the numbers\./)).toBeTruthy();

    // Parent flips live to false on the first answer event.
    rerender(<TraceStrip events={TRACE} live={false} />);
    expect(screen.queryByText(/I should add the numbers\./)).toBeNull();
  });

  it("stays togglable after collapse (re-expand is not overridden)", () => {
    const { rerender } = render(<TraceStrip events={TRACE} live={true} />);
    rerender(<TraceStrip events={TRACE} live={false} />);
    // User re-expands after the auto-collapse.
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText(/I should add the numbers\./)).toBeTruthy();
  });
});
