// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import TrainNewModelCard from "./TrainNewModelCard";

afterEach(cleanup);

describe("TrainNewModelCard", () => {
  it("navigates to the knowledge base page on click", () => {
    render(
      <MemoryRouter initialEntries={["/erudi/models"]}>
        <Routes>
          <Route path="/erudi/models" element={<TrainNewModelCard />} />
          <Route path="/erudi/attach_knowledge_base" element={<div>KB_PAGE</div>} />
        </Routes>
      </MemoryRouter>
    );
    const label = screen.getByText("Attach Knowledge Base");
    expect(label).toBeTruthy();
    fireEvent.click(label.previousSibling); // the clickable card wrapper
    expect(screen.getByText("KB_PAGE")).toBeTruthy();
  });
});
