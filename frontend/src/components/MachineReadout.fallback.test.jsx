// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import MachineReadout from "./MachineReadout";

// Fallback facets: the pre-benchmark loading strip and a machine object with
// nothing measured yet (unknown chip, no score, no recommended range).

afterEach(() => {
  cleanup();
});

describe("MachineReadout fallbacks", () => {
  it("shows the loading strip before the benchmark resolves", () => {
    render(<MachineReadout loading />);

    expect(screen.getByText(/reading hardware/)).toBeTruthy();
  });

  it("renders unknowns when nothing was measured", () => {
    render(<MachineReadout machine={undefined} loading={false} />);

    expect(screen.getByText("Unknown")).toBeTruthy(); // chip
    expect(screen.getAllByText("n/a").length).toBeGreaterThanOrEqual(2); // score label + range
    expect(screen.getByText("Run a model to gauge your fit.")).toBeTruthy();
    // No numeric stats -> no VRAM/RAM figures rendered.
    expect(screen.queryByText("GB")).toBeNull();
  });
});
