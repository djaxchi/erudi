import React from "react";
import PropTypes from "prop-types";

/**
 * The panel's thesis: a compact instrument readout of the user's machine, from the
 * startup benchmark. It states the silicon, the memory budget, and the recommended
 * model-size window every card downstream is judged against. Monospace numbers, no
 * icons — the figures themselves carry it, like a spec sheet.
 */
function Stat({ value, unit, label }) {
  if (value === null || value === undefined) {
    return null;
  }
  return (
    <div className="leading-tight">
      <div className="mono text-[var(--ink)] text-[15px]">
        {value}
        {unit && <span className="text-[var(--ink-dim)] text-xs ml-0.5">{unit}</span>}
      </div>
      <div className="eyebrow !text-[10px] !tracking-[0.14em] mt-0.5">{label}</div>
    </div>
  );
}

Stat.propTypes = {
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  unit: PropTypes.string,
  label: PropTypes.string,
};

export default function MachineReadout({ machine, loading }) {
  if (loading) {
    return (
      <div className="rounded-2xl border border-[var(--line)] bg-[var(--surface)] h-[132px] flex items-center justify-center">
        <div className="text-[var(--ink-faint)] mono text-xs">reading hardware…</div>
      </div>
    );
  }

  const m = machine || {};
  const score = Math.round(m.inferenceScore || 0);
  const range = m.range || {};
  const hasRange = typeof range.min === "number" && typeof range.max === "number";

  return (
    <div className="relative overflow-hidden rounded-2xl border border-[var(--line)] bg-[var(--surface)] rise">
      {/* faint corner glow toward the recommendation — the one thing to look at */}
      <div
        className="pointer-events-none absolute -right-24 -top-24 w-72 h-72 rounded-full blur-3xl"
        style={{ background: "radial-gradient(circle, rgba(52,214,165,0.10), transparent 70%)" }}
      />
      <div className="relative p-5 flex flex-wrap items-center gap-x-9 gap-y-5">
        <div className="min-w-[150px]">
          <div className="eyebrow mb-1.5">Your machine</div>
          <div className="text-2xl font-semibold text-[var(--ink)] tracking-tight leading-none">
            {m.chip || "Unknown"}
          </div>
          <div className="mono text-[11px] text-[var(--ink-dim)] mt-1.5 uppercase tracking-wider">
            {m.backend || ""} runtime
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-x-8 gap-y-4">
          <Stat value={m.memoryGb} unit="GB" label="Unified memory" />
          <Stat value={m.gpuCores} label="GPU cores" />
          <Stat value={m.bandwidth} unit="GB/s" label="Bandwidth" />
          <Stat value={m.inferenceLabel || "n/a"} unit={`· ${score}`} label="Inference" />
        </div>

        <div className="ml-auto flex items-center gap-4 pl-6 sm:border-l border-white/10">
          <div>
            <div className="eyebrow mb-1.5">Sweet spot</div>
            <div className="flex items-baseline gap-1">
              <span
                className="mono text-3xl font-semibold leading-none"
                style={{ color: "var(--fit-good)" }}
              >
                {hasRange ? `${range.min}–${range.max}` : "n/a"}
              </span>
              <span className="mono text-sm text-[var(--ink-dim)]">B</span>
            </div>
            <div className="text-[11px] text-[var(--ink-dim)] mt-1.5 max-w-[180px]">
              {hasRange
                ? `Models up to ~${range.max}B run comfortably here.`
                : "Run a model to gauge your fit."}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

MachineReadout.propTypes = {
  machine: PropTypes.object,
  loading: PropTypes.bool,
};
