// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, cleanup, waitFor } from "@testing-library/react";

// App readiness paths not exercised by App.test.jsx: the no-preload fallback
// (poll /health directly, give up after the timeout), the getInfo() race
// (readiness resolved before the event listener attached), the startup phase
// label, and the Quit action on the error screen.

vi.mock("./pages/LandingPage", () => ({ default: () => <div>MODELS_PAGE</div> }));
vi.mock("./pages/ChatPage", () => ({ default: () => <div>CHAT</div> }));
vi.mock("./pages/ConversationPage", () => ({ default: () => <div>CONV</div> }));
vi.mock("./pages/ArenaPage", () => ({ default: () => <div>ARENA</div> }));
vi.mock("./pages/KnowledgeBasePage", () => ({ default: () => <div>KB</div> }));
vi.mock("./components/UpdateBanner", () => ({ default: () => null }));
vi.mock("./components/InteractionLogger", () => ({ default: () => null }));
vi.mock("./contexts/DownloadModalContext", () => ({
  DownloadModalProvider: ({ children }) => <>{children}</>,
}));
vi.mock("./contexts/KnowledgeBaseContext", () => ({
  KnowledgeBaseProvider: ({ children }) => <>{children}</>,
}));
vi.mock("./services/api/client", () => ({
  apiClient: { get: vi.fn() },
  default: { get: vi.fn() },
}));

import App from "./App.jsx";
import { apiClient } from "./services/api/client";

afterEach(() => {
  cleanup();
  delete window.backendAPI;
  delete window.__ERUDI_BACKEND_TIMEOUT_MS__;
  vi.useRealTimers();
});
beforeEach(() => {
  apiClient.get.mockReset();
});

describe("App fallback health polling (no preload bridge)", () => {
  it("becomes ready when /health/ answers", async () => {
    apiClient.get.mockResolvedValue({ status: "ok" });

    render(<App />);

    await waitFor(() => expect(screen.getByText("MODELS_PAGE")).toBeTruthy());
    expect(apiClient.get).toHaveBeenCalledWith("/health/");
  });

  it("retries every 2s until the backend answers", async () => {
    vi.useFakeTimers();
    window.__ERUDI_BACKEND_TIMEOUT_MS__ = 60000;
    apiClient.get.mockRejectedValueOnce(new Error("down")).mockResolvedValue({ status: "ok" });

    render(<App />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(screen.queryByText("MODELS_PAGE")).toBeNull();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(screen.getByText("MODELS_PAGE")).toBeTruthy();
    expect(apiClient.get).toHaveBeenCalledTimes(2);
  });

  it("gives up with the unreachable error screen after the timeout", async () => {
    window.__ERUDI_BACKEND_TIMEOUT_MS__ = 1; // first failure is already too late
    apiClient.get.mockRejectedValue(new Error("down"));

    render(<App />);

    await waitFor(() => expect(screen.getByText("Retry")).toBeTruthy());
  });

  it("recovers through Retry once the backend answers again", async () => {
    window.__ERUDI_BACKEND_TIMEOUT_MS__ = 1;
    apiClient.get.mockRejectedValue(new Error("down"));

    render(<App />);
    const retry = await screen.findByText("Retry");

    apiClient.get.mockResolvedValue({ status: "ok" });
    await act(async () => {
      retry.click();
    });
    await waitFor(() => expect(screen.getByText("MODELS_PAGE")).toBeTruthy());
  });

  it("Quit closes the window", async () => {
    window.__ERUDI_BACKEND_TIMEOUT_MS__ = 1;
    apiClient.get.mockRejectedValue(new Error("down"));
    const closeSpy = vi.spyOn(window, "close").mockImplementation(() => {});

    render(<App />);
    const quit = await screen.findByText("Quit");
    await act(async () => {
      quit.click();
    });

    expect(closeSpy).toHaveBeenCalledTimes(1);
    closeSpy.mockRestore();
  });
});

describe("App bridge extras", () => {
  it("adopts readiness from getInfo() when the ready event fired before mount", async () => {
    window.backendAPI = {
      onBackendEvent: () => () => {},
      getInfo: vi.fn().mockResolvedValue({ port: 27183, ready: true }),
    };

    render(<App />);

    await waitFor(() => expect(screen.getByText("MODELS_PAGE")).toBeTruthy());
  });

  it("shows the human label of the reported startup phase", async () => {
    let emit;
    window.backendAPI = {
      onBackendEvent: (cb) => {
        emit = cb;
        return () => {};
      },
      getInfo: vi.fn().mockResolvedValue({ port: null, ready: false }),
    };

    render(<App />);
    await act(async () => {
      emit({ event: "phase", phase: "preparing_database" });
    });

    expect(screen.getByText(/Preparing the database/)).toBeTruthy();
  });
});
