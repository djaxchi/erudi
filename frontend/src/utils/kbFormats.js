// Supported Knowledge Base upload formats — the single source of truth for both
// the uploader's file picker (`accept`) and its client-side validation, so the
// two can never drift apart again (#133).
//
// Mirrors the backend ingestion extractors (backend/src/ingestion/reader.py); the
// backend stays the authoritative validator and rejects anything it can't extract.
// Images are intentionally excluded: the pipeline accepts them as `pending_vision`
// but produces zero searchable chunks (no OCR tier yet).
export const SUPPORTED_KB_EXTENSIONS = [".pdf", ".txt", ".docx", ".xlsx", ".csv", ".md"];

/** Value for an <input type="file"> `accept` attribute. */
export const KB_ACCEPT_ATTR = SUPPORTED_KB_EXTENSIONS.join(",");

/** Whether a file name has a Knowledge-Base-supported extension (case-insensitive). */
export function isSupportedKbFile(fileName) {
  if (!fileName || typeof fileName !== "string" || !fileName.includes(".")) {
    return false;
  }
  const extension = "." + fileName.split(".").pop().toLowerCase();
  return SUPPORTED_KB_EXTENSIONS.includes(extension);
}
