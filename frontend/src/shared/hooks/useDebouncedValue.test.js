// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import useDebouncedValue from "./useDebouncedValue";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("useDebouncedValue", () => {
  it("starts with the initial value and only follows changes after the delay", () => {
    const { result, rerender } = renderHook(({ v }) => useDebouncedValue(v, 150), {
      initialProps: { v: "q" },
    });
    expect(result.current).toBe("q");

    rerender({ v: "qw" });
    expect(result.current).toBe("q");
    act(() => vi.advanceTimersByTime(149));
    expect(result.current).toBe("q");
    act(() => vi.advanceTimersByTime(1));
    expect(result.current).toBe("qw");
  });

  it("restarts the timer on every change so only the last value lands", () => {
    const { result, rerender } = renderHook(({ v }) => useDebouncedValue(v, 150), {
      initialProps: { v: "" },
    });
    rerender({ v: "q" });
    act(() => vi.advanceTimersByTime(100));
    rerender({ v: "qwen" });
    act(() => vi.advanceTimersByTime(100));
    expect(result.current).toBe("");
    act(() => vi.advanceTimersByTime(50));
    expect(result.current).toBe("qwen");
  });
});
