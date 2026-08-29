import React from "react";
import PropTypes from "prop-types";
import { useTranslation } from "react-i18next";
import { fitForModel, fitForCatalogModel, modelFootprintGb, FIT_META } from "../utils/hardwareFit";
import { formatGigabytes } from "../i18n/format";

/**
 * The signature element: a compact meter showing a model's on-device footprint
 * against the machine's budget. The fill length encodes size; its color encodes
 * fit (mint/amber/rust); the tick marks the user's comfortable ceiling. When no
 * benchmark window is known it renders a neutral, label-only state.
 *
 * The footprint is the measured download size when the backend has it (#397),
 * shown as an exact figure and driving the fill and the verdict alike, so the
 * card face agrees with the info modal and the installed card; the parameter
 * estimate ("~") is the fallback.
 */
export default function FitGauge({ paramSize, quantized, sizeBytes, range, showLabel = true }) {
  const { t } = useTranslation();
  const subject = { param_size: paramSize, quantized, artifact_size_bytes: sizeBytes };
  const fit = fitForCatalogModel(subject, range);
  const footprint = modelFootprintGb(subject);
  const known = fit.tier !== "unknown";
  let footprintLabel = "";
  if (footprint) {
    footprintLabel = footprint.measured
      ? formatGigabytes(footprint.gb)
      : t("models:fit.footprint", { size: formatGigabytes(footprint.gb) });
  }

  return (
    <div className="w-full">
      <div className="relative h-1.5 w-full rounded-full bg-white/[0.06] overflow-hidden">
        <div
          className="absolute inset-y-0 left-0 rounded-full transition-[width] duration-500 ease-out"
          style={{
            width: `${Math.round(fit.fraction * 100)}%`,
            backgroundColor: known ? fit.color : "var(--ink-faint)",
            opacity: known ? 1 : 0.5,
          }}
        />
        {/* Tick at the comfortable ceiling — "your machine's limit". */}
        {known && (
          <div
            className="absolute top-[-2px] bottom-[-2px] w-px bg-white/40"
            style={{ left: `${Math.round(fit.tickFraction * 100)}%` }}
          />
        )}
      </div>
      {showLabel && (
        <div className="mt-1.5 flex items-center justify-between">
          <span
            className="mono text-[11px]"
            style={{ color: known ? fit.color : "var(--ink-faint)" }}
          >
            {known ? fit.label : t("models:fit.labels.unknown")}
          </span>
          <span className="mono text-[11px] text-[var(--ink-faint)]">{footprintLabel}</span>
        </div>
      )}
    </div>
  );
}

FitGauge.propTypes = {
  paramSize: PropTypes.number,
  quantized: PropTypes.bool,
  /** Measured download size (`artifact_size_bytes`); null/absent = use the estimate. */
  sizeBytes: PropTypes.number,
  range: PropTypes.shape({ min: PropTypes.number, max: PropTypes.number }),
  showLabel: PropTypes.bool,
};

/** Small standalone fit dot for dense lists (category cards). */
export function FitDot({ paramSize, range }) {
  const { t } = useTranslation();
  const fit = fitForModel(paramSize, range);
  const title = fit.tier === "unknown" ? t("models:fit.labels.unknown") : fit.label;
  return (
    <span
      className="inline-block w-2 h-2 rounded-full flex-shrink-0"
      style={{ backgroundColor: fit.color, opacity: fit.tier === "unknown" ? 0.4 : 1 }}
      title={title}
      aria-label={title}
    />
  );
}

FitDot.propTypes = {
  paramSize: PropTypes.number,
  range: PropTypes.shape({ min: PropTypes.number, max: PropTypes.number }),
};

export { FIT_META };
