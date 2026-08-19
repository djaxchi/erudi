// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const { getMock, putMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  putMock: vi.fn(),
}));

vi.mock("../services/api/client", () => ({
  default: { get: getMock, put: putMock },
  apiClient: { get: getMock, put: putMock },
}));

vi.mock("../components/Sidebar", () => ({
  default: () => <div data-testid="sidebar" />,
}));

import SettingsPage from "./SettingsPage";

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/erudi/settings"]}>
      <SettingsPage />
    </MemoryRouter>
  );
}

beforeEach(() => {
  getMock.mockResolvedValue({ web_search_enabled: false });
  putMock.mockResolvedValue({ web_search_enabled: true });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("SettingsPage", () => {
  it("renders the settings heading and the web search section", async () => {
    renderPage();
    expect(screen.getByText("Settings")).toBeTruthy();
    expect(await screen.findByText("Web Search")).toBeTruthy();
  });

  it("fetches the user settings on mount", async () => {
    renderPage();
    await waitFor(() => expect(getMock).toHaveBeenCalledWith("/user_settings/"));
  });

  it("reflects the fetched value on the toggle (off by default)", async () => {
    renderPage();
    const toggle = await screen.findByRole("switch", { name: "Web search" });
    await waitFor(() => expect(toggle.getAttribute("aria-checked")).toBe("false"));
  });

  it("reflects an enabled global setting", async () => {
    getMock.mockResolvedValue({ web_search_enabled: true });
    renderPage();
    const toggle = await screen.findByRole("switch", { name: "Web search" });
    await waitFor(() => expect(toggle.getAttribute("aria-checked")).toBe("true"));
  });

  it("PUTs the new value when toggled and updates the UI", async () => {
    renderPage();
    const toggle = await screen.findByRole("switch", { name: "Web search" });
    await waitFor(() => expect(getMock).toHaveBeenCalled());
    fireEvent.click(toggle);
    await waitFor(() =>
      expect(putMock).toHaveBeenCalledWith("/user_settings/", {
        web_search_enabled: true,
      })
    );
    await waitFor(() => expect(toggle.getAttribute("aria-checked")).toBe("true"));
  });

  it("explains the privacy trade-off and the inheritance rule", async () => {
    renderPage();
    await screen.findByText("Web Search");
    const page = document.body.textContent;
    expect(page).toMatch(/search engines/i);
    expect(page).toMatch(/new conversations/i);
  });

  it("renders the sidebar", () => {
    renderPage();
    expect(screen.getByTestId("sidebar")).toBeTruthy();
  });
});
