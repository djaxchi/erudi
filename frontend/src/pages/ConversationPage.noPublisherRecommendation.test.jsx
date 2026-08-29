// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, waitFor, fireEvent } from "@testing-library/react";

// The conversation header tells the user when the conversation's model has no
// publisher sampling recommendation (#388, `sampling_defaults.source ===
// "none"`), and the flag follows a mid-conversation model switch.

const { tracedFetchMock, navigateMock, locationMock } = vi.hoisted(() => ({
  tracedFetchMock: vi.fn(),
  navigateMock: vi.fn(),
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

vi.mock("../components/Sidebar", () => ({ default: () => null }));
vi.mock("../components/ChatCollapsibleSection", () => ({ default: () => null }));
vi.mock("../components/QuestionInput", () => ({ default: () => null }));
vi.mock("../components/TypingIndicator", () => ({ default: () => null }));
vi.mock("../components/MarkdownRenderer", () => ({ default: () => null }));
vi.mock("../components/modals/CustomizePromptModal", () => ({ default: () => null }));
vi.mock("../components/HeaderBar", () => ({
  default: ({ currentModel, noPublisherRecommendation, onModelChange }) => (
    <div>
      <div data-testid="header">{`${currentModel}|${String(noPublisherRecommendation)}`}</div>
      <button onClick={() => onModelChange("qwen3")}>PICK_QWEN3</button>
      <button onClick={() => onModelChange("llama")}>PICK_LLAMA</button>
    </div>
  ),
}));

import ConversationPage from "./ConversationPage.jsx";

const models = [
  {
    id: 1,
    name: "qwen3",
    weights_available: true,
    sampling_defaults: {
      temperature: 0.6,
      top_p: 0.95,
      max_tokens: 1024,
      max_tokens_cap: 8192,
      source: "base_generation_config",
    },
  },
  {
    id: 2,
    name: "llama",
    weights_available: true,
    sampling_defaults: {
      temperature: 0.2,
      top_p: 0.95,
      max_tokens: 1024,
      max_tokens_cap: 32768,
      source: "none",
    },
  },
];

const detail = {
  id: 7,
  llm_id: 2,
  temperature: 0.2,
  top_p: 0.95,
  max_tokens: 1024,
  custom_prompt: "",
};

const jsonResponse = (payload) => ({ ok: true, json: async () => payload });

const routeFetch = async (url, opts = {}) => {
  const u = String(url);
  if (opts.method === "PATCH") return jsonResponse({});
  if (u.endsWith("/llms/local")) return jsonResponse(models);
  if (u.endsWith("/conversations/7")) return jsonResponse(detail);
  return jsonResponse([]);
};

const header = () => screen.getByTestId("header").textContent;

beforeEach(() => {
  Element.prototype.scrollTo = () => {};
  tracedFetchMock.mockReset();
  tracedFetchMock.mockImplementation(routeFetch);
});
afterEach(() => {
  cleanup();
});

describe("ConversationPage publisher recommendation flag (#388)", () => {
  it("flags the conversation's model when its source is none", async () => {
    render(<ConversationPage />);
    await waitFor(() => expect(header()).toBe("llama|true"));
  });

  it("follows a model switch in both directions", async () => {
    render(<ConversationPage />);
    await waitFor(() => expect(header()).toBe("llama|true"));

    fireEvent.click(screen.getByText("PICK_QWEN3"));
    await waitFor(() => expect(header()).toBe("qwen3|false"));

    fireEvent.click(screen.getByText("PICK_LLAMA"));
    await waitFor(() => expect(header()).toBe("llama|true"));
  });
});
