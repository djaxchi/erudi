// Locale-aware model size for the installed cards and the details modal (#387).
//
// The backend's `model_metadata` carries an English "Size: ~0.7 GB" line that
// used to be printed verbatim whatever the app language. The display value is
// now resolved at render time, in order of trust:
//   1. `artifact_size_bytes` — the measured download size (nullable integer
//      exposed on LLMResponse), when it is a positive number;
//   2. the metadata string, re-formatted ("~0.7 GB" -> "~0,7 Go");
//   3. the footprint estimate from the parameter count (`estimateFootprintGb`).
// Anything else yields null so the caller can fall back to what it has.
import { formatNumber, formatGigabytes } from "../i18n/format";
import { estimateFootprintGb, measuredSizeGb } from "./hardwareFit";

// "~3.2 GB", "4.5 GB", "~3.0-4.0 GB" (range estimate). Anything else is null.
const SIZE_RE = /^\s*(~)?\s*(\d+(?:\.\d+)?)(?:\s*-\s*(\d+(?:\.\d+)?))?\s*GB\s*$/i;

export function parseSizeGb(text) {
  if (typeof text !== "string") return null;
  const match = SIZE_RE.exec(text);
  if (!match) return null;
  const minGb = Number(match[2]);
  const maxGb = match[3] === undefined ? minGb : Number(match[3]);
  return { minGb, maxGb, approximate: match[1] === "~" };
}

function formatRange({ minGb, maxGb, approximate }) {
  const prefix = approximate ? "~" : "";
  if (minGb === maxGb) return `${prefix}${formatGigabytes(minGb)}`;
  return `${prefix}${formatNumber(minGb, { maximumFractionDigits: 1 })}-${formatGigabytes(maxGb)}`;
}

export function displayModelSize(model) {
  if (!model) return null;
  const measured = measuredSizeGb(model);
  if (measured !== null) {
    return formatGigabytes(measured);
  }
  const parsed = parseSizeGb(model.size);
  if (parsed) return formatRange(parsed);
  const estimate = estimateFootprintGb(model.param_size, model.quantized);
  if (estimate) return `~${formatGigabytes(estimate)}`;
  return null;
}
