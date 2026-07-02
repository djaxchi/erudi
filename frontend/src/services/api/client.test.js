// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { apiClient } from "./client";

const okResponse = (body = { ok: true }) => ({
  ok: true,
  status: 200,
  json: async () => body,
});

let sendSpy;
let fetchMock;

beforeEach(() => {
  sendSpy = vi.fn();
  window.logAPI = { send: sendSpy };
  fetchMock = vi.fn().mockResolvedValue(okResponse());
  vi.stubGlobal("fetch", fetchMock);
  vi.spyOn(console, "warn").mockImplementation(() => {});
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  delete window.logAPI;
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const clientEntries = () =>
  sendSpy.mock.calls.map(([entry]) => entry).filter((e) => e.ns === "APIClient");
const entryData = (msg) => {
  const entry = clientEntries().find((e) => e.msg === msg);
  return entry ? JSON.parse(entry.data) : null;
};

describe("APIClient request tracing", () => {
  it("sets an X-Request-ID header on every request", async () => {
    await apiClient.get("/llms/");
    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers["X-Request-ID"]).toMatch(/^fe-[0-9a-z]+-\d+$/);
  });

  it("generates a fresh request id per call", async () => {
    await apiClient.get("/a");
    await apiClient.get("/b");
    const rids = fetchMock.mock.calls.map(([, init]) => init.headers["X-Request-ID"]);
    expect(new Set(rids).size).toBe(2);
  });

  it("logs request start and completion with the same rid", async () => {
    await apiClient.post("/conversations/", { name: "hello" });

    const start = entryData("api.request");
    const done = entryData("api.response");
    expect(start).toBeTruthy();
    expect(done).toBeTruthy();
    expect(start.rid).toBe(done.rid);
    expect(start.method).toBe("POST");
    expect(start.path).toBe("/conversations/");
    expect(start.body).toContain("hello");
    expect(done.status).toBe(200);
    expect(typeof done.duration_ms).toBe("number");

    // The rid in the logs is the one that went over the wire.
    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers["X-Request-ID"]).toBe(start.rid);
  });

  it("truncates the logged body preview at 500 chars", async () => {
    await apiClient.post("/conversations/", { blob: "z".repeat(600) });
    const start = entryData("api.request");
    expect(start.body.length).toBeLessThan(600);
    expect(start.body).toMatch(/… \[\+\d+\]$/);
  });

  it("logs a failure entry with rid, error, and duration on HTTP errors", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: "boom",
      json: async () => ({ detail: "kaput" }),
    });

    await expect(apiClient.get("/llms/")).rejects.toThrow("kaput");

    const fail = entryData("api.failure");
    expect(fail).toBeTruthy();
    expect(fail.error).toBe("kaput");
    expect(fail.status).toBe(500);
    expect(typeof fail.duration_ms).toBe("number");
    expect(fail.rid).toBe(entryData("api.request").rid);
  });
});
