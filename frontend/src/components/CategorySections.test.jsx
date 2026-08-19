// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import CategorySections from "./CategorySections";

afterEach(cleanup);

describe("CategorySections", () => {
  it("shows a loading placeholder while the catalog builds", () => {
    render(<CategorySections models={[]} loading />);
    expect(screen.getByText(/building catalog/)).toBeTruthy();
  });

  it("explains an empty result, echoing the search query", () => {
    render(<CategorySections models={[]} searchQuery="llama" />);
    expect(screen.getByText(/No base models found for “llama”/)).toBeTruthy();
  });

  it("falls back to a generic empty message without a query", () => {
    render(<CategorySections models={[]} />);
    expect(screen.getByText("No base models available")).toBeTruthy();
  });

  it("renders one carousel per capability group, in catalog order", () => {
    render(
      <CategorySections
        models={[
          { id: 1, name: "Coder", category: "code", param_size: 2 },
          { id: 2, name: "Chatty", category: "general", param_size: 2 },
        ]}
      />
    );
    // The category label also appears on each card, so take the section
    // headers (first occurrence of each) to check the ordering.
    const general = screen.getAllByText("General")[0];
    const code = screen.getAllByText("Code")[0];
    expect(general.compareDocumentPosition(code) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});
