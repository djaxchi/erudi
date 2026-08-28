// Global vitest setup: initialize i18next synchronously in English so every
// component test renders the exact English copy the assertions expect, with
// no provider wiring per test. Tests that exercise other languages call
// `i18n.changeLanguage` themselves and reset in their own hooks.
import i18n from "../i18n";

if (i18n.language !== "en") {
  i18n.changeLanguage("en");
}
