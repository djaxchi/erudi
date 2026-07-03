import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { EventEmitter } from "node:events";
import { gracefulShutdown } from "./backendShutdown.js";

// A minimal stand-in for a child_process: an EventEmitter (so once("exit") /
// emit("exit") work) with a spyable stdin.end() and an exitCode field.
function makeFakeProc({ exitCode = null } = {}) {
  const proc = new EventEmitter();
  proc.exitCode = exitCode;
  proc.stdin = { end: vi.fn() };
  return proc;
}

describe("gracefulShutdown", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("resolves 'graceful' when the child exits before the timeout (no kill)", async () => {
    const proc = makeFakeProc();
    const killFn = vi.fn();

    const p = gracefulShutdown(proc, { killFn });
    // stdin is closed to trigger the launcher's EOF watcher.
    expect(proc.stdin.end).toHaveBeenCalledTimes(1);

    // Child exits on its own well within the grace period.
    proc.emit("exit", 0, null);

    await expect(p).resolves.toBe("graceful");
    expect(killFn).not.toHaveBeenCalled();
  });

  it("hard-kills and resolves 'forced' when the child overruns the timeout", async () => {
    const proc = makeFakeProc();
    const killFn = vi.fn();

    const p = gracefulShutdown(proc, { timeoutMs: 8000, killFn });
    expect(killFn).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(8000);

    await expect(p).resolves.toBe("forced");
    expect(killFn).toHaveBeenCalledTimes(1);
    expect(killFn).toHaveBeenCalledWith(proc);
  });

  it("resolves 'noop' for a null process", async () => {
    const killFn = vi.fn();
    await expect(gracefulShutdown(null, { killFn })).resolves.toBe("noop");
    expect(killFn).not.toHaveBeenCalled();
  });

  it("resolves without killing when the process already exited", async () => {
    const proc = makeFakeProc({ exitCode: 0 });
    const killFn = vi.fn();

    const p = gracefulShutdown(proc, { killFn });
    // No wait needed: it exited already, so stdin is never touched either.
    expect(proc.stdin.end).not.toHaveBeenCalled();

    await expect(p).resolves.toBe("graceful");
    expect(killFn).not.toHaveBeenCalled();
  });
});
