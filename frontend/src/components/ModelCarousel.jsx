import React, { useState } from "react";
import PropTypes from "prop-types";
import ExploreModelCard from "./ExploreModelCard";

/**
 * One capability's models as a horizontal carousel that scans quickly, with a
 * "See all" that expands into the full wrapped grid. The collapsed row keeps the
 * page calm; the right-edge fade hints there's more to scroll.
 */
export default function ModelCarousel({ id, label, models, range, onDownload, onInfo }) {
  const [expanded, setExpanded] = useState(false);
  if (!models || models.length === 0) {
    return null;
  }
  const canExpand = models.length > 4;

  return (
    <div id={id} className="scroll-mt-6">
      <div className="flex items-center gap-3 mb-3">
        <span className="eyebrow">{label}</span>
        <span className="mono text-[11px] text-[var(--ink-faint)]">
          {String(models.length).padStart(2, "0")}
        </span>
        <span className="h-px flex-1 bg-white/10" />
        {canExpand && (
          <button
            onClick={() => setExpanded((e) => !e)}
            className="mono text-[11px] text-[var(--ink-dim)] hover:text-[var(--fit-good)] transition-colors"
          >
            {expanded ? "Show less" : "See all"}
          </button>
        )}
      </div>

      {expanded ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
          {models.map((model) => (
            <ExploreModelCard
              key={model.id ?? model.link}
              model={model}
              range={range}
              onDownload={onDownload}
              onInfo={onInfo}
            />
          ))}
        </div>
      ) : (
        <div className="relative">
          <div className="flex gap-3 overflow-x-auto scrollbar-hide snap-x snap-mandatory pb-1 -mx-1 px-1">
            {models.map((model) => (
              <div key={model.id ?? model.link} className="snap-start shrink-0 w-[300px]">
                <ExploreModelCard
                  model={model}
                  range={range}
                  onDownload={onDownload}
                  onInfo={onInfo}
                />
              </div>
            ))}
          </div>
          {models.length > 3 && (
            <div className="pointer-events-none absolute right-0 top-0 bottom-1 w-20 bg-gradient-to-l from-[var(--canvas)] to-transparent" />
          )}
        </div>
      )}
    </div>
  );
}

ModelCarousel.propTypes = {
  id: PropTypes.string,
  label: PropTypes.string.isRequired,
  models: PropTypes.array.isRequired,
  range: PropTypes.shape({ min: PropTypes.number, max: PropTypes.number }),
  onDownload: PropTypes.func,
  onInfo: PropTypes.func,
};
