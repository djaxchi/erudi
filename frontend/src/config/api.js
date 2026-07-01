// API Configuration
// Centralized API base URL for all frontend requests.
//
// The backend picks a free port at startup (it prefers Erudi's canonical 27182
// but scans 27182–27199 if it's taken) and announces the resolved port via its
// lifecycle events, which main.js forwards to the renderer. App.jsx calls
// setBackendPort() with that port before rendering the app, so every request
// targets the right port instead of the hardcoded default. `API_BASE_URL` is an
// ESM live binding — call sites that interpolate it at request time see the update.
//
// Why 27182: it's the leading digits of Euler's number e (2.7182…), a wink for an
// app for erudites — and a practically safe default (IANA-unassigned, below every
// OS's ephemeral range, clear of common dev/LLM ports). See backend/run.py.

const DEFAULT_PORT = 27182;
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
