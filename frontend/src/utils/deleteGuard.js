// Guarded model delete helpers (#225/#317), shared by every delete surface
// (installed cards on the landing page, left-rail Local Models list).
//
// A base-model delete is guarded server-side: DELETE without
// `?orphan_dependents=true` answers 409 with the dependents payload when KB
// assistants share the base's weights. The UI mirrors that truth: it
// pre-checks GET /llms/{id}/dependents to open the guard dialog up front, and
// parses the 409 payload as the safety net when the pre-check raced or failed.
// KB assistants are NEVER guarded — deleting one is a direct 200 that frees
// nothing (the weights belong to its base).

import { API_BASE_URL } from "../config/api";
import { tracedFetch } from "../services/api/client";
import { isKbAssistant } from "./modelWeights";
import { createLogger } from "./logger";

const log = createLogger("deleteGuard");

// Pre-check the dependents of a model about to be deleted. Returns the
// dependents payload (GET /llms/{id}/dependents shape) when the model is a
// base with at least one dependent assistant, else null. Best-effort: any
// failure returns null so the plain dialog opens and the DELETE's 409 stays
// the safety net. KB assistants skip the request entirely.
export async function fetchDeleteDependents(model) {
  if (!model || isKbAssistant(model)) {
    return null;
  }
  try {
    const response = await tracedFetch(`${API_BASE_URL}/llms/${model.id}/dependents`);
    if (response.ok) {
      const data = await response.json();
      if (data && Array.isArray(data.assistants) && data.assistants.length > 0) {
        return data;
      }
    }
  } catch (error) {
    log.warn("Dependents pre-check failed, falling back to the plain dialog:", error);
  }
  return null;
}

// Extract the dependents payload from a guarded-delete 409 response. The
// backend shape is { success, error: { type, message, detail } } with detail
// carrying the same dependents structure as the pre-check. Returns null when
// the payload is absent or unusable (e.g. a 409 for another reason), so the
// caller falls through to its error path instead of staying silent.
export async function parseConflictDependents(response) {
  let detail = null;
  try {
    const body = await response.json();
    detail = body?.error?.detail ?? body?.detail ?? null;
  } catch (parseError) {
    log.error("Could not parse the delete-conflict payload:", parseError);
  }
  if (detail && Array.isArray(detail.assistants) && detail.assistants.length > 0) {
    return detail;
  }
  return null;
}
