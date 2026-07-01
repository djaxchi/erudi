// API Configuration
// Centralized API base URL for all frontend requests.
//
// The backend picks a free port at startup (it prefers 8765 but scans upward if
// it's taken) and announces the resolved port via its lifecycle events, which
// main.js forwards to the renderer. App.jsx calls setBackendPort() with that
// port before rendering the app, so every request targets the right port
// instead of a hardcoded 8765. `API_BASE_URL` is an ESM live binding — call
// sites that interpolate it at request time automatically see the update.

const DEFAULT_PORT = 8765;
let currentPort = DEFAULT_PORT;

export let API_BASE_URL = `http://127.0.0.1:${currentPort}/erudi`;

/** Point the renderer at the backend's actually-resolved port. */
export function setBackendPort(port) {
  const p = Number(port);
  if (!p || p === currentPort) return;
  currentPort = p;
  API_BASE_URL = `http://127.0.0.1:${currentPort}/erudi`;
}

/** Current API base URL (use this in long-lived objects, never cache the value). */
export function getApiBaseUrl() {
  return API_BASE_URL;
}
