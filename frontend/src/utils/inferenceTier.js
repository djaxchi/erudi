// The backend's inference tiers (`global_inference_label`, hardware/services.py
// `_get_label`: Excellent / Good / Fair / Poor / Weak). Every surface that shows
// the label maps it to the same translated tier name under
// `models:machine.tier.*` (#387); an unknown label is shown as the backend
// sent it. Translated at call time so a language switch is reflected on the
// next render.
import i18n from "../i18n";

export const KNOWN_TIERS = ["excellent", "good", "fair", "poor", "weak"];

export function inferenceTierKey(label) {
  const key = String(label || "").toLowerCase();
  return KNOWN_TIERS.includes(key) ? key : null;
}

export function inferenceTierLabel(label) {
  if (!label) return null;
  const tier = inferenceTierKey(label);
  return tier ? i18n.t(`models:machine.tier.${tier}`) : label;
}
