// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, cleanup, fireEvent, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import InteractionLogger from "./InteractionLogger";

let sendSpy;

beforeEach(() => {
  sendSpy = vi.fn();
  window.logAPI = { send: sendSpy };
});

afterEach(() => {
  cleanup();
  delete window.logAPI;
});

const renderWithTracer = (fixture) =>
  render(
    <MemoryRouter initialEntries={["/erudi/models"]}>
      <InteractionLogger />
      {fixture}
    </MemoryRouter>
  );

const uiEntries = () => sendSpy.mock.calls.map(([entry]) => entry).filter((e) => e.ns === "UI");
const entriesOf = (msg) => uiEntries().filter((e) => e.msg === msg);
const dataOf = (entry) => JSON.parse(entry.data);

describe("InteractionLogger", () => {
  it("logs clicks with type, route, and the target label", () => {
    renderWithTracer(<button aria-label="Download model">Get</button>);
    fireEvent.click(screen.getByRole("button", { name: "Download model" }));

    const [entry] = entriesOf("ui.click");
    expect(entry).toBeTruthy();
    expect(entry.level).toBe("info");
    const data = dataOf(entry);
    expect(data.type).toBe("click");
    expect(data.route).toBe("/erudi/models");
    expect(data.target).toMatchObject({ label: "Download model", tag: "button" });
  });

  it("logs the final textarea value on focusout, truncated to 200 chars", () => {
    renderWithTracer(<textarea aria-label="Prompt" defaultValue="" />);
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "y".repeat(250) } });
    fireEvent.focusOut(textarea);

    const [entry] = entriesOf("ui.focusout");
    expect(entry).toBeTruthy();
    const data = dataOf(entry);
    expect(data.value.startsWith("yyyy")).toBe(true);
    expect(data.value.endsWith("… [+50]")).toBe(true);
    // A change event on a textarea must NOT produce a ui.change entry.
    expect(entriesOf("ui.change")).toHaveLength(0);
  });

  it("does not log plain letter keydowns, only Enter/Escape", () => {
    renderWithTracer(<textarea aria-label="Prompt" defaultValue="" />);
    const textarea = screen.getByRole("textbox");

    fireEvent.keyDown(textarea, { key: "a" });
    expect(entriesOf("ui.keydown")).toHaveLength(0);

    fireEvent.keyDown(textarea, { key: "Enter" });
    const [entry] = entriesOf("ui.keydown");
    expect(entry).toBeTruthy();
    expect(dataOf(entry)).toMatchObject({ key: "Enter", route: "/erudi/models" });
  });

  it("logs committed select and checkbox changes", () => {
    renderWithTracer(
      <>
        <select aria-label="Sort" defaultValue="a">
          <option value="a">A</option>
          <option value="b">B</option>
        </select>
        <input type="checkbox" aria-label="Enable" value="on" />
      </>
    );
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "b" } });
    fireEvent.click(screen.getByRole("checkbox"));

    const changes = entriesOf("ui.change").map(dataOf);
    expect(changes.some((d) => d.target.tag === "select" && d.value === "b")).toBe(true);
    expect(
      changes.some((d) => d.input_type === "checkbox" && d.checked === true && d.value === "on")
    ).toBe(true);
  });

  it("detaches its listeners on unmount", () => {
    const { unmount } = renderWithTracer(<button aria-label="Ghost">G</button>);
    unmount();
    sendSpy.mockClear();
    fireEvent.click(document.body);
    expect(uiEntries()).toHaveLength(0);
  });
});
