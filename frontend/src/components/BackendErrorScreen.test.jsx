// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";
import BackendErrorScreen from "./BackendErrorScreen.jsx";

const ERROR = {
  code: "PORT_TIMEOUT",
  title: "Backend did not start in time",
  detail: "The local server did not come up.",
  hint: "Relaunch Erudi.",
  raw: null,
};

afterEach(() => {
  cleanup();
  delete window.backendAPI;
});

const hasLogAndContact = (content) =>
  content.includes("erudi-backend.log") && content.includes("contact us");

describe("BackendErrorScreen", () => {
  it("shows the OS-correct log path from main and a contact-us message", async () => {
    window.backendAPI = {
      getLogPath: vi
        .fn()
        .mockResolvedValue("C:\\Users\\me\\AppData\\Local\\Temp\\erudi-backend.log"),
    };
    render(<BackendErrorScreen error={ERROR} onRetry={() => {}} onQuit={() => {}} />);
    await waitFor(() => expect(screen.getByText(hasLogAndContact)).toBeTruthy());
  });

  it("falls back gracefully when no log path is available", () => {
    render(<BackendErrorScreen error={ERROR} onRetry={() => {}} onQuit={() => {}} />);
    expect(screen.getByText(/Check the backend logs and contact us/i)).toBeTruthy();
  });

  it("invokes onRetry when Retry is clicked", () => {
    const onRetry = vi.fn();
    render(<BackendErrorScreen error={ERROR} onRetry={onRetry} onQuit={() => {}} />);
    fireEvent.click(screen.getByText("Retry"));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
