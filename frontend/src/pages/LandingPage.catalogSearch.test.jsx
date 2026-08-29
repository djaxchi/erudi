// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor, within } from "@testing-library/react";

// Offline search over the bundled catalog (#380): typing in the catalog box
// filters the curated rows client-side (name, repo id, family, category),
// AND-ed with the size / fit filters; the result grid replaces the capability
// carousels while a query is active; an empty result offers to hand the query
// to the Hugging Face panel when the machine is online, and says why not when
// it is offline.

const { tracedFetchMock, ctx } = vi.hoisted(() => ({
  tracedFetchMock: vi.fn(),
  ctx: { open: vi.fn(), completionCount: 0 },
}));

vi.mock("../contexts/DownloadModalContext", () => ({ useDownloadModal: () => ctx }));
vi.mock("../services/api/client", () => ({
  default: { get: vi.fn(async () => ({})) },
  apiClient: { get: vi.fn(async () => ({})) },
  tracedFetch: tracedFetchMock,
}));
vi.mock("react-router-dom", () => ({ useNavigate: () => vi.fn() }));
vi.mock("../components/Sidebar", () => ({ default: () => null }));
vi.mock("../components/ConnectionStatus", () => ({ default: () => null }));
vi.mock("../components/MachineReadout", () => ({ default: () => null }));
vi.mock("../components/ModelCollapsibleSection", async () => {
  const { forwardRef } = await import("react");
  const Section = forwardRef(() => null);
  Section.displayName = "ModelCollapsibleSectionMock";
  return { default: Section };
});
vi.mock("../components/ExploreIndex", () => ({ default: () => null }));
vi.mock("../components/modals/WelcomeModal", () => ({ default: () => null }));
vi.mock("../components/LoadingPopup", () => ({ default: () => null }));
vi.mock("../components/modals/ModelInfoModal", () => ({ default: () => null }));
vi.mock("../components/modals/DeleteModelModal", () => ({ default: () => null }));
vi.mock("../components/modals/MessageModal", () => ({ default: () => null }));
vi.mock("../assets/images/logos/logoerudifinal.png", () => ({ default: "logo.png" }));

// The carousels are what the search grid replaces: a marker is enough.
vi.mock("../components/CategorySections", () => ({
  default: () => <div>category-sections</div>,
}));
vi.mock("../components/ExploreModelCard", () => ({
  default: ({ model }) => <div>{`explore:${model.name}`}</div>,
}));
// The Hugging Face panel only needs to show what was handed to it.
vi.mock("../components/HuggingFaceSearchPanel", () => ({
  default: ({ handoff }) => <div>{`hf-handoff:${handoff?.term ?? ""}`}</div>,
}));

import apiClient from "../services/api/client";
import LandingPage from "./LandingPage.jsx";

const remoteModels = [
  {
    id: 1,
    name: "Qwén 2.5 7B Instruct",
    is_base: true,
    param_size: 7,
    type: "qwen",
    category: "general",
    link: "mlx-community/Qwen2.5-7B-Instruct-4bit",
  },
  {
    id: 2,
    name: "Llama 3.1 8B Instruct",
    is_base: true,
    param_size: 8,
    type: "llama",
    category: "general",
    link: "mlx-community/Llama-3.1-8B-Instruct-4bit",
  },
  {
    id: 3,
    name: "Gemma 3 1B",
    is_base: true,
    param_size: 1,
    type: "gemma",
    category: "vision",
    link: "mlx-community/gemma-3-1b-it-4bit",
  },
  {
    id: 4,
    name: "Communo Qwen Tune",
    is_base: false,
    param_size: 70,
    type: "qwen",
    link: "someone/communo-qwen-tune",
  },
];

const hardware = {
  backend_type: "mlx",
  recommended_param_min: 1,
  recommended_param_max: 8,
};

const jsonResponse = (payload) => ({ ok: true, status: 200, json: async () => payload });

let onLineSpy;

beforeEach(() => {
  ctx.open = vi.fn();
  ctx.completionCount = 0;
  tracedFetchMock.mockReset();
  tracedFetchMock.mockImplementation(async (url) => {
    const u = String(url);
    if (u.endsWith("/llms/local")) return jsonResponse([]);
    if (u.endsWith("/llms/remote")) return jsonResponse(remoteModels);
    return jsonResponse({});
  });
  apiClient.get.mockReset();
  apiClient.get.mockImplementation(async (path) => {
    if (path === "/startup/welcome-popup") return { has_already_displayed: true };
    if (path === "/hardware/app_startup") return hardware;
    return {};
  });
  onLineSpy = vi.spyOn(window.navigator, "onLine", "get").mockReturnValue(true);
});
afterEach(() => {
  cleanup();
  onLineSpy.mockRestore();
});

const searchBox = () => screen.getByRole("searchbox", { name: "Search the catalog" });
const results = () => screen.getByTestId("catalog-search-results");

async function renderAndType(query) {
  render(<LandingPage />);
  await screen.findByText("category-sections");
  fireEvent.change(searchBox(), { target: { value: query } });
}

describe("LandingPage catalog search (#380)", () => {
  it("filters the bundled catalog as the user types, accent-insensitively, base rows first", async () => {
    await renderAndType("qwen");

    const grid = await screen.findByTestId("catalog-search-results");
    // The base model whose name starts with the query comes first, then the
    // community fine-tune that only carries the family in its name/type.
    await waitFor(() =>
      expect(
        within(grid)
          .getAllByText(/^explore:/)
          .map((el) => el.textContent)
      ).toEqual(["explore:Qwén 2.5 7B Instruct", "explore:Communo Qwen Tune"])
    );
    expect(screen.getByText("2 catalog matches for “qwen”")).toBeTruthy();
    // The capability carousels step aside while a query is active.
    expect(screen.queryByText("category-sections")).toBeNull();
  });

  it("matches on the Hugging Face repo id and the category label", async () => {
    await renderAndType("mlx-community/gemma");
    await waitFor(() =>
      expect(
        within(results())
          .getAllByText(/^explore:/)
          .map((el) => el.textContent)
      ).toEqual(["explore:Gemma 3 1B"])
    );

    fireEvent.change(searchBox(), { target: { value: "multimodal" } });
    await waitFor(() =>
      expect(
        within(results())
          .getAllByText(/^explore:/)
          .map((el) => el.textContent)
      ).toEqual(["explore:Gemma 3 1B"])
    );
  });

  it("ANDs the query with the size filter", async () => {
    await renderAndType("instruct");
    await waitFor(() => expect(within(results()).getAllByText(/^explore:/)).toHaveLength(2));

    fireEvent.click(screen.getByText("Under 2B"));

    expect(await screen.findByText(/Nothing in the catalog matches “instruct”/)).toBeTruthy();
    // The filters are part of why nothing matched, so the widening hint shows.
    expect(screen.getByText(/Widen the size range/)).toBeTruthy();
    expect(screen.queryByTestId("catalog-search-results")).toBeNull();
  });

  it("offers to search Hugging Face instead when nothing matches and the machine is online", async () => {
    const scrollSpy = vi.fn();
    Element.prototype.scrollIntoView = scrollSpy;
    await renderAndType("unobtainium");

    const handoff = await screen.findByRole("button", {
      name: "Search Hugging Face for “unobtainium” instead",
    });
    expect(screen.getByText("hf-handoff:")).toBeTruthy();

    fireEvent.click(handoff);

    expect(screen.getByText("hf-handoff:unobtainium")).toBeTruthy();
    expect(scrollSpy).toHaveBeenCalledWith({ behavior: "smooth", block: "start" });
    delete Element.prototype.scrollIntoView;
  });

  it("says the Hugging Face fallback is unavailable when offline, without offering it", async () => {
    onLineSpy.mockReturnValue(false);
    await renderAndType("unobtainium");

    expect(await screen.findByText(/Nothing in the catalog matches “unobtainium”/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Search Hugging Face for/ })).toBeNull();
    expect(screen.getByText("No internet connection for the moment.")).toBeTruthy();
  });

  it("Escape clears the query and brings the carousels back", async () => {
    await renderAndType("qwen");
    await screen.findByTestId("catalog-search-results");

    fireEvent.keyDown(searchBox(), { key: "Escape" });

    expect(await screen.findByText("category-sections")).toBeTruthy();
    expect(screen.queryByTestId("catalog-search-results")).toBeNull();
    expect(searchBox().value).toBe("");
  });

  it("hides the community section while a query is active: the results grid already covers those rows", async () => {
    await renderAndType("qwen");
    await screen.findByTestId("catalog-search-results");

    expect(screen.queryByText("Community fine-tunes")).toBeNull();

    fireEvent.keyDown(searchBox(), { key: "Escape" });

    expect(await screen.findByText("Community fine-tunes")).toBeTruthy();
  });
});
