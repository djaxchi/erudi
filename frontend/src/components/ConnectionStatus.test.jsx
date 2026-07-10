// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import ConnectionStatus from "./ConnectionStatus.jsx";

// The pill reads two REAL backend signals instead of navigator.onLine (#166):
//   GET /health/                   -> {status, db: "ok"|"recovering"|"failed"}
//   GET /startup/connection-status -> {can_download_models: bool}
// These tests mock fetch and assert the priority table, poll-failure handling,
// recovery, and the Restart -> backend:restart IPC wiring.

// Mutable per-test responders; each returns a fetch-like Response or throws.
let respondHealth;
let respondConnection;

const okJson = (payload) => ({ ok: true, json: async () => payload });

const originalFetch = global.fetch;

beforeEach(() => {
  // Default: everything healthy and online.
  respondHealth = () => okJson({ status: "ok", message: "Backend is running", db: "ok" });
  respondConnection = () => okJson({ can_download_models: true, offline_mode: false });

  global.fetch = vi.fn(async (url) => {
    const u = String(url);
    if (u.includes("/health/")) return respondHealth();
    if (u.includes("/startup/connection-status")) return respondConnection();
    return okJson({});
  });
});

afterEach(() => {
  cleanup();
  global.fetch = originalFetch;
  delete window.backendAPI;
  vi.restoreAllMocks();
});

describe("ConnectionStatus pill (#166)", () => {
  it("reads BOTH real signals and shows green Connected when all is well", async () => {
    render(<ConnectionStatus />);

    expect(await screen.findByText("Connected")).toBeTruthy();

    const called = (needle) =>
      global.fetch.mock.calls.some(([url]) => String(url).includes(needle));
    await waitFor(() => expect(called("/health/")).toBe(true));
    await waitFor(() => expect(called("/startup/connection-status")).toBe(true));
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

  it("shows neutral 'Offline' when the internet probe is false but backend+db are ok", async () => {
    respondConnection = () => okJson({ can_download_models: false, offline_mode: true });
    render(<ConnectionStatus />);

    expect(await screen.findByText("Offline")).toBeTruthy();
    // Offline is informative, never an error: no Restart action.
    expect(screen.queryByText("Restart")).toBeNull();
  });

  it("priority: db=failed wins over an offline internet probe", async () => {
    respondHealth = () => okJson({ status: "ok", db: "failed" });
    respondConnection = () => okJson({ can_download_models: false });
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
    render(<ConnectionStatus healthPollMs={20} connectionPollMs={20} />);

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
