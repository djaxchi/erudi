// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { waitFor } from "@testing-library/react";

// index.jsx is the renderer bootstrap: it mounts <App /> into #root and fades
// out the static HTML loader. These tests pin the three entry conditions —
// document already parsed, document still loading (DOMContentLoaded deferred),
// and a missing #root container (no crash, loader untouched).

vi.mock("./App.jsx", () => ({
  default: () => React.createElement("div", { "data-testid": "app-root" }, "APP"),
}));

const importBootstrap = async () => {
  vi.resetModules();
  await import("./index.jsx");
};

const setReadyState = (value) => {
  Object.defineProperty(document, "readyState", { value, configurable: true });
};

beforeEach(() => {
  document.body.innerHTML = '<div id="loader"></div><div id="root"></div>';
});

afterEach(() => {
  setReadyState("complete");
  document.body.innerHTML = "";
});

describe("renderer bootstrap (index.jsx)", () => {
  it("mounts the app immediately and fades then removes the loader", async () => {
    setReadyState("complete");
    await importBootstrap();

    await waitFor(() => expect(document.querySelector('[data-testid="app-root"]')).toBeTruthy());
    // The fade is applied synchronously; the node is removed shortly after.
    await waitFor(() => expect(document.getElementById("loader")).toBeNull());
  });

  it("waits for DOMContentLoaded when the document is still loading", async () => {
    setReadyState("loading");
    await importBootstrap();

    // Nothing mounted yet: the bootstrap deferred to the DOMContentLoaded event.
    expect(document.querySelector('[data-testid="app-root"]')).toBeNull();
    expect(document.getElementById("loader").style.opacity).toBe("");

    document.dispatchEvent(new Event("DOMContentLoaded"));
    await waitFor(() => expect(document.querySelector('[data-testid="app-root"]')).toBeTruthy());
    await waitFor(() => expect(document.getElementById("loader")).toBeNull());
  });

  it("no-ops safely when the #root container is absent", async () => {
    document.body.innerHTML = '<div id="loader"></div>';
    setReadyState("complete");
    await importBootstrap();

    // Early return: no app, and the loader was never touched.
    expect(document.querySelector('[data-testid="app-root"]')).toBeNull();
    expect(document.getElementById("loader").style.opacity).toBe("");
  });
});
