// Pure helpers for interpreting backend lifecycle events.
//
// The backend (`backend/run.py`) emits newline-JSON lifecycle events that the
// Electron main process forwards to the renderer over the "backend-event" IPC
// channel: `{event: "starting"|"ready"|"shutdown"|"startup_error", code?, message?}`.
// `main.js` adds a few of its own codes when the spawn itself fails.
//
// Keeping the interpretation pure + dependency-free means it unit-tests cleanly and
// the renderer wiring (preload bridge + error screen) stays thin.

const MESSAGES = {
  PORT_IN_USE: {
    title: "Port already in use",
    detail: "Another process is using the port Erudi needs for its local server.",
    hint: "Quit any other running Erudi (or the app holding the port) and relaunch.",
  },
  NO_PORT_AVAILABLE: {
    title: "No free port",
    detail: "Erudi could not find a free port to start its local server.",
    hint: "Close other apps using local ports, then relaunch Erudi.",
  },
  PORT_TIMEOUT: {
    title: "Backend did not start in time",
    detail: "The local server did not come up within the startup window.",
    hint: "Relaunch Erudi. If it keeps happening, check the backend log.",
  },
  CRASH_BEFORE_READY: {
    title: "Backend crashed on startup",
    detail: "The local server stopped before it became ready.",
    hint: "Relaunch Erudi; if it persists, check the backend log.",
  },
  IMPORT_ERROR: {
    title: "Backend failed to load",
    detail: "A required backend component could not be loaded.",
    hint: "Reinstall or update Erudi, then check the backend log.",
  },
  DATA_PREP_ERROR: {
    title: "Could not prepare app data",
    detail: "Erudi could not set up its data directory.",
    hint: "Check available disk space and permissions, then relaunch.",
  },
  DATABASE_ERROR: {
    title: "Database error",
    detail: "Erudi's local database failed to start.",
    hint: "Relaunch Erudi; if it persists, check the backend log.",
  },
  CUDA_RUNTIME_ERROR: {
    title: "GPU runtime error",
    detail: "The CUDA runtime failed to initialize.",
    hint: "Update your NVIDIA driver, or use the CPU build of Erudi.",
  },
  MISSING_DEPENDENCY: {
    title: "Missing system dependency",
    detail: "A system library Erudi needs is missing.",
    hint: "Reinstall Erudi, then check the backend log.",
  },
  BACKEND_NOT_FOUND: {
    title: "Backend not found",
    detail: "The bundled backend executable could not be located.",
    hint: "Reinstall Erudi.",
  },
  BACKEND_STARTUP_FAILED: {
    title: "Backend failed to start",
    detail: "The local server could not start after several attempts.",
    hint: "Relaunch Erudi; if it persists, check the backend log.",
  },
  BACKEND_EXIT_ERROR: {
    title: "Backend stopped unexpectedly",
    detail: "The local server process exited with an error.",
    hint: "Relaunch Erudi; if it persists, check the backend log.",
  },
  BACKEND_SPAWN_FAILED: {
    title: "Backend could not be launched",
    detail: "Erudi could not start its local server process.",
    hint: "Reinstall Erudi (or allow it through antivirus/SmartScreen), then relaunch.",
  },
  UNEXPECTED_ERROR: {
    title: "Unexpected startup error",
    detail: "Something went wrong while starting Erudi.",
    hint: "Relaunch Erudi, then check the backend log.",
  },
  POLLING_ERROR: {
    title: "Lost track of the backend",
    detail: "Erudi stopped monitoring the backend during startup.",
    hint: "Relaunch Erudi.",
  },
  // Renderer-side: the /health poll never succeeded within the wait window. This
  // is the catch-all for a silent hang (no startup_error event arrived).
  BACKEND_UNREACHABLE: {
    title: "Can't reach the backend",
    detail: "Erudi's local server isn't responding.",
    hint: "Relaunch Erudi; if it persists, check the backend log.",
  },
};

const FALLBACK = {
  title: "Backend failed to start",
  detail: "Erudi's local server didn't start.",
  hint: "Relaunch Erudi; if it persists, check the backend log.",
};

/**
 * Turn a backend lifecycle event (or a synthetic {code}) into a user-facing
 * descriptor: {code, title, detail, hint, raw}. Unknown/missing codes fall back
 * to a generic descriptor. `raw` carries the backend's own message when present.
 */
export function describeBackendError(evt) {
  const code = (evt && evt.code) || "UNKNOWN";
  const base = MESSAGES[code] || FALLBACK;
  const message = evt && typeof evt.message === "string" ? evt.message.trim() : "";
  return { code, title: base.title, detail: base.detail, hint: base.hint, raw: message || null };
}

/** True when the event signals the backend failed to start. */
export function isStartupError(evt) {
  return !!evt && evt.event === "startup_error";
}

/** True when the event signals the backend is up. */
export function isBackendReady(evt) {
  return !!evt && (evt.event === "ready" || evt.event === "backend_ready");
}
