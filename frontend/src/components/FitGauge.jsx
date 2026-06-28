import React from "react";
import PropTypes from "prop-types";
import { fitForModel, estimateFootprintGb, FIT_META } from "../utils/hardwareFit";

/**
 * The signature element: a compact meter showing a model's on-device footprint
 * against the machine's budget. The fill length encodes size; its color encodes
 * fit (mint/amber/rust); the tick marks the user's comfortable ceiling. When no
 * benchmark window is known it renders a neutral, label-only state.
 */
export default function FitGauge({ paramSize, quantized, range, showLabel = true }) {
  const fit = fitForModel(paramSize, range);
  const footprint = estimateFootprintGb(paramSize, quantized);
  const known = fit.tier !== "unknown";

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
            {known ? fit.label : "Fit unknown"}
          </span>
          <span className="mono text-[11px] text-[var(--ink-faint)]">
            {footprint ? `~${footprint.toFixed(1)} GB` : ""}
          </span>
        </div>
      )}
    </div>
  );
}

FitGauge.propTypes = {
  paramSize: PropTypes.number,
  quantized: PropTypes.bool,
  range: PropTypes.shape({ min: PropTypes.number, max: PropTypes.number }),
  showLabel: PropTypes.bool,
};

/** Small standalone fit dot for dense lists (category cards). */
export function FitDot({ paramSize, range }) {
  const fit = fitForModel(paramSize, range);
  const title = fit.tier === "unknown" ? "Fit unknown" : fit.label;
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
