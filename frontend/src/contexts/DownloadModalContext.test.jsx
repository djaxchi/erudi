// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, act } from "@testing-library/react";

// The download modal owns the full download lifecycle and had zero tests. These
// drive it through its public surface (open -> confirm -> 2s poll) and assert the
// observable results a consumer relies on: the completion counter/timestamp
// (#205), the confirmed callback fan-out, and — critically — the cancel-vs-fail
// split (#133), where a cancelled job must reach onError with the CANCELLED
// sentinel and must NOT bump the completion counter or look like a failure.
//
// tracedFetch is mocked; fake timers drive the setInterval poll deterministically.

const { tracedFetchMock } = vi.hoisted(() => ({ tracedFetchMock: vi.fn() }));

vi.mock("../services/api/client", () => ({
  default: { get: vi.fn() },
  apiClient: { get: vi.fn() },
  tracedFetch: tracedFetchMock,
}));

// Child UI is not under test — expose the two lifecycle triggers as plain buttons.
vi.mock("../components/modals/ConfirmationModal", () => ({
  default: ({ onConfirm, onCancel }) => (
    <div>
      <button onClick={onConfirm}>CONFIRM</button>
      <button onClick={onCancel}>DISMISS</button>
    </div>
  ),
}));
vi.mock("../components/modals/ErrorModal", () => ({ default: () => null }));
vi.mock("../components/Spinner", () => ({ default: () => null }));

import { DownloadModalProvider, useDownloadModal } from "./DownloadModalContext";
import { DOWNLOAD_CANCELLED } from "../utils/downloadStatus";

// Per-test configurable responders for the POST-start / status-poll / cancel URLs.
let postResponder;
let statusResponder;
let cancelResponder;

const onComplete = vi.fn();
const onError = vi.fn();
let currentModel;

function Consumer() {
  const ctx = useDownloadModal();
  return (
    <>
      <button onClick={() => ctx.open(currentModel, { onComplete, onError })}>OPEN</button>
      <span data-testid="downloading">{String(ctx.isDownloading)}</span>
      <span data-testid="completions">{String(ctx.completionCount)}</span>
      <span data-testid="lastCompleted">{ctx.lastCompletedAt === null ? "null" : "set"}</span>
    </>
  );
}

const renderProvider = () =>
  render(
    <DownloadModalProvider>
      <Consumer />
    </DownloadModalProvider>
  );

const val = (id) => screen.getByTestId(id).textContent;

// open -> confirm -> let the POST resolve and fire exactly one 2s poll tick.
const startAndPollOnce = async () => {
  await act(async () => {
    fireEvent.click(screen.getByText("OPEN"));
  });
  await act(async () => {
    fireEvent.click(screen.getByText("CONFIRM"));
    await vi.advanceTimersByTimeAsync(2000);
  });
};

beforeEach(() => {
  vi.useFakeTimers();
  const root = document.createElement("div");
  root.setAttribute("id", "modal-root");
  document.body.appendChild(root);

  onComplete.mockReset();
  onError.mockReset();
  currentModel = { id: 1, name: "Base Model" };

  postResponder = () => ({ ok: true, json: async () => ({ id: "job1" }) });
  statusResponder = () => ({
    ok: true,
    json: async () => ({ status: "completed", progress: 100, time_left: 0 }),
  });
  cancelResponder = () => ({ ok: true });

  tracedFetchMock.mockReset();
  tracedFetchMock.mockImplementation(async (url, opts = {}) => {
    const u = String(url);
    const method = opts.method || "GET";
    if (method === "POST" && (u.endsWith("/download") || u.includes("/download/huggingface"))) {
      return postResponder();
    }
    if (u.includes("/downloads/") && u.endsWith("/cancel")) {
      return cancelResponder();
    }
    if (u.includes("/downloads/") && u.endsWith("/status")) {
      return statusResponder();
    }
    return { ok: true, json: async () => ({}) };
  });
});

afterEach(() => {
  cleanup();
  document.getElementById("modal-root")?.remove();
  vi.runOnlyPendingTimers();
  vi.useRealTimers();
});

const statusCalls = () =>
  tracedFetchMock.mock.calls.filter(
    ([u]) => String(u).includes("/downloads/") && String(u).endsWith("/status")
  );

describe("DownloadModalContext completion (#205)", () => {
  it("bumps the completion counter and timestamp and fires onComplete once", async () => {
    renderProvider();
    expect(val("completions")).toBe("0");
    expect(val("lastCompleted")).toBe("null");

    await startAndPollOnce();

    expect(val("completions")).toBe("1");
    expect(val("lastCompleted")).toBe("set");
    expect(val("downloading")).toBe("false");
    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(onError).not.toHaveBeenCalled();
  });

  it("downloads a catalog model by numeric id", async () => {
    renderProvider();
    await startAndPollOnce();

    const post = tracedFetchMock.mock.calls.find(([, o]) => o?.method === "POST");
    expect(String(post[0])).toMatch(/\/llms\/1\/download$/);
  });

  it("downloads a HuggingFace search hit by link, preserving an unmeasured size as null", async () => {
    currentModel = {
      name: "HF Hit",
      link: "org/repo",
      type: "chat",
      param_size: null,
      quantized: true,
      category: "general",
    };
    renderProvider();
    await startAndPollOnce();

    const post = tracedFetchMock.mock.calls.find(
      ([u, o]) => o?.method === "POST" && String(u).includes("/llms/download/huggingface")
    );
    expect(post).toBeTruthy();
    const body = JSON.parse(post[1].body);
    expect(body.link).toBe("org/repo");
    expect(body.param_size).toBeNull(); // not laundered into a plausible default (#201)
  });
});

describe("DownloadModalContext failure and cancel routing", () => {
  it("routes a failed job to onError with the backend message and does not count it", async () => {
    statusResponder = () => ({
      ok: true,
      json: async () => ({ status: "failed", error_message: "disk full", progress: 0 }),
    });
    renderProvider();

    await startAndPollOnce();

    expect(onError).toHaveBeenCalledWith("disk full");
    expect(onComplete).not.toHaveBeenCalled();
    expect(val("completions")).toBe("0");
    expect(val("downloading")).toBe("false");
  });

  it("routes a cancelled job to onError with the CANCELLED sentinel, not a failure (#133)", async () => {
    statusResponder = () => ({ ok: true, json: async () => ({ status: DOWNLOAD_CANCELLED }) });
    renderProvider();

    await startAndPollOnce();

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledWith(DOWNLOAD_CANCELLED);
    expect(onComplete).not.toHaveBeenCalled();
    expect(val("completions")).toBe("0");
  });

  it("stops silently on a 404 (job already cleaned up) without firing any callback", async () => {
    statusResponder = () => ({ ok: false, status: 404, statusText: "Not Found" });
    renderProvider();

    await startAndPollOnce();

    expect(onComplete).not.toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
    expect(val("downloading")).toBe("false");
  });

  it("surfaces a poll network error through onError and stops downloading", async () => {
    statusResponder = () => {
      throw new TypeError("Failed to fetch");
    };
    renderProvider();

    await startAndPollOnce();

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError.mock.calls[0][0]).toContain("An error occured during download");
    expect(val("downloading")).toBe("false");
  });

  it("reports a failed download START through onError and never begins polling", async () => {
    postResponder = () => ({ ok: false, status: 500, text: async () => "gone" });
    renderProvider();

    await startAndPollOnce();

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError.mock.calls[0][0]).toContain("Failed to start download (500)");
    expect(val("downloading")).toBe("false");
    expect(statusCalls()).toHaveLength(0); // no interval was ever armed
  });
});

describe("DownloadModalContext user cancel", () => {
  it("POSTs the cancel endpoint for the running job when the user cancels", async () => {
    // Keep the job 'running' so the poll never completes it out from under us.
    statusResponder = () => ({
      ok: true,
      json: async () => ({ status: "running", progress: 10, time_left: 60 }),
    });
    renderProvider();

    // Start; jobId is captured from the POST response.
    await act(async () => {
      fireEvent.click(screen.getByText("OPEN"));
    });
    await act(async () => {
      fireEvent.click(screen.getByText("CONFIRM"));
      await vi.advanceTimersByTimeAsync(0); // flush POST -> setJobId, no poll yet
    });

    // Reveal the expanded bar (default is collapsed) to expose the Cancel control.
    await act(async () => {
      fireEvent.click(screen.getByLabelText("Expand"));
    });
    await act(async () => {
      fireEvent.click(screen.getByLabelText("Cancel"));
    });

    const cancel = tracedFetchMock.mock.calls.find(
      ([u, o]) => o?.method === "POST" && String(u).endsWith("/cancel")
    );
    expect(cancel).toBeTruthy();
    expect(String(cancel[0])).toMatch(/\/llms\/downloads\/job1\/cancel$/);
  });
});
