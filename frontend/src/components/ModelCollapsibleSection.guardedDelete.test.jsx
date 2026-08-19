// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";

// Guarded base delete from the left-rail Local Models list (#317): during QA
// the rail sent a bare DELETE, the backend answered 409 (base with dependent
// KB assistants) and the guard flow was unreachable — the model silently
// stayed in the list. The rail must run the same guarded flow as the
// installed cards: dependents pre-check, guard dialog with "Delete anyway"
// retrying with ?orphan_dependents=true, and the 409 payload as safety net.

const { tracedFetchMock } = vi.hoisted(() => ({
  tracedFetchMock: vi.fn(),
}));

vi.mock("../services/api/client", () => ({
  default: { get: vi.fn(async () => []) },
  apiClient: { get: vi.fn(async () => []) },
  tracedFetch: tracedFetchMock,
}));

vi.mock("../contexts/DownloadModalContext", () => ({
  useDownloadModal: () => ({ open: vi.fn(), completionCount: 0 }),
}));

import ModelCollapsibleSection from "./ModelCollapsibleSection.jsx";

const base = { id: 319, name: "Qwen3 4B", link: "/models/319" };
const assistant = {
  id: 320,
  name: "Nimbus Assistant",
  link: "/models/319",
  kb_id: 1,
  is_attached_to_kb: true,
};

const dependents = {
  assistants: [{ id: 320, name: "Nimbus Assistant", kb_id: 1, conversation_count: 1 }],
  own_conversation_count: 1,
  total_conversation_count: 2,
};

const jsonResponse = (payload) => ({ ok: true, status: 200, json: async () => payload });

const deleteCalls = () =>
  tracedFetchMock.mock.calls.filter(([, opts]) => opts?.method === "DELETE");
const dependentsCalls = () =>
  tracedFetchMock.mock.calls.filter(([u]) => String(u).includes("/dependents"));

// The component keeps its loading spinner for an extra second after the fetch
// resolves, so async lookups need a timeout above that floor.
const settle = { timeout: 4000 };

const renderRail = async (rows) => {
  render(<ModelCollapsibleSection title="Local Models" />);
  await waitFor(() => expect(screen.getByText(rows[0].name)).toBeDefined(), settle);
};

beforeEach(() => {
  tracedFetchMock.mockReset();
});
afterEach(() => {
  cleanup();
});

describe("ModelCollapsibleSection guarded base delete (#317)", () => {
  it("pre-checks dependents and deletes with ?orphan_dependents=true from the guard dialog", async () => {
    tracedFetchMock.mockImplementation(async (url, opts = {}) => {
      const u = String(url);
      if (opts.method === "DELETE") return jsonResponse({});
      if (u.endsWith("/llms/319/dependents")) return jsonResponse(dependents);
      if (u.endsWith("/llms/local")) return jsonResponse([base]);
      return jsonResponse([]);
    });
    await renderRail([base]);

    fireEvent.click(screen.getByTitle("Delete model"));

    // The guard dialog spells out the consequences before anything is deleted.
    expect(await screen.findByText("1 assistant")).toBeTruthy();
    expect(screen.getByText(/Nimbus Assistant/)).toBeTruthy();
    expect(screen.getByText("2 conversations")).toBeTruthy();
    expect(deleteCalls()).toHaveLength(0);

    fireEvent.click(screen.getByText("Delete anyway"));

    await waitFor(() => expect(deleteCalls()).toHaveLength(1));
    expect(String(deleteCalls()[0][0])).toContain("/llms/319?orphan_dependents=true");
  });

  it("reopens the dialog with the 409 payload when the pre-check missed the dependents", async () => {
    const deleteResponses = [
      {
        ok: false,
        status: 409,
        json: async () => ({
          success: false,
          error: { type: "STATE_CONFLICT", message: "guarded", detail: dependents },
        }),
      },
      jsonResponse({}),
    ];
    tracedFetchMock.mockImplementation(async (url, opts = {}) => {
      const u = String(url);
      if (opts.method === "DELETE") return deleteResponses.shift();
      if (u.endsWith("/llms/319/dependents")) throw new Error("pre-check down");
      if (u.endsWith("/llms/local")) return jsonResponse([base]);
      return jsonResponse([]);
    });
    await renderRail([base]);

    fireEvent.click(screen.getByTitle("Delete model"));
    expect(await screen.findByText(/Are you sure you want to delete the model/)).toBeTruthy();
    fireEvent.click(screen.getByText("Delete"));

    // The 409 payload reopens the dialog as the guard — never a silent no-op.
    expect(await screen.findByText("Delete anyway")).toBeTruthy();
    expect(screen.getByText(/Nimbus Assistant/)).toBeTruthy();

    fireEvent.click(screen.getByText("Delete anyway"));
    await waitFor(() => expect(deleteCalls()).toHaveLength(2));
    expect(String(deleteCalls()[1][0])).toContain("/llms/319?orphan_dependents=true");
  });

  it("gives KB assistants the plain confirm without any dependents pre-check", async () => {
    tracedFetchMock.mockImplementation(async (url, opts = {}) => {
      const u = String(url);
      if (opts.method === "DELETE") return jsonResponse({});
      if (u.endsWith("/llms/local")) return jsonResponse([base, assistant]);
      return jsonResponse([]);
    });
    await renderRail([base, assistant]);

    const buttons = screen.getAllByTitle("Delete model");
    fireEvent.click(buttons[1]); // the assistant row

    expect(await screen.findByText(/Are you sure you want to delete the model/)).toBeTruthy();
    expect(screen.queryByText("Delete anyway")).toBeNull();
    expect(dependentsCalls()).toHaveLength(0);

    fireEvent.click(screen.getByText("Delete"));
    await waitFor(() => expect(deleteCalls()).toHaveLength(1));
    const url = String(deleteCalls()[0][0]);
    expect(url.endsWith("/llms/320")).toBe(true);
    expect(url).not.toContain("orphan_dependents");
  });

  it("surfaces an unexpected 409 without a usable payload as an error, never silence", async () => {
    tracedFetchMock.mockImplementation(async (url, opts = {}) => {
      const u = String(url);
      if (opts.method === "DELETE")
        return { ok: false, status: 409, json: async () => ({ detail: "downloading" }) };
      if (u.endsWith("/llms/319/dependents"))
        return jsonResponse({
          assistants: [],
          own_conversation_count: 0,
          total_conversation_count: 0,
        });
      if (u.endsWith("/llms/local")) return jsonResponse([base]);
      return jsonResponse([]);
    });
    await renderRail([base]);

    fireEvent.click(screen.getByTitle("Delete model"));
    expect(await screen.findByText(/Are you sure you want to delete the model/)).toBeTruthy();
    fireEvent.click(screen.getByText("Delete"));

    expect(await screen.findByText(/Failed to delete the model/)).toBeTruthy();
  });
});
