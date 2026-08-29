/**
 * Reconcile the boot language with the persisted user setting (#385).
 *
 * Called once the backend is ready. Two cases:
 *   - First launch on this machine (no local mirror yet): the boot language
 *     came from the OS locale, so it becomes the persisted setting — pushed
 *     to the backend when it differs from the row's default.
 *   - Later launches: the backend row is the source of truth (the mirror is
 *     only a cache for the boot screen) and is applied locally.
 * Any failure leaves the current language untouched: the UI keeps working
 * in the language it booted in.
 */
import i18n, { hasStoredLanguage, setAppLanguage } from "./index";
import { normalizeLanguage } from "./languages";
import { createLogger } from "../utils/logger";

const log = createLogger("i18n");

export async function syncLanguageWithBackend(client) {
  const current = i18n.language;
  try {
    const settings = await client.get("/user_settings/");
    const persisted = normalizeLanguage(settings?.language);

    if (!hasStoredLanguage()) {
      if (persisted !== current) {
        await client.put("/user_settings/", { language: current });
      }
      return setAppLanguage(current);
    }

    if (persisted && persisted !== current) {
      return setAppLanguage(persisted);
    }
    return setAppLanguage(current);
  } catch (error) {
    log.warn("Could not sync the interface language with the backend", error);
    return current;
  }
}
