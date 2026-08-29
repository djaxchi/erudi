// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

// A KB assistant whose base model was deleted survives with
// `weights_available === false` (#376). Its Installed card already disables
// Chat and offers Re-bind; the Chat page's own picker must agree: the entry is
// listed but disabled with a hint, it is never auto-selected (neither as the
// default nor through `?model=`), and with nothing selectable the composer
// stays disabled instead of creating a conversation that can only fail.

const { tracedFetchMock } = vi.hoisted(() => ({ tracedFetchMock: vi.fn() }));

vi.mock("../services/api/client", () => ({
  default: { get: vi.fn() },
  apiClient: { get: vi.fn() },
  tracedFetch: tracedFetchMock,
}));

vi.mock("../contexts/DownloadModalContext", () => ({
  useDownloadModal: () => ({ open: vi.fn(), completionCount: 0 }),
}));

vi.mock("../components/Sidebar", () => ({ default: () => null }));
vi.mock("../components/ChatCollapsibleSection", () => ({ default: () => null }));
vi.mock("../components/GradientBox", () => ({ default: ({ children }) => <div>{children}</div> }));
// The composer stub exposes the `disabled` prop the page passes it.
vi.mock("../components/QuestionInput", () => ({
  default: ({ disabled }) => <div data-testid="composer" data-disabled={String(disabled)} />,
}));
vi.mock("../components/modals/CustomizePromptModal", () => ({ default: () => null }));
vi.mock("../components/modals/ErrorModal", () => ({ default: () => null }));

import apiClient from "../services/api/client";
import ChatPage from "./ChatPage.jsx";

const ORPHAN = {
  id: 9,
  name: "Nimbus Assistant",
  kb_id: 3,
  is_attached_to_kb: true,
  weights_available: false,
};
const HEALTHY = { id: 42, name: "Beta Model", weights_available: true };

const renderAt = (search = "") =>
  render(
    <MemoryRouter initialEntries={[`/erudi/chat${search}`]}>
      <ChatPage />
    </MemoryRouter>
  );

const useModels = (models) => {
  apiClient.get.mockImplementation(async (path) => (path === "/llms/local" ? models : []));
};

const openPicker = async () => {
  const trigger = await screen.findByText("Chat with");
  fireEvent.click(trigger.nextSibling);
};

beforeEach(() => {
  apiClient.get.mockReset();
});
afterEach(() => {
  cleanup();
});

describe("ChatPage picker and a weights-missing assistant (#376)", () => {
  it("lists the assistant disabled with a hint and does not select it on click", async () => {
    useModels([ORPHAN, HEALTHY]);
    renderAt();
    await screen.findByTitle("Beta Model");

    await openPicker();
    const entry = screen.getByTestId("model-option-9");
    expect(entry.getAttribute("aria-disabled")).toBe("true");
    expect(entry.textContent).toMatch(/Weights missing/);
    expect(entry.textContent).toMatch(/Models page/);

    fireEvent.click(entry);
    // Still the healthy model, and the picker did not treat it as a pick.
    expect(screen.getByTitle("Beta Model").textContent).toBe("Beta Model");
  });

  it("skips the orphan and preselects the next selectable model", async () => {
    useModels([ORPHAN, HEALTHY]);
    renderAt();

    const selected = await screen.findByTitle("Beta Model");
    expect(selected.textContent).toBe("Beta Model");
    expect(screen.getByTestId("composer").getAttribute("data-disabled")).toBe("false");
  });

  it("leaves nothing selected and the composer disabled when the orphan is the only model", async () => {
    useModels([ORPHAN]);
    renderAt();

    await openPicker();
    expect(screen.getByTestId("model-option-9").getAttribute("aria-disabled")).toBe("true");
    expect(screen.getByText("Select model...")).toBeTruthy();
    expect(screen.queryByTitle("Nimbus Assistant")).toBeNull();
    expect(screen.getByTestId("composer").getAttribute("data-disabled")).toBe("true");
  });

  it("ignores a ?model= deep link that points at the orphan", async () => {
    useModels([ORPHAN, HEALTHY]);
    renderAt("?model=9");

    const selected = await screen.findByTitle("Beta Model");
    expect(selected.textContent).toBe("Beta Model");
    await waitFor(() => expect(screen.queryByTitle("Nimbus Assistant")).toBeNull());
  });
});
