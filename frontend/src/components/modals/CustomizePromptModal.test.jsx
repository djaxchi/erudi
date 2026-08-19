// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, cleanup, screen, fireEvent } from "@testing-library/react";

import CustomizePromptModal from "./CustomizePromptModal.jsx";

afterEach(cleanup);

const setup = (overrides = {}) => {
  const props = {
    isOpen: true,
    onClose: vi.fn(),
    onSave: vi.fn(),
    customPrompt: "You are a helpful assistant.",
    ...overrides,
  };
  const utils = render(<CustomizePromptModal {...props} />);
  return { props, ...utils };
};

describe("CustomizePromptModal", () => {
  it("renders nothing when closed", () => {
    const { container } = setup({ isOpen: false });
    expect(container.querySelector("textarea")).toBeNull();
  });

  it("shows the default title and seeds the textarea with the current prompt", () => {
    setup();
    expect(screen.getByText("Customize System Prompt")).toBeTruthy();
    expect(screen.getByRole("textbox").value).toBe("You are a helpful assistant.");
  });

  it("shows a custom title when provided", () => {
    setup({ title: "Assistant Instructions" });
    expect(screen.getByText("Assistant Instructions")).toBeTruthy();
  });

  it("saves the edited prompt and closes", () => {
    const { props } = setup();
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "Answer only in French." },
    });
    fireEvent.click(screen.getByText("Save Changes"));

    expect(props.onSave).toHaveBeenCalledTimes(1);
    expect(props.onSave).toHaveBeenCalledWith("Answer only in French.");
    expect(props.onClose).toHaveBeenCalledTimes(1);
  });

  it("does not crash on save when onSave is not provided", () => {
    const onClose = vi.fn();
    render(<CustomizePromptModal isOpen onClose={onClose} customPrompt="p" onSave={undefined} />);
    fireEvent.click(screen.getByText("Save Changes"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("cancel discards the edit and closes without saving", () => {
    const { props } = setup();
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "discard me" } });
    fireEvent.click(screen.getByText("Cancel"));

    expect(props.onSave).not.toHaveBeenCalled();
    expect(props.onClose).toHaveBeenCalledTimes(1);
    // Local state is reset to the original prompt, so a later save cannot
    // leak the discarded draft.
    expect(textarea.value).toBe("You are a helpful assistant.");
  });

  it("re-seeds the textarea when the prompt prop changes (conversation switch)", () => {
    const { rerender, props } = setup();
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "draft" } });

    rerender(<CustomizePromptModal {...props} customPrompt="Prompt of the other conversation" />);
    expect(screen.getByRole("textbox").value).toBe("Prompt of the other conversation");
  });

  it("the header X button closes without saving", () => {
    const { props, container } = setup();
    // The X button is the only button inside the header row (contains an svg,
    // no text label).
    const headerClose = container.querySelector("h2 + button");
    fireEvent.click(headerClose);

    expect(props.onClose).toHaveBeenCalledTimes(1);
    expect(props.onSave).not.toHaveBeenCalled();
  });
});
