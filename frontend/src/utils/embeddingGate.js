// Embedding-model gate state machine (#146).
//
// The Knowledge Base needs the e5 embedding model on disk. This pure reducer
// derives what the gate modal should show from a backend status snapshot
// ({ available, downloading, error }) plus the previous state. Presence
// ("available") is the source of truth — never a DB flag — so the modal
// self-heals across backend restarts and partial downloads.

export const GATE = {
  CHECKING: "checking", // initial, before the first status is known
  PROMPT: "prompt", // model absent, idle -> offer to download
  DOWNLOADING: "downloading", // background download in flight -> spinner
  DONE: "done", // just finished -> success + Close
  ERROR: "error", // last download failed -> message + retry
  HIDDEN: "hidden", // model present (or dismissed) -> no modal
};

/**
 * Derive the next gate state from a backend status + the previous state.
 * "done" is only reached from an active download, so opening the KB with the
 * model already present goes straight to hidden (no modal flash).
 * @param {{available?: boolean, downloading?: boolean, error?: string|null}} status
 * @param {string} prev
 */
export function gateStateFromStatus(status, prev) {
  const { available, downloading, error } = status || {};
  if (available) {
    return prev === GATE.DOWNLOADING ? GATE.DONE : GATE.HIDDEN;
  }
  if (downloading) return GATE.DOWNLOADING;
  if (error) return GATE.ERROR;
  return GATE.PROMPT;
}

/** Keep polling only while a download is in flight. */
export function shouldPoll(state) {
  return state === GATE.DOWNLOADING;
}

/** Is the modal covering (and blocking) the KB page? */
export function isGateBlocking(state) {
  return state !== GATE.HIDDEN && state !== GATE.CHECKING;
}
