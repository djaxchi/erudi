// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, cleanup, fireEvent, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import InteractionLogger from "./InteractionLogger";

// Facets beyond InteractionLogger.test.jsx: slider (range) changes, file
// drops, and paste shape logging (length + image flag, never the payload).

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

describe("InteractionLogger media interactions", () => {
  it("logs a committed range value", () => {
    renderWithTracer(<input aria-label="Creativity" type="range" min="0" max="1" step="0.1" />);
    fireEvent.change(screen.getByLabelText("Creativity"), { target: { value: "0.7" } });

    const [entry] = entriesOf("ui.change");
    expect(entry).toBeTruthy();
    expect(dataOf(entry)).toMatchObject({ input_type: "range", value: "0.7" });
  });

  it("logs dropped file names and count", () => {
    renderWithTracer(<div data-testid="dropzone">Drop here</div>);
    fireEvent.drop(screen.getByTestId("dropzone"), {
      dataTransfer: { files: [{ name: "notes.pdf" }, { name: "specs.docx" }] },
    });

    const [entry] = entriesOf("ui.drop");
    expect(entry).toBeTruthy();
    expect(dataOf(entry)).toMatchObject({
      files: ["notes.pdf", "specs.docx"],
      file_count: 2,
    });
  });

  it("logs a drop without a dataTransfer as zero files", () => {
    renderWithTracer(<div data-testid="dropzone">Drop here</div>);
    fireEvent.drop(screen.getByTestId("dropzone"));

    const [entry] = entriesOf("ui.drop");
    expect(dataOf(entry)).toMatchObject({ files: [], file_count: 0 });
  });

  it("logs paste shape only: text length and image presence, never the content", () => {
    renderWithTracer(<textarea aria-label="Prompt" />);
    fireEvent.paste(screen.getByLabelText("Prompt"), {
      clipboardData: {
        getData: () => "secret pasted text",
        items: [{ type: "image/png" }],
      },
    });

    const [entry] = entriesOf("ui.paste");
    expect(entry).toBeTruthy();
    const data = dataOf(entry);
    expect(data).toMatchObject({ text_length: 18, has_image: true });
    expect(entry.data).not.toContain("secret");
  });

  it("logs a paste without clipboard data as empty shape", () => {
    renderWithTracer(<textarea aria-label="Prompt" />);
    fireEvent.paste(screen.getByLabelText("Prompt"));

    const [entry] = entriesOf("ui.paste");
    expect(dataOf(entry)).toMatchObject({ text_length: 0, has_image: false });
  });
});
