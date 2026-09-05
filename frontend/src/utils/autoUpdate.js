/**
 * Bridge the persisted automatic-update preference to the Electron main process.
 *
 * electron-updater lives in main, which has no access to the database; the
 * preference lives in the user-settings singleton, which only the renderer
 * reads. This carries one across to the other: main holds its update checks
 * until it is told, so a user who refused updates never sees a request leave
 * the machine, and everyone else keeps the behaviour they always had.
 *
 * Enabled is the answer whenever the setting cannot be read -- a backend
 * hiccup must not quietly strand an install on an old version.
 */
import { createLogger } from "./logger";

const log = createLogger("autoUpdate");

/**
 * Read the persisted preference and push it to main.
 * @param {{get: Function}} client - API client (apiClient in the app).
 * @returns {Promise<boolean>} The preference that was applied.
 */
export async function syncAutoUpdateWithMain(client) {
  let enabled = true;
  try {
    const settings = await client.get("/user_settings/");
    enabled = settings?.auto_update_enabled !== false;
  } catch (error) {
    log.warn("Could not read the automatic-update setting; updates stay enabled", error);
  }
  notifyAutoUpdatePreference(enabled);
  return enabled;
}

/**
 * Push a preference to main without reading it back from the backend. Used by
 * the Settings toggle, which already knows the value it just persisted.
 * @param {boolean} enabled - Whether updates may be checked and installed.
 */
export function notifyAutoUpdatePreference(enabled) {
  window.updaterAPI?.setAutoUpdateEnabled?.(enabled);
}
