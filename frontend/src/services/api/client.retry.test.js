// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { apiClient } from "./client";

// client.test.js covers the request-TRACING surface only. This file locks the
// resilience core that #116 calls out and that had no coverage: exponential-
// backoff retry on transient errors, the AbortError -> TIMEOUT normalization,
// and handleErrorResponse's status/code/data shaping. retryDelay is zeroed so
// the retry path runs without real wall-clock waits; a dedicated test restores
// it to assert the backoff arithmetic via a sleep spy.

const okJson = (body = {}) => ({ ok: true, status: 200, json: async () => body });

let fetchMock;
let saved;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  vi.spyOn(console, "warn").mockImplementation(() => {});
  vi.spyOn(console, "error").mockImplementation(() => {});
  vi.spyOn(console, "log").mockImplementation(() => {});
  saved = {
    retryDelay: apiClient.retryDelay,
    maxRetries: apiClient.maxRetries,
    timeout: apiClient.timeout,
  };
  apiClient.retryDelay = 0; // collapse backoff waits for the transient-retry tests
});

afterEach(() => {
  Object.assign(apiClient, saved);
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("APIClient transient-error retry", () => {
  it("retries a transient network TypeError and resolves on the next attempt", async () => {
    fetchMock
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(okJson({ ok: 1 }));

    await expect(apiClient.get("/x")).resolves.toEqual({ ok: 1 });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("retries a transient error code (ECONNREFUSED) then succeeds", async () => {
    const refused = Object.assign(new Error("connect ECONNREFUSED"), { code: "ECONNREFUSED" });
    fetchMock.mockRejectedValueOnce(refused).mockResolvedValueOnce(okJson({ ok: 1 }));

    await expect(apiClient.get("/x")).resolves.toEqual({ ok: 1 });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("gives up after maxRetries and rethrows the original transient error", async () => {
    apiClient.maxRetries = 3;
    const err = new TypeError("Failed to fetch");
    fetchMock.mockRejectedValue(err);

    await expect(apiClient.get("/x")).rejects.toBe(err);
    // attempts 1 and 2 retry (attempt < 3); attempt 3 throws -> exactly 3 calls.
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("does NOT retry a non-transient error", async () => {
    const err = new Error("boom"); // plain Error, no fetch-y message, no transient code
    fetchMock.mockRejectedValue(err);

    await expect(apiClient.get("/x")).rejects.toBe(err);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("waits with exponential backoff between attempts", async () => {
    apiClient.retryDelay = 1000;
    apiClient.maxRetries = 3;
    const sleepSpy = vi.spyOn(apiClient, "sleep").mockResolvedValue();
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(apiClient.get("/x")).rejects.toThrow();

    // 1000 * 2^0 before attempt 2, 1000 * 2^1 before attempt 3; none before giving up.
    expect(sleepSpy.mock.calls.map(([ms]) => ms)).toEqual([1000, 2000]);
  });
});

describe("APIClient timeout normalization", () => {
  it("maps an AbortError to a TIMEOUT error and does not retry", async () => {
    const aborted = Object.assign(new Error("The operation was aborted"), { name: "AbortError" });
    fetchMock.mockRejectedValueOnce(aborted);

    await expect(apiClient.get("/x")).rejects.toMatchObject({
      message: "Request timeout",
      code: "TIMEOUT",
    });
    // The abort is caught and converted before the retry check -> single call.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("APIClient error normalization (handleErrorResponse)", () => {
  it("shapes an HTTP error into message/status/code/data using `detail`", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 422,
      statusText: "Unprocessable Entity",
      json: async () => ({ detail: "bad field" }),
    });

    const err = await apiClient.get("/x").catch((e) => e);
    expect(err.message).toBe("bad field");
    expect(err.status).toBe(422);
    expect(err.code).toBe("HTTP_422");
    expect(err.data).toEqual({ detail: "bad field" });
  });

  it("falls back detail -> message -> generic for the error text", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 400,
      statusText: "Bad Request",
      json: async () => ({ message: "only a message" }),
    });
    await expect(apiClient.get("/a")).rejects.toThrow("only a message");

    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: async () => ({}),
    });
    await expect(apiClient.get("/b")).rejects.toThrow("API Error: 500");
  });

  it("uses statusText when the error body is not JSON", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 503,
      statusText: "Service Unavailable",
      json: async () => {
        throw new SyntaxError("Unexpected token < in JSON");
      },
    });

    const err = await apiClient.get("/x").catch((e) => e);
    expect(err.message).toBe("Service Unavailable");
    expect(err.code).toBe("HTTP_503");
    expect(err.data).toEqual({ detail: "Service Unavailable" });
  });

  it("does not retry HTTP error responses", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: async () => ({ detail: "boom" }),
    });

    await expect(apiClient.get("/x")).rejects.toThrow("boom");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("APIClient response handling", () => {
  it("returns the raw Response when the success body is not JSON", async () => {
    const resp = {
      ok: true,
      status: 200,
      json: async () => {
        throw new SyntaxError("not json");
      },
    };
    fetchMock.mockResolvedValueOnce(resp);

    await expect(apiClient.get("/x")).resolves.toBe(resp);
  });

  it("serializes a POST body as JSON on the wire", async () => {
    fetchMock.mockResolvedValueOnce(okJson({}));

    await apiClient.post("/conversations/", { name: "hi" });

    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ name: "hi" });
    expect(init.headers["Content-Type"]).toBe("application/json");
  });
});
