// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, cleanup, waitFor } from "@testing-library/react";

// Stub the heavy pages/contexts so App's readiness logic renders in isolation.
vi.mock("./pages/LandingPage", () => ({ default: () => <div>MODELS_PAGE</div> }));
vi.mock("./pages/ChatPage", () => ({ default: () => <div>CHAT</div> }));
vi.mock("./pages/ConversationPage", () => ({ default: () => <div>CONV</div> }));
vi.mock("./pages/ArenaPage", () => ({ default: () => <div>ARENA</div> }));
vi.mock("./pages/KnowledgeBasePage", () => ({ default: () => <div>KB</div> }));
vi.mock("./components/UpdateBanner", () => ({ default: () => null }));
vi.mock("./contexts/DownloadModalContext", () => ({
  DownloadModalProvider: ({ children }) => <>{children}</>,
}));
vi.mock("./contexts/KnowledgeBaseContext", () => ({
  KnowledgeBaseProvider: ({ children }) => <>{children}</>,
}));

import App from "./App.jsx";
import { getApiBaseUrl } from "./config/api.js";

let emit;
beforeEach(() => {
  emit = null;
  window.backendAPI = {
    onBackendEvent: (cb) => {
      emit = cb;
      return () => {
        emit = null;
      };
    },
    getInfo: vi.fn().mockResolvedValue({ port: null, ready: false }),
    restartBackend: vi.fn().mockResolvedValue({ ok: true }),
    getLogPath: vi.fn().mockResolvedValue("/tmp/erudi-backend.log"),
  };
});
afterEach(() => {
  cleanup();
  delete window.backendAPI;
});

describe("App readiness", () => {
  it("shows the loader until a ready event, then the models page", async () => {
    render(<App />);
    expect(screen.getByText(/AI with you, for you/i)).toBeTruthy(); // loading screen
    await act(async () => {
      emit({ event: "ready", port: 8766 });
    });
    await waitFor(() => expect(screen.getByText("MODELS_PAGE")).toBeTruthy());
  });

  it("adopts the backend's resolved port from the starting event", async () => {
    render(<App />);
    await act(async () => {
      emit({ event: "starting", port: 8791, first_run: true });
    });
    expect(getApiBaseUrl()).toContain("8791");
  });

  it("shows the error screen on a startup_error event", async () => {
    render(<App />);
    await act(async () => {
      emit({ event: "startup_error", code: "IMPORT_ERROR" });
    });
    await waitFor(() => expect(screen.getByText(/Backend failed to load/i)).toBeTruthy());
  });

  it("re-spawns the backend when Retry is clicked", async () => {
    render(<App />);
    await act(async () => {
      emit({ event: "startup_error", code: "CRASH_BEFORE_READY" });
    });
    const retry = await screen.findByText("Retry");
    await act(async () => {
      retry.click();
    });
    expect(window.backendAPI.restartBackend).toHaveBeenCalled();
  });
});
