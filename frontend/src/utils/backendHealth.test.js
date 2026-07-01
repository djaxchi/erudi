import { describe, it, expect, vi } from "vitest";
import { confirmBackendHealth } from "./backendHealth.js";

const URL = "http://127.0.0.1:8765/erudi/health/";

describe("confirmBackendHealth", () => {
  it("returns true immediately on a first successful health check (no sleep)", async () => {
    const fetchFn = vi.fn().mockResolvedValue({ ok: true });
    const sleepFn = vi.fn().mockResolvedValue();
    const ok = await confirmBackendHealth({ fetchFn, url: URL, sleepFn });
    expect(ok).toBe(true);
    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(sleepFn).not.toHaveBeenCalled();
  });

  it("retries with backoff and succeeds", async () => {
    const fetchFn = vi
      .fn()
      .mockResolvedValueOnce({ ok: false })
      .mockRejectedValueOnce(new Error("ECONNREFUSED"))
      .mockResolvedValueOnce({ ok: true });
    const sleepFn = vi.fn().mockResolvedValue();
    const ok = await confirmBackendHealth({ fetchFn, url: URL, sleepFn });
    expect(ok).toBe(true);
    expect(fetchFn).toHaveBeenCalledTimes(3);
    expect(sleepFn.mock.calls.map((c) => c[0])).toEqual([5000, 10000]);
  });

  it("gives up after the full backoff and reports failure", async () => {
    const fetchFn = vi.fn().mockResolvedValue({ ok: false });
    const sleepFn = vi.fn().mockResolvedValue();
    const ok = await confirmBackendHealth({ fetchFn, url: URL, sleepFn });
    expect(ok).toBe(false);
    // 1 initial + 3 backoff retries = 4 attempts; sleeps 5s/10s/20s between.
    expect(fetchFn).toHaveBeenCalledTimes(4);
    expect(sleepFn.mock.calls.map((c) => c[0])).toEqual([5000, 10000, 20000]);
  });

  it("treats a thrown fetch as a failed attempt", async () => {
    const fetchFn = vi.fn().mockRejectedValue(new Error("network down"));
    const sleepFn = vi.fn().mockResolvedValue();
    const ok = await confirmBackendHealth({ fetchFn, url: URL, sleepFn, backoff: [1] });
    expect(ok).toBe(false);
    expect(fetchFn).toHaveBeenCalledTimes(2);
  });
});
