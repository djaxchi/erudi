// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, waitFor, act } from "@testing-library/react";

// Reopening a conversation must hydrate the header model picker with the
// conversation's assigned model (#217). Before the fix, both hydration
// attempts read closure-captured state from the mount render (empty models /
// empty conversations), so the picker stayed on "Select model..." forever
// even though the right model was answering.

const { tracedFetchMock, navigateMock, locationMock } = vi.hoisted(() => ({
  tracedFetchMock: vi.fn(),
  navigateMock: vi.fn(),
  // Stable identities: the page's mount effect lists navigate/location values
  // in its dependency array, so fresh mocks per render would loop it forever.
  locationMock: { pathname: "/conversation/7", state: null },
}));

vi.mock("../services/api/client", () => ({
  default: { get: vi.fn(async () => []) },
  apiClient: { get: vi.fn(async () => []) },
  tracedFetch: tracedFetchMock,
}));

vi.mock("react-router-dom", () => ({
  useParams: () => ({ id: "7" }),
  useNavigate: () => navigateMock,
  useLocation: () => locationMock,
}));

// Stub the heavy children; the HeaderBar stub mirrors the real picker's
// fallback rendering (HeaderBar.jsx: {currentModel || "Select model..."}).
vi.mock("../components/Sidebar", () => ({ default: () => null }));
vi.mock("../components/ChatCollapsibleSection", () => ({ default: () => null }));
vi.mock("../components/QuestionInput", () => ({ default: () => null }));
vi.mock("../components/TypingIndicator", () => ({ default: () => null }));
vi.mock("../components/MarkdownRenderer", () => ({ default: () => null }));
vi.mock("../components/modals/CustomizePromptModal", () => ({ default: () => null }));
vi.mock("../components/HeaderBar", () => ({
  default: ({ currentModel }) => (
    <div data-testid="model-picker">{currentModel || "Select model..."}</div>
  ),
}));

import ConversationPage from "./ConversationPage.jsx";
import apiClient from "../services/api/client";

// jsdom does not implement Element.scrollTo (used by the auto-scroll effect).
beforeEach(() => {
  Element.prototype.scrollTo = () => {};
});

const models = [
  { id: 1, name: "llama-3.2-1b-instruct" },
  { id: 2, name: "qwen2.5-3b-instruct" },
];

const conversationDetail = {
  id: 7,
  llm_id: 2,
  temperature: 0.7,
  top_p: 0.9,
  max_tokens: 512,
  custom_prompt: "",
};

const jsonResponse = (payload) => ({ ok: true, json: async () => payload });

const routeFetch = async (url, opts = {}) => {
  const u = String(url);
  if (opts.method === "PATCH") return jsonResponse({});
  if (u.endsWith("/llms/local")) return jsonResponse(models);
  if (u.endsWith("/conversations/7")) return jsonResponse(conversationDetail);
  return jsonResponse([]);
};

const picker = () => screen.getByTestId("model-picker");

beforeEach(() => {
  tracedFetchMock.mockClear();
  apiClient.get.mockClear();
  tracedFetchMock.mockImplementation(routeFetch);
});
afterEach(() => {
  cleanup();
});

describe("ConversationPage model picker hydration (#217)", () => {
  it("shows the conversation's assigned model after reopening, not the placeholder", async () => {
    render(<ConversationPage />);

    await waitFor(() => expect(picker().textContent).toBe("qwen2.5-3b-instruct"));
  });

  it("hydrates when the models list resolves AFTER the conversation detail", async () => {
    let resolveModels;
    const pendingModels = new Promise((resolve) => {
      resolveModels = resolve;
    });
    tracedFetchMock.mockImplementation(async (url, opts = {}) => {
      if (String(url).endsWith("/llms/local")) return pendingModels;
      return routeFetch(url, opts);
    });

    render(<ConversationPage />);

    // The conversation detail has fully landed (the load effect ends with
    // apiClient.get) while the models list is still in flight.
    await waitFor(() => expect(apiClient.get).toHaveBeenCalled());
    await act(async () => {});
    expect(picker().textContent).toBe("Select model...");

    await act(async () => {
      resolveModels(jsonResponse(models));
    });

    await waitFor(() => expect(picker().textContent).toBe("qwen2.5-3b-instruct"));
  });

  it("hydrates when the conversation detail resolves AFTER the models list", async () => {
    let resolveDetail;
    const pendingDetail = new Promise((resolve) => {
      resolveDetail = resolve;
    });
    tracedFetchMock.mockImplementation(async (url, opts = {}) => {
      const u = String(url);
      if (!opts.method && u.endsWith("/conversations/7")) return pendingDetail;
      return routeFetch(url, opts);
    });

    render(<ConversationPage />);

    // The models list has landed while the conversation detail is still in
    // flight (its Promise.all in the load effect is blocked on the detail).
    await waitFor(() =>
      expect(tracedFetchMock.mock.calls.some(([url]) => String(url).endsWith("/llms/local"))).toBe(
        true
      )
    );
    await act(async () => {});
    expect(picker().textContent).toBe("Select model...");

    await act(async () => {
      resolveDetail(jsonResponse(conversationDetail));
    });

    await waitFor(() => expect(picker().textContent).toBe("qwen2.5-3b-instruct"));
  });
});
