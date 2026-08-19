// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, cleanup, screen, fireEvent } from "@testing-library/react";

import ConfirmationModal from "./ConfirmationModal.jsx";

afterEach(cleanup);

const setup = (overrides = {}) => {
  const props = {
    text: "Gemma 4B",
    isOpen: true,
    onConfirm: vi.fn(),
    onCancel: vi.fn(),
    ...overrides,
  };
  const utils = render(<ConfirmationModal {...props} />);
  return { props, ...utils };
};

describe("ConfirmationModal (download confirmation)", () => {
  it("renders nothing when closed", () => {
    setup({ isOpen: false });
    expect(screen.queryByText("Download")).toBeNull();
  });

  it("asks about the exact model name", () => {
    setup();
    expect(screen.getByText("Gemma 4B")).toBeTruthy();
    expect(screen.getByText(/Are you sure you want to download/)).toBeTruthy();
    expect(screen.getByText(/installed locally on your system/)).toBeTruthy();
  });

  it("Download fires onConfirm only", () => {
    const { props } = setup();
    fireEvent.click(screen.getByText("Download"));

    expect(props.onConfirm).toHaveBeenCalledTimes(1);
    expect(props.onCancel).not.toHaveBeenCalled();
  });

  it("Cancel fires onCancel only", () => {
    const { props } = setup();
    fireEvent.click(screen.getByText("Cancel"));

    expect(props.onCancel).toHaveBeenCalledTimes(1);
    expect(props.onConfirm).not.toHaveBeenCalled();
  });
});
