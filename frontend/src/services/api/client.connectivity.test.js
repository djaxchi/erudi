// @vitest-environment jsdom
/**
 * The API client is where the app finds out that the network is really broken.
 *
 * Nothing polls a remote host any more, so the status pill would otherwise only
 * know what the operating system tells it -- and the OS says "link up" on a
 * captive portal, behind a dead DNS server, or on a Wi-Fi that goes nowhere.
 * A request that dies without a response is the honest counter-evidence, and a
 * request that completes is what takes it back. An HTTP error is neither: it
 * proves the path works, so it must leave connectivity alone.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { apiClient, tracedFetch } from "./client";
import { isNetworkOnline, reportNetworkSuccess } from "../../utils/networkStatus";

const okJson = (body = {}) => ({ ok: true, status: 200, json: async () => body });

let fetchMock;
let saved;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  vi.spyOn(console, "warn").mockImplementation(() => {});
  vi.spyOn(console, "error").mockImplementation(() => {});
  vi.spyOn(console, "log").mockImplementation(() => {});
  saved = { retryDelay: apiClient.retryDelay, maxRetries: apiClient.maxRetries };
  apiClient.retryDelay = 0;
});

afterEach(() => {
  Object.assign(apiClient, saved);
  reportNetworkSuccess();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("APIClient connectivity reporting", () => {
  it("reports offline once a request has failed at the network layer", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(apiClient.get("/llms/")).rejects.toThrow();

    expect(isNetworkOnline()).toBe(false);
  });

  it("goes back online as soon as a request completes", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(apiClient.get("/llms/")).rejects.toThrow();
    expect(isNetworkOnline()).toBe(false);

    fetchMock.mockReset();
    fetchMock.mockResolvedValue(okJson({ ok: true }));
    await apiClient.get("/llms/");

    expect(isNetworkOnline()).toBe(true);
  });

  it("leaves connectivity alone on an HTTP error, which proves the path works", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Server Error",
      json: async () => ({ detail: "boom" }),
    });

    await expect(apiClient.get("/llms/")).rejects.toThrow();

    expect(isNetworkOnline()).toBe(true);
  });

  it("reports offline from a raw tracedFetch failure too", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(tracedFetch("http://127.0.0.1:27182/erudi/llms/")).rejects.toThrow();

    expect(isNetworkOnline()).toBe(false);
  });

  it("does not report offline when the caller aborted the request", async () => {
    const aborted = new Error("aborted");
    aborted.name = "AbortError";
    fetchMock.mockRejectedValue(aborted);

    await expect(apiClient.get("/llms/")).rejects.toThrow();

    expect(isNetworkOnline()).toBe(true);
  });
});
