// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, cleanup, screen, fireEvent } from "@testing-library/react";

import MessageModal from "./MessageModal.jsx";

afterEach(cleanup);

const setup = (overrides = {}) => {
  const props = {
    isOpen: true,
    title: "Heads up",
    message: "Something happened.",
    onClose: vi.fn(),
    ...overrides,
  };
  const utils = render(<MessageModal {...props} />);
  return { props, ...utils };
};

describe("MessageModal", () => {
  it("renders nothing when closed", () => {
    setup({ isOpen: false });
    expect(screen.queryByText("Heads up")).toBeNull();
  });

  it("shows title and message", () => {
    setup();
    expect(screen.getByText("Heads up")).toBeTruthy();
    expect(screen.getByText("Something happened.")).toBeTruthy();
  });

  it("styles the body per message type", () => {
    const bodyBox = () => screen.getByText("Something happened.").parentElement;

    setup({ type: "success" });
    expect(bodyBox().className).toContain("text-green-400");
    cleanup();

    setup({ type: "error" });
    expect(bodyBox().className).toContain("text-red-400");
    cleanup();

    setup(); // default "info"
    expect(bodyBox().className).toContain("text-white");
  });

  it("both close controls fire onClose", () => {
    const { props, container } = setup();
    fireEvent.click(screen.getByText("Close"));
    expect(props.onClose).toHaveBeenCalledTimes(1);

    const headerX = container.querySelector("h2 + button");
    fireEvent.click(headerX);
    expect(props.onClose).toHaveBeenCalledTimes(2);
  });
});
