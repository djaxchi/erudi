// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor, act } from "@testing-library/react";
import ConnectionStatus from "./ConnectionStatus.jsx";
import { reportNetworkFailure, reportNetworkSuccess } from "../utils/networkStatus";

// The pill reads one local signal and one free one:
//   GET /health/ -> {status, db: "ok"|"recovering"|"failed"}
//   connectivity -> navigator.onLine + online/offline, corrected by failed
//                   requests (utils/networkStatus). No request leaves the
//                   machine to answer it.
// These tests assert the priority table, poll-failure handling, recovery, and
// the Restart -> backend:restart IPC wiring.

// Mutable per-test responder; returns a fetch-like Response or throws.
let respondHealth;

const okJson = (payload) => ({ ok: true, json: async () => payload });

const originalFetch = global.fetch;

/** Set navigator.onLine and fire the matching window event, as a browser does. */
function setLink(up) {
  Object.defineProperty(window.navigator, "onLine", { value: up, configurable: true });
  window.dispatchEvent(new window.Event(up ? "online" : "offline"));
}

beforeEach(() => {
  // Default: everything healthy and online.
  respondHealth = () => okJson({ status: "ok", message: "Backend is running", db: "ok" });
  setLink(true);
  reportNetworkSuccess();

  global.fetch = vi.fn(async (url) => {
    const u = String(url);
    if (u.includes("/health/")) return respondHealth();
    return okJson({});
  });
});

afterEach(() => {
  cleanup();
  global.fetch = originalFetch;
  delete window.backendAPI;
  setLink(true);
  reportNetworkSuccess();
  vi.restoreAllMocks();
});

describe("ConnectionStatus pill (#166)", () => {
  it("shows green Connected when the backend is healthy and the machine is online", async () => {
    render(<ConnectionStatus />);

    expect(await screen.findByText("Connected")).toBeTruthy();

    const called = (needle) =>
      global.fetch.mock.calls.some(([url]) => String(url).includes(needle));
    await waitFor(() => expect(called("/health/")).toBe(true));
  });

  it("asks nobody about connectivity: the only request it makes is the local health check", async () => {
    render(<ConnectionStatus />);
    await screen.findByText("Connected");

    const urls = global.fetch.mock.calls.map(([url]) => String(url));
    expect(urls.every((u) => u.includes("/health/"))).toBe(true);
  });

  it("shows amber 'Restoring the database...' while db is recovering", async () => {
    respondHealth = () => okJson({ status: "ok", db: "recovering" });
    render(<ConnectionStatus />);

    expect(await screen.findByText("Restoring the database...")).toBeTruthy();
    // Not an error state: no Restart action for a transient recovery.
    expect(screen.queryByText("Restart")).toBeNull();
  });

  it("shows red 'Database error' with a Restart action when db has failed", async () => {
    respondHealth = () => okJson({ status: "ok", db: "failed" });
    render(<ConnectionStatus />);

    expect(await screen.findByText("Database error")).toBeTruthy();
    expect(screen.getByText("Restart")).toBeTruthy();
  });

  it("shows neutral 'Offline' when the machine has no network but backend+db are ok", async () => {
    setLink(false);
    render(<ConnectionStatus />);

    expect(await screen.findByText("Offline")).toBeTruthy();
    // Offline is informative, never an error: no Restart action.
    expect(screen.queryByText("Restart")).toBeNull();
  });

  it("priority: db=failed wins over being offline", async () => {
    respondHealth = () => okJson({ status: "ok", db: "failed" });
    setLink(false);
    render(<ConnectionStatus />);

    expect(await screen.findByText("Database error")).toBeTruthy();
    expect(screen.queryByText("Offline")).toBeNull();
  });

  it("shows red 'Backend unreachable' + Restart when the health poll fails", async () => {
    respondHealth = () => {
      throw new Error("network down");
    };
    render(<ConnectionStatus />);

    expect(await screen.findByText("Backend unreachable")).toBeTruthy();
    expect(screen.getByText("Restart")).toBeTruthy();
  });

  it("recovers: db recovering -> ok flips the pill back to green Connected", async () => {
    respondHealth = () => okJson({ status: "ok", db: "recovering" });
    // Short cadence so the follow-up poll fires within the test.
    render(<ConnectionStatus healthPollMs={20} />);

    expect(await screen.findByText("Restoring the database...")).toBeTruthy();

    // Database heals; the next poll should return to the green state.
    respondHealth = () => okJson({ status: "ok", db: "ok" });
    expect(await screen.findByText("Connected")).toBeTruthy();
  });

  it("Restart action calls the backend:restart IPC bridge", async () => {
    respondHealth = () => {
      throw new Error("network down");
    };
    window.backendAPI = { restartBackend: vi.fn().mockResolvedValue({ ok: true }) };
    render(<ConnectionStatus />);

    const restart = await screen.findByText("Restart");
    fireEvent.click(restart);

    expect(window.backendAPI.restartBackend).toHaveBeenCalledTimes(1);
  });
});

describe("ConnectionStatus connectivity signal", () => {
  it("flips to Offline the moment the link drops, with no poll to wait for", async () => {
    render(<ConnectionStatus />);
    await screen.findByText("Connected");

    await act(async () => {
      setLink(false);
    });

    expect(await screen.findByText("Offline")).toBeTruthy();
  });

  it("comes back to Connected when the link returns", async () => {
    setLink(false);
    render(<ConnectionStatus />);
    await screen.findByText("Offline");

    await act(async () => {
      setLink(true);
    });

    expect(await screen.findByText("Connected")).toBeTruthy();
  });

  it("believes a failed request even while the machine still claims a link", async () => {
    render(<ConnectionStatus />);
    await screen.findByText("Connected");

    await act(async () => {
      reportNetworkFailure();
    });

    expect(await screen.findByText("Offline")).toBeTruthy();
  });

  it("stops listening once unmounted, so a later link change is harmless", async () => {
    const { unmount } = render(<ConnectionStatus />);
    await screen.findByText("Connected");

    unmount();
    await act(async () => {
      setLink(false);
    });

    expect(screen.queryByText("Offline")).toBeNull();
  });
});
