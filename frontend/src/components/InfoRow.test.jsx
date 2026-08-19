// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import InfoRow from "./InfoRow";

afterEach(cleanup);

describe("InfoRow", () => {
  it("renders the label and value", () => {
    render(<InfoRow label="Memory">16 GB</InfoRow>);
    expect(screen.getByText("Memory")).toBeTruthy();
    expect(screen.getByText("16 GB")).toBeTruthy();
  });

  it("uses header typography when isHeader is set", () => {
    render(
      <InfoRow label="CPU" isHeader>
        M3 Pro
      </InfoRow>
    );
    expect(screen.getByText("CPU").className).toContain("font-bold");
  });

  it("shows a colored bullet when provided", () => {
    const { container } = render(
      <InfoRow label="Status" bullet="bg-green-500">
        OK
      </InfoRow>
    );
    expect(container.querySelector(".bg-green-500")).not.toBeNull();
  });

  it("prefers the icon over the bullet", () => {
    const { container } = render(
      <InfoRow label="Status" bullet="bg-green-500" icon={<span data-icon="x" />}>
        OK
      </InfoRow>
    );
    expect(container.querySelector("[data-icon='x']")).not.toBeNull();
    expect(container.querySelector(".bg-green-500")).toBeNull();
  });
});
