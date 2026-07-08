// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";

// Guarded base delete (#225): deleting a local model first pre-checks
// GET /llms/{id}/dependents. With dependents, the confirmation dialog lists
// the assistants + conversation count and "Delete anyway" sends the DELETE
// with ?orphan_dependents=true. Without dependents the classic dialog and the
// plain DELETE are unchanged. A 409 on the plain DELETE (pre-check raced or
// failed) is the safety net: its payload reopens the dialog with dependents.

const { tracedFetchMock } = vi.hoisted(() => ({
  tracedFetchMock: vi.fn(async () => ({ ok: true, json: async () => [] })),
}));

vi.mock("../contexts/DownloadModalContext", () => ({
  useDownloadModal: () => ({ open: vi.fn(), completionCount: 0 }),
}));

vi.mock("../services/api/client", () => ({
  default: { get: vi.fn(async () => ({})) },
  apiClient: { get: vi.fn(async () => ({})) },
  tracedFetch: tracedFetchMock,
}));

vi.mock("react-router-dom", () => ({ useNavigate: () => vi.fn() }));

// Stub the heavy children, but keep ModelCard (the delete trigger) and
// DeleteModelModal (the dialog under test) REAL.
vi.mock("../components/Sidebar", () => ({ default: () => null }));
vi.mock("../components/ModelCollapsibleSection", () => ({ default: () => null }));
vi.mock("../components/ExploreModelCard", () => ({ default: () => null }));
vi.mock("../components/MachineReadout", () => ({ default: () => null }));
vi.mock("../components/HuggingFaceSearchPanel", () => ({ default: () => null }));
vi.mock("../components/CategorySections", () => ({ default: () => null }));
vi.mock("../components/CatalogFilters", () => ({ default: () => null }));
vi.mock("../components/ExploreIndex", () => ({ default: () => null }));
vi.mock("../components/ConnectionStatus", () => ({ default: () => null }));
vi.mock("../components/LoadingPopup", () => ({ default: () => null }));
vi.mock("../components/modals/ModelInfoModal", () => ({ default: () => null }));
vi.mock("../components/modals/MessageModal", () => ({ default: () => null }));
vi.mock("../components/modals/WelcomeModal", () => ({ default: () => null }));
vi.mock("../assets/images/logos/logoerudifinal.png", () => ({ default: "logo.png" }));

import LandingPage from "./LandingPage.jsx";

const localModels = [
  {
    id: 5,
    name: "base-model",
    link: "/models/5",
    model_metadata: "size: 4.2 GB",
    weights_available: true,
    kb_id: null,
  },
];

const dependents = {
  assistants: [{ id: 9, name: "kb-helper", kb_id: 3, conversation_count: 2 }],
  own_conversation_count: 1,
  total_conversation_count: 3,
};

const jsonResponse = (payload) => ({ ok: true, status: 200, json: async () => payload });

const makeRouteFetch =
  ({ dependentsResponse, deleteResponses = [] } = {}) =>
  async (url, opts = {}) => {
    const u = String(url);
    if (opts.method === "DELETE") {
      return deleteResponses.length > 0 ? deleteResponses.shift() : jsonResponse({});
    }
    if (u.endsWith("/llms/5/dependents")) {
      if (dependentsResponse instanceof Error) throw dependentsResponse;
      return jsonResponse(dependentsResponse);
    }
    if (u.endsWith("/llms/local")) return jsonResponse(localModels);
    if (u.endsWith("/llms/remote")) return jsonResponse([]);
    return jsonResponse([]);
  };

const deleteCalls = () =>
  tracedFetchMock.mock.calls.filter(([, opts]) => opts?.method === "DELETE");

const renderAndOpenDialog = async () => {
  render(<LandingPage />);
  await screen.findByText("base-model");
  fireEvent.click(screen.getByTitle("Delete model"));
};

beforeEach(() => {
  tracedFetchMock.mockClear();
});
afterEach(() => {
  cleanup();
});

describe("LandingPage guarded base delete (#225)", () => {
  it("lists dependents in the dialog and deletes with ?orphan_dependents=true", async () => {
    tracedFetchMock.mockImplementation(makeRouteFetch({ dependentsResponse: dependents }));
    await renderAndOpenDialog();

    // The dialog spells out the consequences before anything is deleted.
    expect(await screen.findByText("1 assistant")).toBeTruthy();
    expect(screen.getByText(/kb-helper/)).toBeTruthy();
    expect(screen.getByText("3 conversations")).toBeTruthy();
    expect(screen.getByText(/Deleting it frees 4\.2 GB/)).toBeTruthy();
    expect(
      screen.getByText(
        "Assistants will remain and must be re-bound to another model; conversations are kept."
      )
    ).toBeTruthy();
    expect(deleteCalls()).toHaveLength(0);

    fireEvent.click(screen.getByText("Delete anyway"));

    await waitFor(() => expect(deleteCalls()).toHaveLength(1));
    expect(String(deleteCalls()[0][0])).toContain("/llms/5?orphan_dependents=true");
  });

  it("keeps the classic dialog and the plain DELETE when there are no dependents", async () => {
    tracedFetchMock.mockImplementation(
      makeRouteFetch({
        dependentsResponse: {
          assistants: [],
          own_conversation_count: 0,
          total_conversation_count: 0,
        },
      })
    );
    await renderAndOpenDialog();

    expect(await screen.findByText(/Are you sure you want to delete the model/)).toBeTruthy();
    expect(screen.queryByText("Delete anyway")).toBeNull();

    fireEvent.click(screen.getByText("Delete"));

    await waitFor(() => expect(deleteCalls()).toHaveLength(1));
    const url = String(deleteCalls()[0][0]);
    expect(url.endsWith("/llms/5")).toBe(true);
    expect(url).not.toContain("orphan_dependents");
  });

  it("falls back to the 409 payload when the pre-check fails (safety net)", async () => {
    tracedFetchMock.mockImplementation(
      makeRouteFetch({
        dependentsResponse: new Error("pre-check down"),
        deleteResponses: [
          {
            ok: false,
            status: 409,
            json: async () => ({ error: { detail: dependents } }),
          },
        ],
      })
    );
    await renderAndOpenDialog();

    // Pre-check failed -> plain dialog, plain DELETE.
    expect(await screen.findByText(/Are you sure you want to delete the model/)).toBeTruthy();
    fireEvent.click(screen.getByText("Delete"));
    await waitFor(() => expect(deleteCalls()).toHaveLength(1));
    expect(String(deleteCalls()[0][0])).not.toContain("orphan_dependents");

    // The 409 payload reopens the dialog with the dependents listed.
    expect(await screen.findByText("Delete anyway")).toBeTruthy();
    expect(screen.getByText(/kb-helper/)).toBeTruthy();

    fireEvent.click(screen.getByText("Delete anyway"));
    await waitFor(() => expect(deleteCalls()).toHaveLength(2));
    expect(String(deleteCalls()[1][0])).toContain("/llms/5?orphan_dependents=true");
  });
});
