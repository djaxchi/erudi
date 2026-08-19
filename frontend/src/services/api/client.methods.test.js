// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { apiClient, tracedFetch } from "./client";

// Complements client.test.js: pins the PUT/PATCH/DELETE verb helpers (method +
// serialized body actually sent over the wire) and the body-preview
// summarization tracedFetch logs for non-string payloads (binary bodies must
// be described, never dumped).

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

const requestEntryData = () => {
  const entry = sendSpy.mock.calls
    .map(([e]) => e)
    .find((e) => e.ns === "APIClient" && e.msg === "api.request");
  return entry ? JSON.parse(entry.data) : null;
};

describe("APIClient verb helpers", () => {
  it("put() sends a PUT with the JSON-serialized data", async () => {
    await expect(apiClient.put("/llms/3", { name: "renamed" })).resolves.toEqual({ ok: true });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/llms/3");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body)).toEqual({ name: "renamed" });
  });

  it("patch() sends a PATCH with the JSON-serialized data", async () => {
    await expect(apiClient.patch("/conversations/9", { title: "t" })).resolves.toEqual({
      ok: true,
    });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/conversations/9");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body)).toEqual({ title: "t" });
  });

  it("delete() sends a DELETE with no body", async () => {
    await expect(apiClient.delete("/llms/3")).resolves.toEqual({ ok: true });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/llms/3");
    expect(init.method).toBe("DELETE");
    expect(init.body).toBeUndefined();
  });
});

describe("tracedFetch body previews", () => {
  it("summarizes a FormData body as kind + field count", async () => {
    const form = new FormData();
    form.append("file", new Blob(["abc"]), "a.txt");
    form.append("kb_id", "7");

    await tracedFetch("http://127.0.0.1:27182/erudi/upload", { method: "POST", body: form });

    expect(requestEntryData()).toMatchObject({ body_kind: "FormData", body_size: 2 });
  });

  it("summarizes a Blob body as kind + byte size", async () => {
    await tracedFetch("http://127.0.0.1:27182/erudi/upload", {
      method: "POST",
      body: new Blob(["abcd"]),
    });

    expect(requestEntryData()).toMatchObject({ body_kind: "Blob", body_size: 4 });
  });

  it("summarizes an ArrayBuffer body as kind + byte length", async () => {
    await tracedFetch("http://127.0.0.1:27182/erudi/upload", {
      method: "POST",
      body: new ArrayBuffer(8),
    });

    expect(requestEntryData()).toMatchObject({ body_kind: "ArrayBuffer", body_size: 8 });
  });

  it("summarizes a typed-array body with its constructor name", async () => {
    await tracedFetch("http://127.0.0.1:27182/erudi/upload", {
      method: "POST",
      body: new Uint8Array(16),
    });

    expect(requestEntryData()).toMatchObject({ body_kind: "Uint8Array", body_size: 16 });
  });

  it("previews a URLSearchParams body as its string form", async () => {
    await tracedFetch("http://127.0.0.1:27182/erudi/upload", {
      method: "POST",
      body: new URLSearchParams({ a: "1" }),
    });

    expect(requestEntryData()).toMatchObject({ body: "a=1" });
  });

  it("falls back to typeof for other body kinds", async () => {
    await tracedFetch("http://127.0.0.1:27182/erudi/upload", {
      method: "POST",
      body: { not: "a fetch body" },
    });

    expect(requestEntryData()).toMatchObject({ body_kind: "object" });
  });
});
