import React, { useState, useEffect, useCallback, useRef } from "react";
import PropTypes from "prop-types";
import { HelpCircle, RefreshCw } from "lucide-react";
import Tooltip from "./Tooltip";
import { getApiBaseUrl } from "../config/api";

/**
 * Live status pill for the bottom of the left rail. Erudi is local-first, so this
 * reads the two REAL signals the backend exposes rather than the browser's
 * `navigator.onLine` (unreliable in Electron -- it stays "online" when the machine
 * is actually offline):
 *
 *   - GET /health/                    -> {status, db: "ok"|"recovering"|"failed"}
 *       Local and cheap; polled often (~15s). Drives the backend-reachable check
 *       and surfaces the DB watchdog state added in #162/#270.
 *   - GET /startup/connection-status  -> {can_download_models: bool, ...}
 *       A real internet round-trip; polled rarely (~45s).
 *
 * Display priority (offline is NOT an error -- local chat keeps working):
 *   1. backend unreachable (health poll fails/times out) -> red + Restart
 *   2. db === "recovering"                                -> amber "Restoring the database..."
 *   3. db === "failed"                                    -> red "Database error" + Restart
 *   4. internet offline (connection-status false)         -> gray "Offline" (informative)
 *   5. all good                                           -> green "Connected"
 *
 * The internet signal is tri-state (true | false | null): a failed or slow
 * connectivity probe becomes `null` (unknown) and NEVER asserts "Offline", so a
 * flaky probe can only ever fall back to the health/db truth, never alarm.
 */

// Poll cadences and per-request client timeouts. Exposed as props so tests can
// drive the state machine on short intervals; production uses the defaults.
const HEALTH_POLL_MS = 15000;
const CONNECTION_POLL_MS = 45000;
const HEALTH_TIMEOUT_MS = 8000;
// Longer than the health timeout: this probe does a real network round-trip. The
// bound exists so a pathologically slow offline probe (captive portal / dropped
// packets) can never wedge the pill -- it aborts and the internet state goes unknown.
const CONNECTION_TIMEOUT_MS = 10000;

/** Map the raw signals to a single visual descriptor, honoring the priority order. */
function resolveDisplay({ backendReachable, dbState, online }) {
  if (!backendReachable) {
    return {
      dot: "bg-red-500",
      label: "Backend unreachable",
      labelClass: "text-red-300",
      showRestart: true,
      title: "The local backend is not responding",
      tooltip: "The local backend stopped responding. Restart it to reconnect.",
    };
  }
  if (dbState === "recovering") {
    return {
      dot: "bg-amber-400",
      ping: "bg-amber-400/60",
      pulse: true,
      label: "Restoring the database...",
      labelClass: "text-amber-300",
      title: "The local database is recovering",
      tooltip: "The local database is restoring. Your data is safe; this clears on its own.",
    };
  }
  if (dbState === "failed") {
    return {
      dot: "bg-red-500",
      label: "Database error",
      labelClass: "text-red-300",
      showRestart: true,
      title: "The local database hit an error",
      tooltip: "The local database hit an error. Restart the backend to recover.",
    };
  }
  if (online === false) {
    return {
      dot: "bg-gray-500",
      label: "Offline",
      labelClass: "text-gray-400",
      title: "No internet connection",
      tooltip:
        "No internet: the catalog and downloads are unavailable, but chatting with installed models still works.",
    };
  }
  return {
    dot: "bg-emerald-400",
    ping: "bg-emerald-400/60",
    pulse: true,
    label: "Connected",
    labelClass: "text-gray-300",
    title: "Connected to the internet",
    tooltip: "You can chat with installed models offline. Installing new ones needs a connection.",
  };
}

export default function ConnectionStatus({
  healthPollMs = HEALTH_POLL_MS,
  connectionPollMs = CONNECTION_POLL_MS,
  healthTimeoutMs = HEALTH_TIMEOUT_MS,
  connectionTimeoutMs = CONNECTION_TIMEOUT_MS,
}) {
  // Optimistic defaults so mounting never flashes an alarming state before the
  // first poll resolves; `online: null` means "internet state not yet known".
  const [status, setStatus] = useState({
    backendReachable: true,
    dbState: "ok",
    online: null,
  });

  // Kept in a ref so the interval callbacks always see the latest timeouts
  // without re-subscribing the effect on every prop identity change.
  const timeoutsRef = useRef({ healthTimeoutMs, connectionTimeoutMs });
  timeoutsRef.current = { healthTimeoutMs, connectionTimeoutMs };

  useEffect(() => {
    let cancelled = false;
    const controllers = new Set();
    // Guards against overlapping requests per signal (a slow poll must not stack
    // on top of the next interval tick).
    const inFlight = { health: false, connection: false };

    async function fetchWithTimeout(path, timeoutMs) {
      const controller = new AbortController();
      controllers.add(controller);
      const timer = setTimeout(() => controller.abort(), timeoutMs);
      try {
        return await fetch(`${getApiBaseUrl()}${path}`, {
          signal: controller.signal,
          cache: "no-store",
        });
      } finally {
        clearTimeout(timer);
        controllers.delete(controller);
      }
    }

    async function pollHealth() {
      if (cancelled || inFlight.health) return;
      inFlight.health = true;
      try {
        const res = await fetchWithTimeout("/health/", timeoutsRef.current.healthTimeoutMs);
        if (!res.ok) throw new Error(`health ${res.status}`);
        const data = await res.json();
        if (cancelled) return;
        const db = data && typeof data.db === "string" ? data.db : "ok";
        setStatus((s) => ({ ...s, backendReachable: true, dbState: db }));
      } catch {
        // Any failure/timeout means the local backend is not answering. A failed
        // poll is a state change, never a crash.
        if (!cancelled) setStatus((s) => ({ ...s, backendReachable: false }));
      } finally {
        inFlight.health = false;
      }
    }

    async function pollConnection() {
      if (cancelled || inFlight.connection) return;
      inFlight.connection = true;
      try {
        const res = await fetchWithTimeout(
          "/startup/connection-status",
          timeoutsRef.current.connectionTimeoutMs
        );
        if (!res.ok) throw new Error(`connection ${res.status}`);
        const data = await res.json();
        if (cancelled) return;
        setStatus((s) => ({ ...s, online: Boolean(data.can_download_models) }));
      } catch {
        // Unknown, not offline: never assert "Offline" off a failed/slow probe.
        if (!cancelled) setStatus((s) => ({ ...s, online: null }));
      } finally {
        inFlight.connection = false;
      }
    }

    // Prime both signals immediately, then settle into their cadences.
    pollHealth();
    pollConnection();
    const healthTimer = setInterval(pollHealth, healthPollMs);
    const connectionTimer = setInterval(pollConnection, connectionPollMs);

    // Browser online/offline events are only an OPTIMISTIC fast-path re-poll
    // trigger -- never the source of truth (they lie in Electron).
    const onNetworkChange = () => {
      pollConnection();
      pollHealth();
    };
    window.addEventListener("online", onNetworkChange);
    window.addEventListener("offline", onNetworkChange);

    return () => {
      cancelled = true;
      clearInterval(healthTimer);
      clearInterval(connectionTimer);
      window.removeEventListener("online", onNetworkChange);
      window.removeEventListener("offline", onNetworkChange);
      controllers.forEach((c) => c.abort());
    };
  }, [healthPollMs, connectionPollMs]);

  const handleRestart = useCallback(() => {
    const pending = window.backendAPI?.restartBackend?.();
    if (pending && typeof pending.catch === "function") pending.catch(() => {});
  }, []);

  const d = resolveDisplay(status);

  return (
    <div className="flex items-center gap-2.5 px-4 py-3 border-t border-white/10" title={d.title}>
      <span className="relative flex w-2.5 h-2.5">
        {d.pulse && (
          <span
            className={`absolute inline-flex w-full h-full rounded-full ${d.ping} animate-ping`}
          />
        )}
        <span className={`relative inline-flex w-2.5 h-2.5 rounded-full ${d.dot}`} />
      </span>
      <span className={`text-sm ${d.labelClass}`}>{d.label}</span>
      {d.showRestart && (
        <button
          type="button"
          onClick={handleRestart}
          title="Restart the backend"
          className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs text-gray-300 hover:text-white hover:bg-white/10 transition-colors"
        >
          <RefreshCw className="w-3 h-3" />
          Restart
        </button>
      )}
      <Tooltip side="top-right" width="w-64" content={d.tooltip}>
        <HelpCircle className="w-3.5 h-3.5 text-gray-400 hover:text-emerald-400 transition-colors cursor-help" />
      </Tooltip>
    </div>
  );
}

ConnectionStatus.propTypes = {
  healthPollMs: PropTypes.number,
  connectionPollMs: PropTypes.number,
  healthTimeoutMs: PropTypes.number,
  connectionTimeoutMs: PropTypes.number,
};
