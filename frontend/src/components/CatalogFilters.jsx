import React from "react";
import PropTypes from "prop-types";
import { SIZE_BUCKETS } from "../utils/hardwareFit";

/**
 * Catalog filters for the browse area: a size bucket plus a "Fits my machine"
 * toggle that leans on the startup benchmark to hide anything that needs more
 * memory. Plain mono chips — no icons — consistent with the search suggestions.
 */
export default function CatalogFilters({ value, onChange, hasRange }) {
  const chip = (active) =>
    `mono text-[11px] rounded-full px-2.5 py-1 border transition-colors ${
      active
        ? "border-[var(--fit-good)] text-[var(--fit-good)] bg-[var(--fit-good)]/10"
        : "border-white/10 text-[var(--ink-dim)] hover:text-[var(--ink)] hover:border-white/20"
    }`;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="mono text-[11px] text-[var(--ink-faint)] mr-1">size</span>
      {SIZE_BUCKETS.map((b) => (
        <button
          key={b.key}
          onClick={() => onChange({ ...value, size: b.key })}
          className={chip(value.size === b.key)}
        >
          {b.label}
        </button>
      ))}
      {hasRange && (
        <>
          <span className="w-px h-4 bg-white/10 mx-1.5" />
          <button
            onClick={() => onChange({ ...value, fitOnly: !value.fitOnly })}
            className={chip(value.fitOnly)}
          >
            Fits my machine
          </button>
        </>
      )}
    </div>
  );
}

CatalogFilters.propTypes = {
  value: PropTypes.shape({ size: PropTypes.string, fitOnly: PropTypes.bool }).isRequired,
  onChange: PropTypes.func.isRequired,
  hasRange: PropTypes.bool,
};
