// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";

// Non-mutating interactions of ChatCollapsibleSection: selection/navigation,
// new chat, refresh (success + failure), collapse toggle and empty state.
// The DELETE and PATCH mutations are pinned in their own test files.

const { tracedFetchMock, navigateMock } = vi.hoisted(() => ({
  tracedFetchMock: vi.fn(),
  navigateMock: vi.fn(),
}));

vi.mock("../services/api/client", () => ({
  default: { get: vi.fn(async () => []) },
  apiClient: { get: vi.fn(async () => []) },
  tracedFetch: tracedFetchMock,
}));

vi.mock("react-router-dom", () => ({
  useNavigate: () => navigateMock,
}));

import ChatCollapsibleSection from "./ChatCollapsibleSection.jsx";

const items = [
  { id: "7", name: "My chat" },
  { id: "8", name: "Other chat" },
];

beforeEach(() => {
  tracedFetchMock.mockReset();
  navigateMock.mockReset();
});
afterEach(() => {
  cleanup();
});

describe("ChatCollapsibleSection interactions", () => {
  it("selecting a conversation calls onSelect and navigates to it", () => {
    const onSelect = vi.fn();
    render(
      <ChatCollapsibleSection
        title="Previous Chats"
        items={items}
        selectedId="8"
        onSelect={onSelect}
      />
    );

    fireEvent.click(screen.getByText("My chat"));
    expect(onSelect).toHaveBeenCalledWith("7");
    expect(String(navigateMock.mock.calls[0][0])).toContain("7");
  });

  it("highlights the selected conversation", () => {
    render(<ChatCollapsibleSection title="Previous Chats" items={items} selectedId="8" />);

    const selectedRow = screen.getByText("Other chat").closest("div");
    const otherRow = screen.getByText("My chat").closest("div");
    expect(selectedRow.className).toContain("bg-emerald-500/50");
    expect(otherRow.className).not.toContain("bg-emerald-500/50");
  });

  it("the plus button navigates to a new chat", () => {
    render(<ChatCollapsibleSection title="Previous Chats" items={items} />);

    fireEvent.click(screen.getByLabelText("New chat"));
    expect(navigateMock).toHaveBeenCalledWith("/erudi/chat");
  });

  it("toggles the collapsed state when the header is clicked", () => {
    const { container } = render(<ChatCollapsibleSection title="Previous Chats" items={items} />);

    const contentGrid = () => container.querySelector("div.grid");
    expect(contentGrid().className).toContain("grid-rows-[1fr]");
    fireEvent.click(screen.getByText("Previous Chats"));
    expect(contentGrid().className).toContain("grid-rows-[0fr]");
    fireEvent.click(screen.getByText("Previous Chats"));
    expect(contentGrid().className).toContain("grid-rows-[1fr]");
  });

  it("shows the empty state when there are no conversations", () => {
    render(<ChatCollapsibleSection title="Previous Chats" items={[]} />);
    expect(screen.getByText("Nothing here…")).toBeDefined();
  });

  it("refresh awaits onRefresh, showing a spinner meanwhile", async () => {
    let resolveRefresh;
    const onRefresh = vi.fn(() => new Promise((resolve) => (resolveRefresh = resolve)));
    render(<ChatCollapsibleSection title="Previous Chats" items={items} onRefresh={onRefresh} />);

    fireEvent.click(screen.getByLabelText("Refresh conversations"));

    // The list is replaced by a spinner while the refresh is in flight; the
    // handler debounces 300ms before invoking onRefresh.
    await waitFor(() => expect(screen.queryByText("My chat")).toBeNull());
    await waitFor(() => expect(onRefresh).toHaveBeenCalledTimes(1), { timeout: 2000 });

    resolveRefresh();
    await waitFor(() => expect(screen.getByText("My chat")).toBeDefined());
  });

  it("a failing refresh surfaces an error modal that can be closed", async () => {
    const onRefresh = vi.fn(async () => {
      throw new Error("backend gone");
    });
    render(<ChatCollapsibleSection title="Previous Chats" items={items} onRefresh={onRefresh} />);

    fireEvent.click(screen.getByLabelText("Refresh conversations"));
    await waitFor(() =>
      expect(screen.getByText(/Failed to refresh conversations: backend gone/)).toBeDefined()
    );

    fireEvent.click(screen.getByRole("button", { name: /close/i }));
    await waitFor(() => expect(screen.queryByText(/Failed to refresh conversations/)).toBeNull());
  });

  it("renders disabled styling when disabled", () => {
    const { container } = render(
      <ChatCollapsibleSection title="Previous Chats" items={items} disabled />
    );
    expect(container.firstChild.className).toContain("pointer-events-none");
  });
});
