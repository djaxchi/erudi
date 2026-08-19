// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, cleanup, screen, fireEvent } from "@testing-library/react";

import WelcomeModal from "./WelcomeModal.jsx";

afterEach(cleanup);

// Complements WelcomeModal.test.jsx (caption tiers, #303) with the modal's
// open/close mechanics and the loading / error / no-info hardware panel states.
describe("WelcomeModal states and close behavior", () => {
  it("renders nothing when closed", () => {
    render(<WelcomeModal isOpen={false} onClose={vi.fn()} />);
    expect(screen.queryByText("Welcome!")).toBeNull();
  });

  it("shows the evaluating spinner while loading", () => {
    render(<WelcomeModal isOpen onClose={vi.fn()} loading hardwareInfo={null} />);
    expect(screen.getByText(/We are evaluating your hardware/)).toBeTruthy();
    expect(screen.queryByText("Chat Performance")).toBeNull();
  });

  it("surfaces a hardware evaluation failure", () => {
    render(
      <WelcomeModal
        isOpen
        onClose={vi.fn()}
        loading={false}
        hardwareInfo={{ error: "probe timed out" }}
      />
    );
    expect(screen.getByText(/Evaluation Failed/)).toBeTruthy();
    expect(screen.getByText("probe timed out")).toBeTruthy();
  });

  it("shows no performance panel when hardware info is absent", () => {
    render(<WelcomeModal isOpen onClose={vi.fn()} loading={false} hardwareInfo={null} />);
    expect(screen.getByText("Hardware Evaluation")).toBeTruthy();
    expect(screen.queryByText("Chat Performance")).toBeNull();
  });

  it("rounds the score and falls back to Unknown badge for a missing label", () => {
    render(
      <WelcomeModal
        isOpen
        onClose={vi.fn()}
        loading={false}
        hardwareInfo={{ global_inference_score: 53.4, global_inference_label: null }}
      />
    );
    expect(screen.getByText("53%")).toBeTruthy();
    expect(screen.getByText("Unknown")).toBeTruthy();
  });

  it("closes on backdrop click but not on clicks inside the dialog", () => {
    const onClose = vi.fn();
    const { container } = render(
      <WelcomeModal isOpen onClose={onClose} loading={false} hardwareInfo={null} />
    );

    fireEvent.click(screen.getByText("Welcome!"));
    expect(onClose).not.toHaveBeenCalled();

    fireEvent.click(container.firstChild);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("Get Started closes the modal", () => {
    const onClose = vi.fn();
    render(<WelcomeModal isOpen onClose={onClose} loading={false} hardwareInfo={null} />);
    fireEvent.click(screen.getByText("Get Started"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
