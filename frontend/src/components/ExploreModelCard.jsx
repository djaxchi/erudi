import React from "react";
import PropTypes from "prop-types";
import { BadgeCheck, Download, Heart, Image as ImageIcon } from "lucide-react";
import GradientBox from "./GradientBox";
import FitGauge from "./FitGauge";
import { CATEGORY_META } from "../utils/modelCatalog";
import { modelSupportsVision } from "../utils/modelCapabilities";
import { isTestedModel } from "../utils/testedModels";

/**
 * Explore-panel model card. Frosted-glass surface (the look the catalog has always
 * had), no decorative icons — the fit gauge is the only graphic, because "will it
 * run on my machine?" is the one thing a local-LLM user needs at a glance. Name and
 * category up top, the gauge in the middle, monospace metrics, one clear action.
 */
export default function ExploreModelCard({ model, range, onDownload, onInfo }) {
  const unavailable = model?.runnable === false;
  const isVision = modelSupportsVision(model);
  const tested = isTestedModel(model);
  const cat = CATEGORY_META[model.category];
  const params =
    typeof model.param_size === "number"
      ? model.param_size >= 1
        ? `${Number(model.param_size.toFixed(model.param_size < 10 ? 1 : 0))}B`
        : `${Math.round(model.param_size * 1000)}M`
      : null;

  const formatCount = (val) => {
    const n = parseInt(String(val ?? "").replace(/[^\d]/g, ""), 10);
    if (!n) return null;
    if (n >= 1e6) return `${(n / 1e6).toFixed(n >= 1e7 ? 0 : 1).replace(/\.0$/, "")}M`;
    if (n >= 1e3) return `${Math.round(n / 1e3)}k`;
    return String(n);
  };

  const downloads = formatCount(model.downloads);
  const likes = formatCount(model.likes);

  return (
    <GradientBox
      className="h-full bg-[#1a1a1a]/60 backdrop-blur-sm border border-white/10 transition-colors duration-200 hover:border-[var(--fit-good)]/40 after:pointer-events-none after:absolute after:inset-0 after:z-[5] after:bg-[var(--fit-good)] after:opacity-0 after:transition-opacity after:duration-200 hover:after:opacity-[0.07]"
      contentClassName="relative z-10 flex flex-col h-full p-4"
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-1.5 min-w-0">
          <h4 className="text-[15px] font-semibold text-[var(--ink)] leading-snug">{model.name}</h4>
          {tested && (
            <span
              className="flex items-center shrink-0 text-[var(--fit-good)]"
              title="Tested by the Erudi team — verified for chat and Knowledge Base"
            >
              <BadgeCheck className="w-4 h-4" />
            </span>
          )}
        </div>
        {cat && (
          <span className="eyebrow !text-[9px] !tracking-[0.12em] whitespace-nowrap pt-1 text-[var(--ink-faint)]">
            {cat.label}
          </span>
        )}
      </div>

      <FitGauge
        paramSize={model.param_size}
        quantized={model.quantized}
        range={range}
        showLabel={!unavailable}
      />

      {unavailable && (
        <div className="mt-1.5 mono text-[11px] text-[var(--fit-heavy)]">
          Not supported on your hardware
        </div>
      )}

      <div className="mt-auto pt-4">
        <div className="mono text-xs text-[var(--ink-dim)] flex items-center gap-2 mb-2.5">
          {/* Unmeasured size (#201): say so plainly rather than implying a value. */}
          {params ? <span>{params}</span> : <span className="italic">Size unknown</span>}
          {isVision && (
            <span
              className="flex items-center gap-1 text-[var(--fit-good)]"
              title="Supports image input (vision)"
            >
              <ImageIcon className="w-3.5 h-3.5" />
            </span>
          )}
          {downloads && (
            <span className="flex items-center gap-1">
              <Download className="w-3 h-3" />
              <span className="text-[var(--ink)] font-semibold">{downloads}</span>
            </span>
          )}
          {likes && (
            <span className="flex items-center gap-1">
              <Heart className="w-3 h-3" />
              <span className="text-[var(--ink)] font-semibold">{likes}</span>
            </span>
          )}
          {model.gated && <span className="text-[var(--fit-tight)]">gated</span>}
        </div>
        <div className="flex items-center justify-end gap-3">
          <button
            onClick={() => onInfo && onInfo(model)}
            className="text-sm text-[var(--ink-dim)] hover:text-[var(--ink)] transition-colors"
          >
            Details
          </button>
          <button
            onClick={() => !unavailable && onDownload && onDownload(model)}
            disabled={unavailable}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
              unavailable
                ? "opacity-30 cursor-not-allowed text-[var(--ink-dim)]"
                : "bg-[var(--fit-good)] text-[#07241d] hover:brightness-110"
            }`}
          >
            Download
          </button>
        </div>
      </div>
    </GradientBox>
  );
}

ExploreModelCard.propTypes = {
  model: PropTypes.object.isRequired,
  range: PropTypes.shape({ min: PropTypes.number, max: PropTypes.number }),
  onDownload: PropTypes.func,
  onInfo: PropTypes.func,
};
