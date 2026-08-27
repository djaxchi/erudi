// Download lifecycle helpers shared by the download modal context and its consumers.
//
// A user-initiated cancel was being reported through the same `onError` callback as
// a real failure, so cancelling a download showed a misleading "Download failed"
// dialog (#133). Centralizing the status string + the error-vs-cancel decision here
// keeps the two paths distinct and testable.

import i18n from "../i18n";

/** The status a cancelled download job reports (backend + poll path). */
export const DOWNLOAD_CANCELLED = "cancelled";

/**
 * Client-side status for a job that stopped making progress in a NON-terminal
 * state (#315). Never reported by the backend: the poll gives up on it so the
 * UI cannot spin forever waiting for a response that may never come.
 */
export const DOWNLOAD_STALLED = "stalled";

/**
 * Shown when the transfer finished but the job never reached a terminal state.
 * Deliberately not phrased as a failure: the weights are on disk, only the
 * finalization bookkeeping did not complete (#291), so telling the user the
 * download failed would be wrong. Resolved at call time so it follows the
 * active app language (#385).
 */
export function downloadStalledMessage() {
  return i18n.t("downloads:errors.stalled");
}

/**
 * Map a download `onError` reason to a user-facing message, or `null` when there is
 * nothing to show (a cancellation is not a failure).
 */
export function downloadErrorMessage(reason) {
  if (reason === DOWNLOAD_CANCELLED) return null;
  if (reason === DOWNLOAD_STALLED) return downloadStalledMessage();
  return i18n.t("downloads:errors.failedRetry");
}
