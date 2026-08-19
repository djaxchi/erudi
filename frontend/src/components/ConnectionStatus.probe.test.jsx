// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, waitFor, act } from "@testing-library/react";
import ConnectionStatus from "./ConnectionStatus";

// Facets beyond ConnectionStatus.test.jsx: a failed internet probe must stay
// "unknown" (never assert Offline), and browser online/offline events trigger
// an immediate optimistic re-poll of both signals.

let fetchMock;

const healthOk = { ok: true, json: async () => ({ status: "ok", db: "ok" }) };
const connectionOk = { ok: true, json: async () => ({ can_download_models: true }) };

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("ConnectionStatus probe resilience", () => {
  it("keeps green Connected when the internet probe fails (unknown, not Offline)", async () => {
    fetchMock.mockImplementation(async (url) => {
      if (String(url).includes("/health/")) return healthOk;
      throw new TypeError("probe timed out");
    });

    render(<ConnectionStatus />);

    await waitFor(() => expect(screen.getByText("Connected")).toBeTruthy());
    expect(screen.queryByText("Offline")).toBeNull();
  });

  it("re-polls both signals immediately on a browser online event", async () => {
    fetchMock.mockImplementation(async (url) =>
      String(url).includes("/health/") ? healthOk : connectionOk
    );
    render(<ConnectionStatus />);
    await waitFor(() => expect(screen.getByText("Connected")).toBeTruthy());

    const before = fetchMock.mock.calls.length;
    await act(async () => {
      window.dispatchEvent(new Event("online"));
    });

    await waitFor(() => expect(fetchMock.mock.calls.length).toBe(before + 2));
    const urls = fetchMock.mock.calls.slice(before).map(([u]) => String(u));
    expect(urls.some((u) => u.includes("/health/"))).toBe(true);
    expect(urls.some((u) => u.includes("/startup/connection-status"))).toBe(true);
  });

  it("flips to Offline via the fast-path re-poll after an offline event", async () => {
    let online = true;
    fetchMock.mockImplementation(async (url) => {
      if (String(url).includes("/health/")) return healthOk;
      return { ok: true, json: async () => ({ can_download_models: online }) };
    });
    render(<ConnectionStatus />);
    await waitFor(() => expect(screen.getByText("Connected")).toBeTruthy());

    online = false;
    await act(async () => {
      window.dispatchEvent(new Event("offline"));
    });

    await waitFor(() => expect(screen.getByText("Offline")).toBeTruthy());
  });
});
