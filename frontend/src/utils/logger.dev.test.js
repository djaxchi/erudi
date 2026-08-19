// @vitest-environment jsdom
/* eslint-disable no-console -- asserting on the console echo is the point here */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Dev-only logger behavior needs NODE_ENV=development at module load, so the
// module is re-imported fresh per test. Also pins the last-resort
// "[unserializable]" path (data whose JSON AND String conversions both throw).

let sendSpy;

beforeEach(() => {
  vi.resetModules();
  sendSpy = vi.fn();
  window.logAPI = { send: sendSpy };
  vi.spyOn(console, "log").mockImplementation(() => {});
  vi.spyOn(console, "debug").mockImplementation(() => {});
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  delete window.logAPI;
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

describe("logger in development", () => {
  it("forwards debug entries and echoes info to the console", async () => {
    vi.stubEnv("NODE_ENV", "development");
    const { createLogger } = await import("./logger.js");
    const log = createLogger("DevNS");

    log.debug("debug message", { a: 1 });
    log.info("info message");

    expect(console.debug).toHaveBeenCalledWith("[DevNS] debug message", { a: 1 });
    expect(console.log).toHaveBeenCalledWith("[DevNS] info message");
    const debugEntry = sendSpy.mock.calls.map(([e]) => e).find((e) => e.level === "debug");
    expect(debugEntry).toMatchObject({ ns: "DevNS", msg: "debug message" });
  });
});

describe("logger serialization last resort", () => {
  it("labels data that can be neither JSON- nor String-serialized", async () => {
    const { createLogger } = await import("./logger.js");
    const log = createLogger("NS");

    const evil = {
      toJSON() {
        throw new Error("no json");
      },
      toString() {
        throw new Error("no string");
      },
    };
    log.error("bad data", evil);

    const entry = sendSpy.mock.calls.map(([e]) => e).find((e) => e.msg === "bad data");
    expect(entry.data).toBe("[unserializable]");
  });
});
