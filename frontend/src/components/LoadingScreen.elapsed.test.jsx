// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, act } from "@testing-library/react";
import LoadingScreen from "./LoadingScreen";

// The elapsed-seconds counter appears after the first tick so a slow boot is
// visibly progressing, not frozen.

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("LoadingScreen elapsed counter", () => {
  it("shows elapsed seconds once at least one second has passed", async () => {
    vi.useFakeTimers();
    render(<LoadingScreen phase="loading_catalog" />);

    expect(screen.getByText(/Loading the model catalog/)).toBeTruthy();
    expect(screen.queryByText(/\(\d+s\)/)).toBeNull();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });

    expect(screen.getByText("(3s)")).toBeTruthy();
  });
});
