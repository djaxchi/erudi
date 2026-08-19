// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";

// #310 — per-conversation Web Search toggle in the settings panel. Hidden by
// default so the Arena (which shares HeaderBar but has no conversation row)
// stays untouched; ConversationPage opts in with showWebSearch.

import HeaderBar from "./HeaderBar.jsx";

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = globalThis.ResizeObserver || ResizeObserverStub;

const renderBar = (props = {}) =>
  render(<HeaderBar onApply={() => {}} onCustomizePrompt={() => {}} {...props} />);

const openSettings = () => fireEvent.click(screen.getByLabelText("Toggle settings"));

afterEach(() => {
  cleanup();
});

describe("HeaderBar web search toggle (#310)", () => {
  it("is hidden by default (Arena keeps the panel unchanged)", async () => {
    renderBar();
    openSettings();
    await screen.findAllByRole("slider");
    expect(screen.queryByRole("switch", { name: "Web search" })).toBeNull();
  });

  it("renders when showWebSearch is set, reflecting initialWebSearch", async () => {
    renderBar({ showWebSearch: true, initialWebSearch: true });
    openSettings();
    const toggle = await screen.findByRole("switch", { name: "Web search" });
    expect(toggle.getAttribute("aria-checked")).toBe("true");
  });

  it("defaults to off", async () => {
    renderBar({ showWebSearch: true });
    openSettings();
    const toggle = await screen.findByRole("switch", { name: "Web search" });
    expect(toggle.getAttribute("aria-checked")).toBe("false");
  });

  it("reports the flipped value through onWebSearchChange", async () => {
    const onWebSearchChange = vi.fn();
    renderBar({ showWebSearch: true, initialWebSearch: false, onWebSearchChange });
    openSettings();
    const toggle = await screen.findByRole("switch", { name: "Web search" });
    fireEvent.click(toggle);
    expect(onWebSearchChange).toHaveBeenCalledWith(true);
    expect(toggle.getAttribute("aria-checked")).toBe("true");
  });

  it("syncs with a later initialWebSearch prop change (hydration)", async () => {
    const { rerender } = renderBar({ showWebSearch: true, initialWebSearch: false });
    openSettings();
    const toggle = await screen.findByRole("switch", { name: "Web search" });
    expect(toggle.getAttribute("aria-checked")).toBe("false");
    rerender(
      <HeaderBar onApply={() => {}} onCustomizePrompt={() => {}} showWebSearch initialWebSearch />
    );
    expect(toggle.getAttribute("aria-checked")).toBe("true");
  });
});
