// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createLogger } from "./logger";

let sendSpy;

beforeEach(() => {
  sendSpy = vi.fn();
  window.logAPI = { send: sendSpy };
  vi.spyOn(console, "warn").mockImplementation(() => {});
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  delete window.logAPI;
  vi.restoreAllMocks();
});

describe("createLogger bridge forwarding", () => {
  it("forwards log() and info() at info level with namespace, message, and ts", () => {
    const logger = createLogger("NS");
    logger.log("hello", { a: 1 });
    logger.info("world");

    expect(sendSpy).toHaveBeenCalledTimes(2);
    const [first, second] = sendSpy.mock.calls.map(([entry]) => entry);
    expect(first).toMatchObject({ level: "info", ns: "NS", msg: "hello", data: '{"a":1}' });
    expect(first.ts).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
    expect(second).toMatchObject({ level: "info", ns: "NS", msg: "world" });
    expect(second.data).toBeUndefined();
  });

  it("forwards warn and error with their levels (console kept)", () => {
    const logger = createLogger("NS");
    logger.warn("careful", { retry: true });
    logger.error("boom");

    const levels = sendSpy.mock.calls.map(([entry]) => entry.level);
    expect(levels).toEqual(["warn", "error"]);
    expect(console.warn).toHaveBeenCalled();
    expect(console.error).toHaveBeenCalled();
  });

  it("serializes data to JSON and truncates at 2000 chars", () => {
    createLogger("NS").warn("big", "x".repeat(3000));
    const entry = sendSpy.mock.calls[0][0];
    expect(entry.data.startsWith("xxxxxxxxxx")).toBe(true);
    expect(entry.data.endsWith("… [+1000]")).toBe(true);
    expect(entry.data.length).toBe(2000 + "… [+1000]".length);
  });

  it("serializes Error objects readably", () => {
    createLogger("NS").error("failed", new TypeError("kaput"));
    const entry = sendSpy.mock.calls[0][0];
    expect(entry.data).toBe("TypeError: kaput");
  });

  it("does not forward debug outside development", () => {
    createLogger("NS").debug("hidden", { secret: true });
    expect(sendSpy).not.toHaveBeenCalled();
  });

  it("does not throw when the bridge is absent", () => {
    delete window.logAPI;
    const logger = createLogger("NS");
    expect(() => {
      logger.log("a");
      logger.info("b");
      logger.warn("c");
      logger.error("d");
    }).not.toThrow();
  });

  it("does not throw when the bridge itself throws", () => {
    window.logAPI = {
      send: () => {
        throw new Error("ipc down");
      },
    };
    expect(() => createLogger("NS").warn("x")).not.toThrow();
  });

  it("survives unserializable data", () => {
    const cyclic = {};
    cyclic.self = cyclic;
    expect(() => createLogger("NS").warn("cyclic", cyclic)).not.toThrow();
    const entry = sendSpy.mock.calls[0][0];
    expect(typeof entry.data).toBe("string");
  });
});
