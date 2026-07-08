// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor, within } from "@testing-library/react";

// Orphaned KB assistants (#225/#208): a card with weights_available === false
// shows "Model weights missing", blocks Chat, and offers a Re-bind picker of
// installed base models (local, non-assistant, weights on disk) that POSTs
// /llms/{assistant_id}/rebind and refreshes. Healthy assistant cards say
// "Uses the weights of <base>" (never a Size line — they own no disk space);
// plain installed model cards are unchanged.

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

// Stub the heavy children; ModelCard (the card under test) stays REAL.
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
vi.mock("../components/modals/DeleteModelModal", () => ({ default: () => null }));
vi.mock("../components/modals/MessageModal", () => ({ default: () => null }));
vi.mock("../components/modals/WelcomeModal", () => ({ default: () => null }));
vi.mock("../assets/images/logos/logoerudifinal.png", () => ({ default: "logo.png" }));

import LandingPage from "./LandingPage.jsx";

// One healthy base, one orphaned assistant (base deleted), one healthy
// assistant bound to the base (same link).
const localModels = [
  {
    id: 1,
    name: "qwen-base",
    link: "/models/1",
    model_metadata: "size: 2.1 GB",
    weights_available: true,
    kb_id: null,
  },
  {
    id: 2,
    name: "docs-assistant",
    link: "/models/gone",
    model_metadata: "",
    weights_available: false,
    kb_id: 7,
  },
  {
    id: 3,
    name: "notes-assistant",
    link: "/models/1",
    model_metadata: "",
    weights_available: true,
    kb_id: 8,
  },
];

const jsonResponse = (payload) => ({ ok: true, json: async () => payload });

const routeFetch = async (url, opts = {}) => {
  const u = String(url);
  if (opts.method === "POST" && u.includes("/rebind")) return jsonResponse({});
  if (u.endsWith("/llms/local")) return jsonResponse(localModels);
  if (u.endsWith("/llms/remote")) return jsonResponse([]);
  return jsonResponse([]);
};

const localListCalls = () =>
  tracedFetchMock.mock.calls.filter(
    ([url, opts]) => String(url).endsWith("/llms/local") && !opts?.method
  );

beforeEach(() => {
  tracedFetchMock.mockClear();
  tracedFetchMock.mockImplementation(routeFetch);
});
afterEach(() => {
  cleanup();
});

describe("LandingPage orphaned assistant cards (#225/#208)", () => {
  it("marks the orphaned assistant, blocks its Chat and keeps other cards unchanged", async () => {
    render(<LandingPage />);
    await screen.findByText("docs-assistant");

    // Orphan: weights-missing state, Chat blocked, Re-bind offered.
    expect(screen.getByText("Model weights missing")).toBeTruthy();
    const blockedChat = screen.getByTitle("Model weights missing - re-bind to chat");
    expect(blockedChat.disabled).toBe(true);
    expect(screen.getAllByText("Re-bind")).toHaveLength(1);

    // Healthy assistant: weights wording (#208), no Size line, Chat enabled.
    expect(screen.getByText("Uses the weights of qwen-base")).toBeTruthy();

    // Plain installed model: unchanged card with its Size line.
    expect(screen.getByText("Size: 2.1 GB")).toBeTruthy();
    const enabledChats = screen.getAllByTitle("Chat");
    expect(enabledChats).toHaveLength(2);
    enabledChats.forEach((btn) => expect(btn.disabled).toBe(false));
  });

  it("re-binds through the picker: POST /llms/{id}/rebind, then refreshes", async () => {
    render(<LandingPage />);
    await screen.findByText("docs-assistant");
    const before = localListCalls().length;

    fireEvent.click(screen.getByTitle("Re-bind to another installed model"));

    // The picker offers only installed base models with weights on disk —
    // never assistants (healthy or orphaned).
    const dropdown = screen.getByTitle("Re-bind to another installed model").nextElementSibling;
    expect(within(dropdown).getByText("qwen-base")).toBeTruthy();
    expect(within(dropdown).queryByText("notes-assistant")).toBeNull();
    expect(within(dropdown).queryByText("docs-assistant")).toBeNull();

    fireEvent.click(within(dropdown).getByText("qwen-base"));

    const posts = () => tracedFetchMock.mock.calls.filter(([, opts]) => opts?.method === "POST");
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(String(posts()[0][0])).toContain("/llms/2/rebind");
    expect(JSON.parse(posts()[0][1].body)).toEqual({ new_base_llm_id: 1 });

    // The installed list is re-fetched so the card leaves its orphan state.
    await waitFor(() => expect(localListCalls().length).toBeGreaterThan(before));
  });
});
