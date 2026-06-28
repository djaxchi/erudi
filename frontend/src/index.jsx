import * as React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
// Self-hosted Montserrat (latin), bundled so the app's typography works offline.
import "@fontsource/montserrat/latin-400.css";
import "@fontsource/montserrat/latin-500.css";
import "@fontsource/montserrat/latin-600.css";
import "@fontsource/montserrat/latin-700.css";
import "@fontsource/montserrat/latin-800.css";
import "./index.css";

function renderApp() {
  const container = document.getElementById("root");
  if (!container) {
    return;
  }
  const root = createRoot(container);
  root.render(<App />);

  const loader = document.getElementById("loader");
  if (loader) {
    loader.style.transition = "opacity 0.5s ease";
    loader.style.opacity = "0";
    setTimeout(() => loader.remove(), 10);
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", renderApp);
} else {
  renderApp();
}
