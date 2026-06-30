// Download lifecycle helpers shared by the download modal context and its consumers.
//
// A user-initiated cancel was being reported through the same `onError` callback as
// a real failure, so cancelling a download showed a misleading "Download failed"
// dialog (#133). Centralizing the status string + the error-vs-cancel decision here
// keeps the two paths distinct and testable.

/** The status a cancelled download job reports (backend + poll path). */
export const DOWNLOAD_CANCELLED = "cancelled";

/**
 * Map a download `onError` reason to a user-facing message, or `null` when there is
 * nothing to show (a cancellation is not a failure).
 */
export function downloadErrorMessage(reason) {
  if (reason === DOWNLOAD_CANCELLED) return null;
  return "Download failed. Please try again.";
}
