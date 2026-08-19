// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import HardwareLoadingPopup from "./LoadingPopup";

afterEach(cleanup);

describe("HardwareLoadingPopup", () => {
  it("renders nothing when hidden", () => {
    const { container } = render(<HardwareLoadingPopup show={false} loading />);
    expect(container.innerHTML).toBe("");
  });

  it("reports the evaluation as in progress while loading", () => {
    render(<HardwareLoadingPopup show loading />);
    expect(screen.getByText("Evaluating Hardware")).toBeTruthy();
    expect(screen.getByText(/Loading\.\.\./)).toBeTruthy();
  });

  it("reports the evaluation as complete once loading ends", () => {
    render(<HardwareLoadingPopup show loading={false} />);
    expect(screen.getByText(/Complete/)).toBeTruthy();
  });

  it("closes from both the header icon and the footer button", () => {
    const onClose = vi.fn();
    render(<HardwareLoadingPopup show loading onClose={onClose} />);
    fireEvent.click(screen.getByText("Close"));
    const headerClose = document.querySelector("svg").closest("button");
    fireEvent.click(headerClose);
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
