// Post-`ready` health confirmation.
//
// Readiness itself is event-driven (main.js waits for the backend's `ready`
// JSON event, patiently, up to a first-run-aware cap — a slow boot is never a
// failure). Once `ready` arrives, we still do ONE confirming HTTP GET so the
// renderer proves it can actually reach the server on the resolved port (this
// catches port mismatches / loopback / firewall issues). If it doesn't answer
// immediately we retry with backoff — these retries hit the HTTP endpoint only,
// the backend process stays up (never respawned here).

import { HEALTH_CONFIRM_BACKOFF_MS } from "./backendRetry.js";

const defaultSleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Confirm the backend answers a health request, retrying with backoff.
 *
 * @param {object}   opts
 * @param {function} opts.fetchFn  async (url) => Response-like ({ ok })
 * @param {string}   opts.url      health URL to GET
 * @param {function} [opts.sleepFn] async (ms) => void (injectable for tests)
 * @param {number[]} [opts.backoff] backoff waits between attempts (ms)
 * @returns {Promise<boolean>} true if a health check succeeded within budget
 */
export async function confirmBackendHealth({
  fetchFn,
  url,
  sleepFn = defaultSleep,
  backoff = HEALTH_CONFIRM_BACKOFF_MS,
}) {
  const attempts = backoff.length + 1; // one initial try, then one per backoff step
  for (let i = 0; i < attempts; i++) {
    try {
      const res = await fetchFn(url);
      if (res && res.ok) return true;
    } catch {
      // not reachable yet — fall through to backoff
    }
    if (i < backoff.length) {
      await sleepFn(backoff[i]);
    }
  }
  return false;
}
