// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

vi.mock("../services/api/client", () => {
  const apiClient = { get: vi.fn() };
  return { apiClient, default: apiClient };
});
vi.mock("../utils/logger", () => ({
  createLogger: () => ({ error: vi.fn(), warn: vi.fn(), info: vi.fn(), debug: vi.fn() }),
}));
// Stub the card so result ordering and forwarded props stay assertable without
// pulling the full card UI into this suite.
const seenCardProps = vi.hoisted(() => []);
vi.mock("./ExploreModelCard", () => ({
  default: (props) => {
    seenCardProps.push(props);
    return <div data-testid="model-card">{props.model.name}</div>;
  },
}));

import apiClient from "../services/api/client";
import HuggingFaceSearchPanel from "./HuggingFaceSearchPanel";

const RANGE = { min: 4, max: 8 };

const hit = (overrides = {}) => ({
  name: "some-model",
  link: `hf/${overrides.name || "some-model"}`,
  category: "text",
  param_size: 7,
  quantized: true,
  gated: false,
  downloads: 100,
  likes: 10,
  pipeline_tag: "text-generation",
  ...overrides,
});

function renderPanel(props = {}) {
  return render(<HuggingFaceSearchPanel range={RANGE} {...props} />);
}

async function search(term) {
  const input = screen.getByPlaceholderText(/Try "qwen coder"/);
  fireEvent.change(input, { target: { value: term } });
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  await waitFor(() =>
    expect(screen.queryByText(/searching hugging face for/)).not.toBeInTheDocument()
  );
}

let onLineSpy;

beforeEach(() => {
  vi.clearAllMocks();
  onLineSpy = vi.spyOn(window.navigator, "onLine", "get").mockReturnValue(true);
});

afterEach(() => {
  cleanup();
  onLineSpy.mockRestore();
});

describe("HuggingFaceSearchPanel search flow", () => {
  it("renders idle with suggestion chips and no results section", () => {
    renderPanel();
    ["coding", "reasoning", "vision", "tiny", "uncensored", "multilingual"].forEach((s) => {
      expect(screen.getByRole("button", { name: s })).toBeInTheDocument();
    });
    expect(screen.queryByText(/results for/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Search" })).toBeDisabled();
  });

  it("does not search a whitespace-only query submitted via Enter", () => {
    renderPanel();
    const input = screen.getByPlaceholderText(/Try "qwen coder"/);
    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(apiClient.get).not.toHaveBeenCalled();
  });

  it("hits the HF search endpoint with the URL-encoded query on Enter", async () => {
    apiClient.get.mockResolvedValueOnce([]);
    renderPanel();
    const input = screen.getByPlaceholderText(/Try "qwen coder"/);
    fireEvent.change(input, { target: { value: "qwen coder" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() =>
      expect(apiClient.get).toHaveBeenCalledWith("/llms/search/huggingface?q=qwen%20coder")
    );
  });

  it("shows a live loading indicator while the request is in flight", async () => {
    let resolveRequest;
    apiClient.get.mockReturnValueOnce(new Promise((resolve) => (resolveRequest = resolve)));
    renderPanel();
    const input = screen.getByPlaceholderText(/Try "qwen coder"/);
    fireEvent.change(input, { target: { value: "qwen" } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(screen.getByText(/searching hugging face for/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Searching…" })).toBeDisabled();

    resolveRequest([]);
    await waitFor(() =>
      expect(screen.queryByText(/searching hugging face for/)).not.toBeInTheDocument()
    );
  });

  it("a suggestion chip searches its term and fills the input", async () => {
    apiClient.get.mockResolvedValueOnce([]);
    renderPanel();
    fireEvent.click(screen.getByRole("button", { name: "coding" }));
    await waitFor(() =>
      expect(apiClient.get).toHaveBeenCalledWith("/llms/search/huggingface?q=coding")
    );
    expect(screen.getByPlaceholderText(/Try "qwen coder"/)).toHaveValue("coding");
  });
});

describe("HuggingFaceSearchPanel error vs zero-results", () => {
  it("distinguishes zero results from an error: empty payload gets guidance, not an error", async () => {
    apiClient.get.mockResolvedValueOnce([]);
    renderPanel();
    await search("unobtainium");
    expect(screen.getByText(/Nothing runnable matched “unobtainium”/)).toBeInTheDocument();
    expect(screen.queryByText(/couldn’t reach Hugging Face/)).not.toBeInTheDocument();
  });

  it("labels a failed request as a reachability problem, not offline and not zero results", async () => {
    apiClient.get.mockRejectedValueOnce(new Error("HTTP 502"));
    renderPanel();
    await search("qwen");
    expect(
      screen.getByText("Search couldn’t reach Hugging Face. Check your connection and try again.")
    ).toBeInTheDocument();
    expect(screen.queryByText(/Nothing runnable matched/)).not.toBeInTheDocument();
    expect(screen.queryByText(/No internet connection/)).not.toBeInTheDocument();
  });

  it("reports genuine offline without firing a request", async () => {
    onLineSpy.mockReturnValue(false);
    renderPanel();
    const input = screen.getByPlaceholderText(/Try "qwen coder"/);
    fireEvent.change(input, { target: { value: "qwen" } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByText("No internet connection for the moment.")).toBeInTheDocument();
    expect(apiClient.get).not.toHaveBeenCalled();
  });
});

describe("HuggingFaceSearchPanel handoff from the catalog search (#380)", () => {
  it("runs the handed-over term as a search and fills the box with it", async () => {
    apiClient.get.mockResolvedValueOnce([]);
    renderPanel({ handoff: { term: "unobtainium", seq: 1 } });
    await waitFor(() =>
      expect(apiClient.get).toHaveBeenCalledWith("/llms/search/huggingface?q=unobtainium")
    );
    expect(screen.getByPlaceholderText(/Try "qwen coder"/)).toHaveValue("unobtainium");
  });

  it("searches again when the same term is handed over a second time", async () => {
    apiClient.get.mockResolvedValueOnce([]).mockResolvedValueOnce([]);
    const { rerender } = renderPanel({ handoff: { term: "qwen", seq: 1 } });
    await waitFor(() => expect(apiClient.get).toHaveBeenCalledTimes(1));

    rerender(<HuggingFaceSearchPanel range={RANGE} handoff={{ term: "qwen", seq: 2 }} />);
    await waitFor(() => expect(apiClient.get).toHaveBeenCalledTimes(2));
  });

  it("does nothing without a handoff", () => {
    renderPanel();
    expect(apiClient.get).not.toHaveBeenCalled();
  });
});

describe("HuggingFaceSearchPanel results and sorting", () => {
  const FIXTURES = [
    // Input order is deliberately the reverse of the expected fit ranking.
    hit({ name: "big-base", param_size: 30, downloads: 5, likes: 1 }),
    hit({ name: "tiny-base", param_size: 0.5, downloads: 900, likes: 2 }),
    hit({ name: "llama-3b-chat", param_size: 3, downloads: 50, likes: 99 }),
    hit({ name: "qwen-7b-instruct", param_size: 7, downloads: 200, likes: 40 }),
  ];

  const renderedNames = () => screen.getAllByTestId("model-card").map((el) => el.textContent);

  it("ranks results by hardware fit: chat models first, then ideal → good → heavy", async () => {
    apiClient.get.mockResolvedValueOnce(FIXTURES);
    renderPanel();
    await search("qwen");
    expect(screen.getByText(/4 results for “qwen”/)).toBeInTheDocument();
    expect(renderedNames()).toEqual(["qwen-7b-instruct", "llama-3b-chat", "tiny-base", "big-base"]);
  });

  it("re-sorts by downloads, likes, smallest and largest via the sort select", async () => {
    apiClient.get.mockResolvedValueOnce(FIXTURES);
    renderPanel();
    await search("qwen");

    const select = screen.getByRole("combobox");
    fireEvent.change(select, { target: { value: "downloads" } });
    expect(renderedNames()).toEqual(["tiny-base", "qwen-7b-instruct", "llama-3b-chat", "big-base"]);

    fireEvent.change(select, { target: { value: "likes" } });
    expect(renderedNames()).toEqual(["llama-3b-chat", "qwen-7b-instruct", "tiny-base", "big-base"]);

    fireEvent.change(select, { target: { value: "smallest" } });
    expect(renderedNames()).toEqual(["tiny-base", "llama-3b-chat", "qwen-7b-instruct", "big-base"]);

    fireEvent.change(select, { target: { value: "largest" } });
    expect(renderedNames()).toEqual(["big-base", "qwen-7b-instruct", "llama-3b-chat", "tiny-base"]);
  });

  it("collapse hides the cards, show restores them, clear resets the panel", async () => {
    apiClient.get.mockResolvedValueOnce(FIXTURES);
    renderPanel();
    await search("qwen");

    fireEvent.click(screen.getByRole("button", { name: "Collapse" }));
    expect(screen.queryAllByTestId("model-card")).toHaveLength(0);

    fireEvent.click(screen.getByRole("button", { name: "Show" }));
    expect(screen.getAllByTestId("model-card")).toHaveLength(4);

    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(screen.queryByText(/results for/)).not.toBeInTheDocument();
    expect(screen.queryAllByTestId("model-card")).toHaveLength(0);
  });

  it("maps search hits to details-modal fields, forwarding range and callbacks", async () => {
    seenCardProps.length = 0;
    const onDownload = vi.fn();
    const onInfo = vi.fn();
    apiClient.get.mockResolvedValueOnce([
      hit({
        name: "full",
        link: "hf/full",
        param_size: 7,
        downloads: 1234,
        likes: 56,
        pipeline_tag: "text-generation",
        gated: true,
      }),
      hit({
        name: "bare",
        link: "hf/bare",
        param_size: null,
        downloads: 0,
        likes: 0,
        pipeline_tag: null,
      }),
    ]);
    renderPanel({ onDownload, onInfo });
    await search("models");

    expect(screen.getByText(/2 results for “models”/)).toBeInTheDocument();
    const byName = Object.fromEntries(seenCardProps.map((p) => [p.model.name, p]));
    expect(byName.full.model).toMatchObject({
      link: "hf/full",
      runnable: true,
      gated: true,
      parameters: "7B",
      downloads: "1234",
      likes: "56",
      pipeline: "text-generation",
    });
    expect(byName.bare.model).toMatchObject({
      parameters: "Unknown",
      downloads: "Unknown",
      likes: "Unknown",
      pipeline: "Unknown",
    });
    expect(byName.full.range).toEqual(RANGE);
    expect(byName.full.onDownload).toBe(onDownload);
    expect(byName.full.onInfo).toBe(onInfo);
  });
});
