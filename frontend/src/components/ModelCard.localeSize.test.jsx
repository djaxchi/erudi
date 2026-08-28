// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import i18n from "../i18n";

// The installed card's Size line used to print the backend's English metadata
// string verbatim ("Taille : ~0.7 GB" in French, #387). It now goes through
// the locale formatter, preferring the measured artifact size when present.

vi.mock("../contexts/DownloadModalContext", () => ({
  useDownloadModal: () => ({ open: vi.fn() }),
}));

import ModelCard from "./ModelCard.jsx";

beforeEach(async () => {
  await i18n.changeLanguage("fr");
});
afterEach(async () => {
  cleanup();
  await i18n.changeLanguage("en");
});

describe("ModelCard size line in French (#387)", () => {
  it("formats the metadata size string in the active locale", () => {
    render(<ModelCard model={{ id: 1, name: "Gemma 1B", size: "~0.7 GB" }} type="local" />);
    expect(screen.getByText("Taille : ~0,7 Go")).toBeTruthy();
  });

  it("prefers the measured artifact size over the metadata string", () => {
    render(
      <ModelCard
        model={{ id: 1, name: "Gemma 1B", size: "~0.7 GB", artifact_size_bytes: 760_000_000 }}
        type="local"
      />
    );
    expect(screen.getByText("Taille : 0,8 Go")).toBeTruthy();
  });

  it("falls back to the parameter-count estimate, then to the raw value", () => {
    render(
      <ModelCard model={{ id: 1, name: "Seven", size: "Inconnu", param_size: 7 }} type="local" />
    );
    expect(screen.getByText("Taille : ~4,2 Go")).toBeTruthy();
    cleanup();
    render(<ModelCard model={{ id: 1, name: "Bare", size: "Inconnu" }} type="local" />);
    expect(screen.getByText("Taille : Inconnu")).toBeTruthy();
  });
});
