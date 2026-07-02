// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import LoadingScreen from "./LoadingScreen.jsx";

afterEach(cleanup);

describe("LoadingScreen", () => {
  it("shows a human label for the current phase", () => {
    render(<LoadingScreen phase="preparing_database" firstRun={false} />);
    expect(screen.getByText(/Preparing the database/i)).toBeTruthy();
  });

  it("falls back to a generic label for an unknown/absent phase", () => {
    render(<LoadingScreen phase={null} firstRun={false} />);
    expect(screen.getByText(/Starting Erudi/i)).toBeTruthy();
  });

  it("labels the crash-recovery phase", () => {
    render(<LoadingScreen phase="recovering_database" firstRun={false} />);
    expect(screen.getByText(/Recovering the database/i)).toBeTruthy();
  });

  it("shows the first-launch hint only on first run", () => {
    const { rerender } = render(<LoadingScreen phase="starting" firstRun={true} />);
    expect(screen.getByText(/First launch/i)).toBeTruthy();
    rerender(<LoadingScreen phase="starting" firstRun={false} />);
    expect(screen.queryByText(/First launch/i)).toBeNull();
  });
});
