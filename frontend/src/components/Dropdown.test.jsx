// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import Dropdown from "./Dropdown";

const options = ["Alpha", "Beta", "Gamma"];

afterEach(cleanup);

describe("Dropdown", () => {
  it("starts closed, showing only the current value", () => {
    render(<Dropdown options={options} value="Alpha" onChange={() => {}} />);
    expect(screen.getByRole("button").textContent).toContain("Alpha");
    expect(screen.queryByText("Beta")).toBeNull();
  });

  it("opens on click, selects an option and closes", () => {
    const onChange = vi.fn();
    render(<Dropdown options={options} value="Alpha" onChange={onChange} />);
    fireEvent.click(screen.getByRole("button"));
    fireEvent.click(screen.getByText("Beta"));
    expect(onChange).toHaveBeenCalledWith("Beta");
    expect(screen.queryByText("Gamma")).toBeNull(); // list closed again
  });

  it("marks the current value in the open list", () => {
    render(<Dropdown options={options} value="Gamma" onChange={() => {}} />);
    fireEvent.click(screen.getByRole("button"));
    const items = screen.getAllByRole("listitem");
    const gamma = items.find((li) => li.textContent === "Gamma");
    expect(gamma.className).toContain("font-semibold");
  });

  it("closes when clicking outside", () => {
    render(<Dropdown options={options} value="Alpha" onChange={() => {}} />);
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("Beta")).toBeTruthy();
    fireEvent.mouseDown(document.body);
    expect(screen.queryByText("Beta")).toBeNull();
  });

  it("toggles closed when the button is clicked twice", () => {
    render(<Dropdown options={options} value="Alpha" onChange={() => {}} />);
    const button = screen.getByRole("button");
    fireEvent.click(button);
    fireEvent.click(button);
    expect(screen.queryByText("Beta")).toBeNull();
  });
});
