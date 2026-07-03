// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, cleanup, waitFor } from "@testing-library/react";

// A completed download is surfaced by the context as an incrementing
// completionCount (context STATE), not only through the per-download
// onComplete callback. Any mounted LandingPage must refresh its installed
// list when that counter ticks, regardless of which entry point started the
// download or whether the page remounted mid-download (#205).

const { tracedFetchMock, ctx } = vi.hoisted(() => ({
  tracedFetchMock: vi.fn(async () => ({ ok: true, json: async () => [] })),
  ctx: { completionCount: 0 },
}));

// The context value carries completionCount; the test drives it via `ctx`.
vi.mock("../contexts/DownloadModalContext", () => ({
  useDownloadModal: () => ({ open: vi.fn(), completionCount: ctx.completionCount }),
}));

vi.mock("../services/api/client", () => ({
  default: { get: vi.fn(async () => ({})) },
  apiClient: { get: vi.fn(async () => ({})) },
  tracedFetch: tracedFetchMock,
}));

vi.mock("react-router-dom", () => ({ useNavigate: () => vi.fn() }));

// Stub the heavy children — none are needed to observe the refresh fetch.
vi.mock("../components/Sidebar", () => ({ default: () => null }));
vi.mock("../components/ModelCollapsibleSection", () => ({ default: () => null }));
vi.mock("../components/ModelCard", () => ({ default: () => null }));
vi.mock("../components/ExploreModelCard", () => ({ default: () => null }));
vi.mock("../components/MachineReadout", () => ({ default: () => null }));
vi.mock("../components/HuggingFaceSearchPanel", () => ({ default: () => null }));
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

const localCalls = () =>
  tracedFetchMock.mock.calls.filter(([url]) => String(url).includes("/llms/local"));

beforeEach(() => {
  ctx.completionCount = 0;
  tracedFetchMock.mockClear();
  tracedFetchMock.mockImplementation(async () => ({ ok: true, json: async () => [] }));
});
afterEach(() => {
  cleanup();
});

describe("LandingPage refresh on download completion (#205)", () => {
  it("re-fetches the local models when the context completion counter ticks", async () => {
    const { rerender } = render(<LandingPage />);

    // Mount fetches the local list once.
    await waitFor(() => expect(localCalls().length).toBeGreaterThan(0));
    const before = localCalls().length;

    // A download somewhere completes -> context bumps completionCount.
    ctx.completionCount = 1;
    rerender(<LandingPage />);

    await waitFor(() => expect(localCalls().length).toBeGreaterThan(before));
  });

  it("does not refresh on mount when no download has completed", async () => {
    render(<LandingPage />);
    await waitFor(() => expect(localCalls().length).toBeGreaterThan(0));
    // The mount fetch (refreshCatalog) hits /llms/local exactly once; the
    // completion effect stays inert while completionCount is 0.
    expect(localCalls().length).toBe(1);
  });
});
