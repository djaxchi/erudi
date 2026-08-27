// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import FitGauge, { FitDot } from "./FitGauge";

const range = { min: 2, max: 8 };

afterEach(cleanup);

describe("FitGauge", () => {
  it("labels an in-window model as an ideal fit with its footprint", () => {
    render(<FitGauge paramSize={4} quantized range={range} />);
    expect(screen.getByText("Ideal fit")).toBeTruthy();
    expect(screen.getByText("~2.4 GB")).toBeTruthy(); // 4B quantized × 0.6 GB/B
  });

  it("labels a below-window model as running easily", () => {
    render(<FitGauge paramSize={1} range={range} />);
    expect(screen.getByText("Runs easily")).toBeTruthy();
  });

  it("labels a model just above the ceiling as a tight fit", () => {
    render(<FitGauge paramSize={12} range={range} />);
    expect(screen.getByText("Tight fit")).toBeTruthy();
  });

  it("labels an oversized model as needing more memory", () => {
    render(<FitGauge paramSize={20} range={range} />);
    expect(screen.getByText("Needs more memory")).toBeTruthy();
  });

  it("doubles the footprint estimate for non-quantized models", () => {
    render(<FitGauge paramSize={4} quantized={false} range={range} />);
    // Sizes go through the locale-aware formatter (#385), which drops a
    // trailing ".0" the way Intl does — "8 GB", not "8.0 GB".
    expect(screen.getByText("~8 GB")).toBeTruthy();
  });

  it("renders the neutral state when no benchmark window is known", () => {
    const { container } = render(<FitGauge paramSize={4} range={null} />);
    expect(screen.getByText("Fit unknown")).toBeTruthy();
    // No ceiling tick without a known window.
    expect(container.querySelectorAll(".bg-white\\/40").length).toBe(0);
  });

  it("hides the label row when showLabel is off", () => {
    render(<FitGauge paramSize={4} range={range} showLabel={false} />);
    expect(screen.queryByText("Ideal fit")).toBeNull();
  });

  it("draws the tick at the comfortable ceiling for known fits", () => {
    const { container } = render(<FitGauge paramSize={4} range={range} />);
    const tick = container.querySelector(".bg-white\\/40");
    expect(tick.style.left).toBe("50%");
  });
});

describe("FitDot", () => {
  it("labels a known fit", () => {
    render(<FitDot paramSize={4} range={range} />);
    expect(screen.getByLabelText("Ideal fit")).toBeTruthy();
  });

  it("labels an unknown fit and dims the dot", () => {
    render(<FitDot paramSize={4} range={null} />);
    const dot = screen.getByLabelText("Fit unknown");
    expect(dot.style.opacity).toBe("0.4");
  });
});
