// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";

// #228 sibling contract for models: deleting a model must fire exactly ONE
// DELETE request, and a failed DELETE must surface an error message to the
// user instead of failing silently.

const { tracedFetchMock, openDownloadMock } = vi.hoisted(() => ({
  tracedFetchMock: vi.fn(),
  openDownloadMock: vi.fn(),
}));

vi.mock("../services/api/client", () => ({
  default: { get: vi.fn(async () => []) },
  apiClient: { get: vi.fn(async () => []) },
  tracedFetch: tracedFetchMock,
}));

vi.mock("../contexts/DownloadModalContext", () => ({
  useDownloadModal: () => ({ open: openDownloadMock, completionCount: 0 }),
}));

import ModelCollapsibleSection from "./ModelCollapsibleSection.jsx";

const localModels = [
  { id: 1, name: "gemma-270m" },
  { id: 2, name: "qwen-0.5b" },
];
const remoteModels = [
  { id: 10, name: "llama-3-8b", runnable: true },
  { id: 11, name: "mixtral-8x7b", runnable: false },
];

const listResponse = (models) => ({ ok: true, json: async () => models });

const deleteCalls = () =>
  tracedFetchMock.mock.calls.filter(([, opts]) => opts?.method === "DELETE");

// The component keeps its loading spinner for an extra second after the fetch
// resolves, so waitFor needs a timeout above that floor.
const settle = { timeout: 4000 };

beforeEach(() => {
  tracedFetchMock.mockReset();
  openDownloadMock.mockReset();
});
afterEach(() => {
  cleanup();
});

describe("ModelCollapsibleSection fetch & render", () => {
  it("fetches /llms/local for Local Models and renders the rows after loading", async () => {
    tracedFetchMock.mockImplementation(async () => listResponse(localModels));
    render(<ModelCollapsibleSection kind="local" />);

    expect(screen.getByText("Loading models...")).toBeDefined();
    await waitFor(() => expect(screen.getByText("gemma-270m")).toBeDefined(), settle);
    expect(screen.getByText("qwen-0.5b")).toBeDefined();
    expect(String(tracedFetchMock.mock.calls[0][0])).toContain("/llms/local");
  });

  it("fetches /llms/remote for Remote Models and marks non-runnable rows unavailable", async () => {
    tracedFetchMock.mockImplementation(async () => listResponse(remoteModels));
    render(<ModelCollapsibleSection kind="remote" />);

    await waitFor(() => expect(screen.getByText("llama-3-8b")).toBeDefined(), settle);
    expect(String(tracedFetchMock.mock.calls[0][0])).toContain("/llms/remote");
    expect(screen.getByText("unavailable")).toBeDefined();
    expect(screen.getByTitle("Unavailable on your hardware")).toBeDefined();
  });

  it("shows the empty-state copy per section when the list is empty", async () => {
    tracedFetchMock.mockImplementation(async () => listResponse([]));
    render(<ModelCollapsibleSection kind="local" />);
    await waitFor(() => expect(screen.getByText("No models here...")).toBeDefined(), settle);
    cleanup();

    tracedFetchMock.mockClear();
    tracedFetchMock.mockImplementation(async () => listResponse([]));
    render(<ModelCollapsibleSection kind="remote" />);
    await waitFor(() => expect(screen.getByText("No models available...")).toBeDefined(), settle);
  });

  it("surfaces an error message when the initial fetch rejects", async () => {
    tracedFetchMock.mockImplementation(async () => {
      throw new Error("network down");
    });
    render(<ModelCollapsibleSection kind="local" />);

    await waitFor(
      () => expect(screen.getByText(/Failed to fetch available models/)).toBeDefined(),
      settle
    );
    // Closing the error modal clears the message.
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByText(/Failed to fetch available models/)).toBeNull();
  });

  it("re-fetches local models when the refresh icon is clicked", async () => {
    tracedFetchMock.mockImplementation(async () => listResponse(localModels));
    const { container } = render(<ModelCollapsibleSection kind="local" />);
    await waitFor(() => expect(screen.getByText("gemma-270m")).toBeDefined(), settle);

    tracedFetchMock.mockClear();
    fireEvent.click(container.querySelector("svg.lucide-refresh-ccw"));
    await waitFor(() => expect(tracedFetchMock).toHaveBeenCalledTimes(1), settle);
    expect(String(tracedFetchMock.mock.calls[0][0])).toContain("/llms/local");
  });

  it("shows an error when the refresh returns a non-ok response", async () => {
    tracedFetchMock.mockImplementationOnce(async () => listResponse(localModels));
    const { container } = render(<ModelCollapsibleSection kind="local" />);
    await waitFor(() => expect(screen.getByText("gemma-270m")).toBeDefined(), settle);

    tracedFetchMock.mockImplementation(async () => ({ ok: false, status: 500 }));
    fireEvent.click(container.querySelector("svg.lucide-refresh-ccw"));
    await waitFor(
      () => expect(screen.getByText(/Failed to fetch local models/)).toBeDefined(),
      settle
    );
  });

  it("collapses and expands the section when the header is clicked", async () => {
    tracedFetchMock.mockImplementation(async () => listResponse(localModels));
    const { container } = render(<ModelCollapsibleSection kind="local" />);
    await waitFor(() => expect(screen.getByText("gemma-270m")).toBeDefined(), settle);

    const contentGrid = () => container.querySelector("div.grid");
    expect(contentGrid().className).toContain("grid-rows-[1fr]");
    fireEvent.click(screen.getByText("Local Models"));
    expect(contentGrid().className).toContain("grid-rows-[0fr]");
    fireEvent.click(screen.getByText("Local Models"));
    expect(contentGrid().className).toContain("grid-rows-[1fr]");
  });
});

describe("ModelCollapsibleSection search", () => {
  it("filters remote models by the search term and shows a not-found state", async () => {
    tracedFetchMock.mockImplementation(async () => listResponse(remoteModels));
    render(<ModelCollapsibleSection kind="remote" hasSearch />);
    await waitFor(() => expect(screen.getByText("llama-3-8b")).toBeDefined(), settle);

    const input = screen.getByPlaceholderText("Looking for a model?");
    fireEvent.change(input, { target: { value: "LLAMA" } });
    expect(screen.getByText("llama-3-8b")).toBeDefined();
    expect(screen.queryByText("mixtral-8x7b")).toBeNull();

    fireEvent.change(input, { target: { value: "no-such-model" } });
    expect(screen.getByText("No models found...")).toBeDefined();
  });
});

describe("ModelCollapsibleSection download flow", () => {
  it("opens the download modal for a runnable remote model, not for a disabled one", async () => {
    tracedFetchMock.mockImplementation(async () => listResponse(remoteModels));
    render(<ModelCollapsibleSection kind="remote" />);
    await waitFor(() => expect(screen.getByText("llama-3-8b")).toBeDefined(), settle);

    fireEvent.click(screen.getByText("mixtral-8x7b"));
    expect(openDownloadMock).not.toHaveBeenCalled();

    fireEvent.click(screen.getByText("llama-3-8b"));
    expect(openDownloadMock).toHaveBeenCalledTimes(1);
    expect(openDownloadMock.mock.calls[0][0]).toEqual(remoteModels[0]);
  });

  it("refreshes local models on download completion and surfaces download errors", async () => {
    tracedFetchMock.mockImplementation(async () => listResponse(remoteModels));
    const onLocalModelRefresh = vi.fn();
    render(<ModelCollapsibleSection kind="remote" onLocalModelRefresh={onLocalModelRefresh} />);
    await waitFor(() => expect(screen.getByText("llama-3-8b")).toBeDefined(), settle);

    fireEvent.click(screen.getByText("llama-3-8b"));
    const { onComplete } = openDownloadMock.mock.calls[0][1];

    onComplete();
    expect(onLocalModelRefresh).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByText("llama-3-8b"));
    const secondOpts = openDownloadMock.mock.calls[1][1];
    secondOpts.onError(null);
    await waitFor(() => expect(screen.getByText("Download failed.")).toBeDefined(), settle);
  });
});

describe("ModelCollapsibleSection delete (#228)", () => {
  it("fires exactly one DELETE on confirm, shows success, and refreshes the parent", async () => {
    tracedFetchMock.mockImplementation(async (url, opts) => {
      if (opts?.method === "DELETE") {
        return { ok: true };
      }
      return listResponse(localModels);
    });
    const onLocalModelRefresh = vi.fn();
    render(<ModelCollapsibleSection kind="local" onLocalModelRefresh={onLocalModelRefresh} />);
    await waitFor(() => expect(screen.getByText("gemma-270m")).toBeDefined(), settle);

    fireEvent.click(screen.getAllByTitle("Delete model")[0]);
    // The dialog opens once the dependents pre-check resolves (#317).
    fireEvent.click(await screen.findByRole("button", { name: "Delete" }, settle));

    await waitFor(
      () =>
        expect(screen.getByText("Model gemma-270m has been successfully deleted.")).toBeDefined(),
      settle
    );
    expect(deleteCalls()).toHaveLength(1);
    expect(String(deleteCalls()[0][0])).toContain("/llms/1");
    await waitFor(() => expect(onLocalModelRefresh).toHaveBeenCalledTimes(1), settle);
  });

  it("cancelling the confirm dialog fires no DELETE", async () => {
    tracedFetchMock.mockImplementation(async () => listResponse(localModels));
    render(<ModelCollapsibleSection kind="local" />);
    await waitFor(() => expect(screen.getByText("gemma-270m")).toBeDefined(), settle);

    fireEvent.click(screen.getAllByTitle("Delete model")[0]);
    fireEvent.click(await screen.findByRole("button", { name: "Cancel" }, settle));

    expect(deleteCalls()).toHaveLength(0);
    // AnimatePresence keeps the dialog mounted during its exit animation.
    await waitFor(() => expect(screen.queryByText("Delete Model")).toBeNull(), settle);
  });

  it("surfaces an errorMessage when the DELETE fails", async () => {
    tracedFetchMock.mockImplementation(async (url, opts) => {
      if (opts?.method === "DELETE") {
        return { ok: false, status: 500 };
      }
      return listResponse(localModels);
    });
    render(<ModelCollapsibleSection kind="local" />);
    await waitFor(() => expect(screen.getByText("gemma-270m")).toBeDefined(), settle);

    fireEvent.click(screen.getAllByTitle("Delete model")[0]);
    fireEvent.click(await screen.findByRole("button", { name: "Delete" }, settle));

    await waitFor(
      () => expect(screen.getByText(/Failed to delete the model/)).toBeDefined(),
      settle
    );
    expect(deleteCalls()).toHaveLength(1);
    expect(screen.queryByText(/successfully deleted/)).toBeNull();
  });
});
