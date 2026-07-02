// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";

// A failed download start (e.g. 404 on a stale catalog id) must silently
// refresh the models lists so the stale entry disappears and the user's next
// click works (#167). No new error UI is asserted here — the refresh is the fix.

const { tracedFetchMock } = vi.hoisted(() => ({
  tracedFetchMock: vi.fn(async () => ({ ok: true, json: async () => [] })),
}));

// The download modal immediately reports a failed start to the page callbacks.
vi.mock("../contexts/DownloadModalContext", () => ({
  useDownloadModal: () => ({
    open: (model, callbacks) => {
      callbacks.onError("Failed to start download (404): gone");
    },
  }),
}));

vi.mock("../services/api/client", () => ({
  default: { get: vi.fn(async () => ({})) },
  apiClient: { get: vi.fn(async () => ({})) },
  tracedFetch: tracedFetchMock,
}));

vi.mock("react-router-dom", () => ({ useNavigate: () => vi.fn() }));

// Stub the heavy children; keep one prop-receiving child as the download trigger.
vi.mock("../components/Sidebar", () => ({ default: () => null }));
vi.mock("../components/ModelCollapsibleSection", () => ({ default: () => null }));
vi.mock("../components/ModelCard", () => ({ default: () => null }));
vi.mock("../components/ExploreModelCard", () => ({ default: () => null }));
vi.mock("../components/MachineReadout", () => ({ default: () => null }));
vi.mock("../components/HuggingFaceSearchPanel", () => ({
  default: ({ onDownload }) => <button onClick={() => onDownload({ id: 3, name: "x" })}>DL</button>,
}));
vi.mock("../components/CategorySections", () => ({ default: () => null }));
vi.mock("../components/CatalogFilters", () => ({ default: () => null }));
vi.mock("../components/ExploreIndex", () => ({ default: () => null }));
vi.mock("../components/ConnectionStatus", () => ({ default: () => null }));
vi.mock("../components/LoadingPopup", () => ({ default: () => null }));
vi.mock("../components/modals/ModelInfoModal", () => ({ default: () => null }));
vi.mock("../components/modals/DeleteModelModal", () => ({ default: () => null }));
vi.mock("../components/modals/MessageModal", () => ({ default: () => null }));
vi.mock("../components/modals/WelcomeModal", () => ({ default: () => null }));
vi.mock("../assets/images/logos/logoerudifinal.png", () => ({ default: "logo.png" }));

import LandingPage from "./LandingPage.jsx";

const modelsCalls = () =>
  tracedFetchMock.mock.calls.filter(
    ([url]) => String(url).includes("/llms/local") || String(url).includes("/llms/remote")
  );

const renderAndSettle = async () => {
  render(<LandingPage />);
  // Mount fetches both models lists once.
  await waitFor(() => {
    const urls = modelsCalls().map(([url]) => String(url));
    expect(urls.some((u) => u.includes("/llms/local"))).toBe(true);
    expect(urls.some((u) => u.includes("/llms/remote"))).toBe(true);
  });
};

beforeEach(() => {
  tracedFetchMock.mockClear();
  tracedFetchMock.mockImplementation(async () => ({ ok: true, json: async () => [] }));
});
afterEach(() => {
  cleanup();
});

describe("LandingPage download start failure (#167)", () => {
  it("silently refreshes the models lists when a download fails to start", async () => {
    await renderAndSettle();
    const before = modelsCalls().length;

    fireEvent.click(screen.getByText("DL"));

    await waitFor(() => {
      const after = modelsCalls()
        .map(([url]) => String(url))
        .slice(before);
      expect(after.some((u) => u.includes("/llms/local"))).toBe(true);
      expect(after.some((u) => u.includes("/llms/remote"))).toBe(true);
    });
  });

  it("does not crash when the silent refresh itself fails", async () => {
    await renderAndSettle();
    const before = modelsCalls().length;
    tracedFetchMock.mockRejectedValueOnce(new Error("network down"));

    fireEvent.click(screen.getByText("DL"));

    await waitFor(() => {
      expect(modelsCalls().length).toBeGreaterThan(before);
    });
    // The page is still alive after the rejected refresh.
    expect(screen.getByText("DL")).toBeTruthy();
  });
});
