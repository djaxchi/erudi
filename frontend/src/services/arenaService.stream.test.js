import { describe, it, expect, vi, beforeEach } from "vitest";

// Streaming path of askArena: chunks are decoded, forwarded to onStreamChunk
// as they arrive, and the trimmed concatenation is returned. A non-OK response
// must reject before any body read.

const { tracedFetchMock } = vi.hoisted(() => ({ tracedFetchMock: vi.fn() }));

vi.mock("./api/client", () => ({ tracedFetch: tracedFetchMock }));

import { askArena } from "./arenaService.js";

const encoder = new TextEncoder();

/** Streaming Response stub that yields the given text chunks then finishes. */
const streamOf = (...chunks) => {
  const queue = chunks.map((text) => ({ done: false, value: encoder.encode(text) }));
  queue.push({ done: true, value: undefined });
  return {
    ok: true,
    body: { getReader: () => ({ read: async () => queue.shift() }) },
  };
};

beforeEach(() => {
  tracedFetchMock.mockReset();
});

describe("askArena streaming", () => {
  it("forwards each decoded chunk to onStreamChunk and returns the trimmed full text", async () => {
    tracedFetchMock.mockResolvedValue(streamOf("Hello ", "world", "  "));
    const onStreamChunk = vi.fn();

    const result = await askArena({ question: "hi", llmId: 1, onStreamChunk });

    expect(onStreamChunk.mock.calls.map(([c]) => c)).toEqual(["Hello ", "world", "  "]);
    expect(result).toBe("Hello world");
  });

  it("works without an onStreamChunk callback", async () => {
    tracedFetchMock.mockResolvedValue(streamOf("plain answer"));

    await expect(askArena({ question: "hi", llmId: 1 })).resolves.toBe("plain answer");
  });

  it("rejects when the backend answers non-OK, before reading any body", async () => {
    const getReader = vi.fn();
    tracedFetchMock.mockResolvedValue({ ok: false, status: 500, body: { getReader } });

    await expect(askArena({ question: "hi", llmId: 1 })).rejects.toThrow("Arena query failed");
    expect(getReader).not.toHaveBeenCalled();
  });
});
