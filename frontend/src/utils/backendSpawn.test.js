import { describe, it, expect } from "vitest";
import { buildBackendSpawnOptions } from "./backendSpawn.js";

const io = { cwd: "/work/dir", env: { PYTHONUTF8: "1" } };

describe("buildBackendSpawnOptions", () => {
  it("hides the console window on every platform (#142 Windows flash)", () => {
    for (const platform of ["win32", "darwin", "linux"]) {
      expect(buildBackendSpawnOptions(platform, io).windowsHide).toBe(true);
    }
  });

  it("detaches only on POSIX (process-group kill), never on Windows (taskkill /T)", () => {
    expect(buildBackendSpawnOptions("win32", io).detached).toBe(false);
    expect(buildBackendSpawnOptions("darwin", io).detached).toBe(true);
    expect(buildBackendSpawnOptions("linux", io).detached).toBe(true);
  });

  it("pipes stdio and passes cwd/env through unchanged", () => {
    const opts = buildBackendSpawnOptions("win32", io);
    expect(opts.stdio).toEqual(["pipe", "pipe", "pipe"]);
    expect(opts.cwd).toBe("/work/dir");
    expect(opts.env).toBe(io.env);
  });
});
