// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import MachineReadout from "./MachineReadout.jsx";

afterEach(cleanup);

// The memory stat is platform-dependent (#202): Apple Silicon shares one pool
// ("Unified memory"), CPU/CUDA machines expose plain "RAM", and CUDA adds a
// separate "VRAM" stat sourced from vram_total_gb.
describe("MachineReadout memory labels", () => {
  it("labels CPU-only memory as RAM and shows no VRAM stat", () => {
    render(<MachineReadout machine={{ backend: "CPU", memoryGb: 16 }} />);
    expect(screen.getByText("RAM")).toBeTruthy();
    expect(screen.queryByText("Unified memory")).toBeNull();
    expect(screen.queryByText("VRAM")).toBeNull();
  });

  it("labels Apple Silicon memory as Unified memory", () => {
    render(<MachineReadout machine={{ backend: "MLX", memoryGb: 36 }} />);
    expect(screen.getByText("Unified memory")).toBeTruthy();
    expect(screen.queryByText("RAM")).toBeNull();
    expect(screen.queryByText("VRAM")).toBeNull();
  });

  it("labels CUDA memory as RAM and adds a separate VRAM stat", () => {
    render(<MachineReadout machine={{ backend: "CUDA", memoryGb: 32, vramGb: 12 }} />);
    expect(screen.getByText("RAM")).toBeTruthy();
    expect(screen.getByText("VRAM")).toBeTruthy();
    expect(screen.queryByText("Unified memory")).toBeNull();
    // The VRAM value renders alongside its label.
    expect(screen.getByText("12")).toBeTruthy();
  });
});
