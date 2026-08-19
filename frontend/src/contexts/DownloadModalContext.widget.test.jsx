// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, act } from "@testing-library/react";

// Facets not covered by DownloadModalContext.test.jsx: the expanded progress
// widget (time-left formatting across units, progress percent), dismissing the
// confirmation, and the two cancel fallbacks (no job id yet; cancel endpoint
// failing -> local cleanup with the CANCELLED sentinel).

const { tracedFetchMock } = vi.hoisted(() => ({ tracedFetchMock: vi.fn() }));

vi.mock("../services/api/client", () => ({
  default: { get: vi.fn() },
  apiClient: { get: vi.fn() },
  tracedFetch: tracedFetchMock,
}));

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

let postResponder;
let statusResponder;
let cancelResponder;

const onComplete = vi.fn();
const onError = vi.fn();

function Consumer() {
  const ctx = useDownloadModal();
  return (
    <>
      <button onClick={() => ctx.open({ id: 1, name: "Base Model" }, { onComplete, onError })}>
        OPEN
      </button>
      <span data-testid="downloading">{String(ctx.isDownloading)}</span>
    </>
  );
}

const renderProvider = () =>
  render(
    <DownloadModalProvider>
      <Consumer />
    </DownloadModalProvider>
  );

beforeEach(() => {
  vi.useFakeTimers();
  const root = document.createElement("div");
  root.setAttribute("id", "modal-root");
  document.body.appendChild(root);

  onComplete.mockReset();
  onError.mockReset();

  postResponder = () => ({ ok: true, json: async () => ({ id: "job1" }) });
  statusResponder = () => ({
    ok: true,
    json: async () => ({ status: "running", progress: 42.35, time_left: 3700 }),
  });
  cancelResponder = () => ({ ok: true });

  tracedFetchMock.mockReset();
  tracedFetchMock.mockImplementation(async (url, opts = {}) => {
    const u = String(url);
    const method = opts.method || "GET";
    if (method === "POST" && u.endsWith("/download")) return postResponder();
    if (u.includes("/downloads/") && u.endsWith("/cancel")) return cancelResponder();
    if (u.includes("/downloads/") && u.endsWith("/status")) return statusResponder();
    return { ok: true, json: async () => ({}) };
  });
});

afterEach(() => {
  cleanup();
  document.getElementById("modal-root")?.remove();
  vi.runOnlyPendingTimers();
  vi.useRealTimers();
});

// open -> confirm -> flush the POST and one 2s poll tick. The widget expands
// by itself at the 2s mark (the auto-uncollapse timeout), so no Expand click.
const startPollAndExpand = async () => {
  await act(async () => {
    fireEvent.click(screen.getByText("OPEN"));
  });
  await act(async () => {
    fireEvent.click(screen.getByText("CONFIRM"));
    await vi.advanceTimersByTimeAsync(2000);
  });
};

describe("Download widget progress readout", () => {
  it("shows the model, hours-scale time left and the progress percent while running", async () => {
    renderProvider();
    await startPollAndExpand();

    expect(screen.getByText(/Downloading:/).textContent).toContain("Base Model");
    expect(screen.getByText("1h 1m")).toBeTruthy(); // 3700s
    expect(screen.getByText("42.4 %")).toBeTruthy();
  });

  it("formats day-scale and minute-scale times and collapses back on demand", async () => {
    statusResponder = () => ({
      ok: true,
      json: async () => ({ status: "running", progress: 1, time_left: 90000 }),
    });
    renderProvider();
    await startPollAndExpand();
    expect(screen.getByText("1d 1h")).toBeTruthy(); // 90000s

    statusResponder = () => ({
      ok: true,
      json: async () => ({ status: "running", progress: 2, time_left: 95 }),
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(screen.getByText("1m 35s")).toBeTruthy();

    statusResponder = () => ({
      ok: true,
      json: async () => ({ status: "running", progress: 3, time_left: 40 }),
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(screen.getByText("40s")).toBeTruthy();

    // Collapse hides the readout again.
    await act(async () => {
      fireEvent.click(screen.getByLabelText("Collapse"));
    });
    expect(screen.queryByText(/Downloading:/)).toBeNull();
  });

  it("shows -- placeholders while the job is still pending", async () => {
    statusResponder = () => ({
      ok: true,
      json: async () => ({ status: "pending", progress: 0, time_left: null }),
    });
    renderProvider();
    await startPollAndExpand();

    expect(screen.getAllByText("--")).toHaveLength(2); // time left AND progress
  });
});

describe("Confirmation dismissal", () => {
  it("dismissing the confirmation starts nothing", async () => {
    renderProvider();
    await act(async () => {
      fireEvent.click(screen.getByText("OPEN"));
    });
    await act(async () => {
      fireEvent.click(screen.getByText("DISMISS"));
    });

    expect(screen.queryByText("CONFIRM")).toBeNull();
    expect(tracedFetchMock).not.toHaveBeenCalled();
    expect(screen.getByTestId("downloading").textContent).toBe("false");
  });
});

describe("Cancel fallbacks", () => {
  it("cancels locally with the CANCELLED sentinel when no job id exists yet", async () => {
    // POST never resolves: downloading is on, but jobId was never captured.
    postResponder = () => new Promise(() => {});
    renderProvider();

    await act(async () => {
      fireEvent.click(screen.getByText("OPEN"));
    });
    await act(async () => {
      fireEvent.click(screen.getByText("CONFIRM"));
      await vi.advanceTimersByTimeAsync(0);
    });
    await act(async () => {
      fireEvent.click(screen.getByLabelText("Expand"));
    });
    await act(async () => {
      fireEvent.click(screen.getByLabelText("Cancel"));
    });

    expect(onError).toHaveBeenCalledWith(DOWNLOAD_CANCELLED);
    expect(screen.getByTestId("downloading").textContent).toBe("false");
    // No cancel endpoint was hit — there was no job to cancel.
    expect(tracedFetchMock.mock.calls.some(([u]) => String(u).endsWith("/cancel"))).toBe(false);
  });

  it("cleans up locally with the CANCELLED sentinel when the cancel endpoint fails", async () => {
    cancelResponder = () => ({ ok: false, status: 500, statusText: "boom" });
    renderProvider();
    await startPollAndExpand();

    await act(async () => {
      fireEvent.click(screen.getByLabelText("Cancel"));
    });

    expect(onError).toHaveBeenCalledWith(DOWNLOAD_CANCELLED);
    expect(screen.getByTestId("downloading").textContent).toBe("false");
  });
});
