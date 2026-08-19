// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, cleanup, screen, fireEvent } from "@testing-library/react";

import ComingSoonModal from "./ComingSoonModal.jsx";

afterEach(cleanup);

describe("ComingSoonModal", () => {
  it("renders nothing when hidden", () => {
    render(
      <ComingSoonModal showComingSoonModal={false} onClose={vi.fn()} featureName="Training" />
    );
    expect(screen.queryByText("Coming Soon")).toBeNull();
  });

  it("names the feature under development", () => {
    render(<ComingSoonModal showComingSoonModal onClose={vi.fn()} featureName="Training" />);
    expect(screen.getByText("Coming Soon")).toBeTruthy();
    expect(screen.getByText("Training")).toBeTruthy();
    expect(screen.getByText(/under development/)).toBeTruthy();
  });

  it("shows the optional description box only when provided", () => {
    const { unmount } = render(
      <ComingSoonModal
        showComingSoonModal
        onClose={vi.fn()}
        featureName="Training"
        featureDescription="Fine-tune models on your own data."
      />
    );
    expect(screen.getByText("Fine-tune models on your own data.")).toBeTruthy();
    unmount();

    render(<ComingSoonModal showComingSoonModal onClose={vi.fn()} featureName="Training" />);
    expect(screen.queryByText("Fine-tune models on your own data.")).toBeNull();
  });

  it("both the X button and 'Got it' close the modal", () => {
    const onClose = vi.fn();
    const { container } = render(
      <ComingSoonModal showComingSoonModal onClose={onClose} featureName="Training" />
    );

    fireEvent.click(screen.getByText("Got it"));
    expect(onClose).toHaveBeenCalledTimes(1);

    const buttons = container.querySelectorAll("button");
    // First button in the DOM is the header X.
    fireEvent.click(buttons[0]);
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
