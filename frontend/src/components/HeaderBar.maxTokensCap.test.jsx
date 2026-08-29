// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import HeaderBar from "./HeaderBar";

// HeaderBar observes its own width with ResizeObserver, which jsdom lacks.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = globalThis.ResizeObserver || ResizeObserverStub;

// The max-tokens field's ceiling follows the model (#388, the #136 cap item):
// `maxTokensCap` = min(model context window, engine window) resolved by the
// backend. Without the prop the ceiling is the API's own upper bound.

const openSettings = () => fireEvent.click(screen.getByLabelText("Toggle settings"));

afterEach(() => {
  cleanup();
});

describe("HeaderBar maxTokensCap", () => {
  it("wires the prop to the number input's max", async () => {
    render(<HeaderBar maxTokensCap={4096} />);
    openSettings();
    const maxTokens = await screen.findByRole("spinbutton");
    expect(maxTokens.getAttribute("max")).toBe("4096");
  });

  it("defaults to the API's upper bound (32768) without the prop", async () => {
    render(<HeaderBar />);
    openSettings();
    const maxTokens = await screen.findByRole("spinbutton");
    expect(maxTokens.getAttribute("max")).toBe("32768");
  });
});
