/**
 * Whether this machine is on a network, decided without sending anything.
 *
 * Two signals feed it, and neither costs a request:
 *
 *   - `navigator.onLine` and the `online` / `offline` window events, which are
 *     the operating system's own view of the link. They change the instant the
 *     link does, where a poll would take up to its interval to notice.
 *   - The requests the app already makes when the user acts. `navigator.onLine`
 *     answers "is there a link", not "is the internet reachable", so a request
 *     that dies at the network layer is the stronger evidence and overrides it;
 *     a request that goes through clears the flag again.
 *
 * Deliberately not here: any request made only to answer this question. The app
 * is local-first, and a heartbeat to a third party would tell that third party
 * when the user's machine is running Erudi.
 */

// True once a request failed at the network layer, until one succeeds or the OS
// reports a fresh link.
let lastRequestFailed = false;
const listeners = new Set();

/** The OS view of the link. Absent navigator (non-browser): assume a link. */
function linkIsUp() {
  return typeof navigator === "undefined" || navigator.onLine !== false;
}

/** Current connectivity as the app understands it. */
export function isNetworkOnline() {
  return linkIsUp() && !lastRequestFailed;
}

function emit() {
  const online = isNetworkOnline();
  for (const listener of listeners) listener(online);
}

/**
 * Record that a request failed at the network layer (no response at all, as
 * opposed to an HTTP error, which proves the path works).
 */
export function reportNetworkFailure() {
  if (lastRequestFailed) return;
  lastRequestFailed = true;
  emit();
}

/** Record that a request completed, clearing any earlier network failure. */
export function reportNetworkSuccess() {
  if (!lastRequestFailed) return;
  lastRequestFailed = false;
  emit();
}

// Attached once, for the life of the renderer rather than of a subscriber: the
// state has to stay right even while nothing is watching, or a component that
// mounts later would inherit a failure the OS has since contradicted.
if (typeof window !== "undefined") {
  window.addEventListener("online", () => {
    // A fresh link supersedes whatever a request said before it dropped.
    lastRequestFailed = false;
    emit();
  });
  window.addEventListener("offline", emit);
}

/**
 * Watch connectivity. The listener is called with the new value whenever it
 * changes, never on subscription -- read `isNetworkOnline()` for the initial
 * state.
 * @param {(online: boolean) => void} listener
 * @returns {() => void} Unsubscribe.
 */
export function subscribeNetworkStatus(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
