import React from "react";
import PropTypes from "prop-types";
import { useTranslation } from "react-i18next";
import { formatNumber } from "../i18n/format";

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
        {typeof value === "number" ? formatNumber(value) : value}
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

// The backend's inference tiers (global_inference_label). Each maps to a
// translated tier name and a friendly one-liner under the chip name (#199
// follow-up) — fills what was dead space under a short GPU name, and keeps the
// "Weak"/"Poor" tiers from reading like a verdict. Never technical: that's what
// the stats row is for. An unknown label is shown as the backend sent it.
const KNOWN_TIERS = ["excellent", "good", "fair", "poor", "weak"];
const tierKey = (label) => {
  const key = String(label || "").toLowerCase();
  return KNOWN_TIERS.includes(key) ? key : null;
};

export default function MachineReadout({ machine, loading }) {
  const { t } = useTranslation();

  if (loading) {
    return (
      <div className="rounded-2xl border border-[var(--line)] bg-[var(--surface)] h-[132px] flex items-center justify-center">
        <div className="text-[var(--ink-faint)] mono text-xs">
          {t("models:machine.readingHardware")}
        </div>
      </div>
    );
  }

  const m = machine || {};
  const score = Math.round(m.inferenceScore || 0);
  const range = m.range || {};
  const hasRange = typeof range.min === "number" && typeof range.max === "number";
  const tier = tierKey(m.inferenceLabel);
  const tierLabel = tier ? t(`models:machine.tier.${tier}`) : m.inferenceLabel;
  const notAvailable = t("models:machine.notAvailable");

  // Apple Silicon shares one pool between CPU and GPU ("Unified memory"); CPU and
  // CUDA machines expose it as plain system "RAM", and CUDA adds a separate VRAM
  // stat from vram_total_gb (#202).
  const isCuda = m.backend === "CUDA";
  const memoryLabel =
    m.backend === "MLX" ? t("models:machine.unifiedMemory") : t("models:machine.ram");
  const gbUnit = t("common:units.gb");

  return (
    <div className="relative overflow-hidden rounded-2xl border border-[var(--line)] bg-[var(--surface)] rise">
      {/* faint corner glow toward the recommendation — the one thing to look at */}
      <div
        className="pointer-events-none absolute -right-24 -top-24 w-72 h-72 rounded-full blur-3xl"
        style={{ background: "radial-gradient(circle, rgba(52,214,165,0.10), transparent 70%)" }}
      />
      <div className="relative p-5 grid grid-cols-[auto_1fr_auto] items-stretch gap-x-9">
        <div className="min-w-[150px] flex flex-col justify-between">
          <div>
            <div className="eyebrow mb-1.5">{t("models:machine.yourMachine")}</div>
            <div className="text-2xl font-semibold text-[var(--ink)] tracking-tight leading-none">
              {m.chip || t("common:status.unknown")}
            </div>
            <div className="mono text-[11px] text-[var(--ink-dim)] mt-1.5 uppercase tracking-wider">
              {t("models:machine.runtime", { backend: m.backend || "" })}
            </div>
          </div>
          {tier && (
            <div className="text-[12px] text-[var(--ink-dim)] italic">
              {t(`models:machine.catchphrase.${tier}`)}
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-x-8 gap-y-4">
          <Stat value={m.memoryGb} unit={gbUnit} label={memoryLabel} />
          {isCuda && <Stat value={m.vramGb} unit={gbUnit} label={t("models:machine.vram")} />}
          <Stat value={m.gpuCores} label={t("models:machine.gpuCores")} />
          <Stat
            value={m.bandwidth}
            unit={t("models:machine.bandwidthUnit")}
            label={t("models:machine.bandwidth")}
          />
          <Stat
            value={tierLabel || notAvailable}
            unit={`· ${formatNumber(score)}`}
            label={t("models:machine.inference")}
          />
        </div>

        <div className="flex items-end justify-end gap-4 pl-6 sm:border-l border-white/10">
          <div>
            <div className="eyebrow mb-1.5">{t("models:machine.sweetSpot")}</div>
            <div className="flex items-baseline gap-1">
              <span
                className="mono text-3xl font-semibold leading-none"
                style={{ color: "var(--fit-good)" }}
              >
                {hasRange
                  ? t("models:machine.rangeValue", { min: range.min, max: range.max })
                  : notAvailable}
              </span>
              <span className="mono text-sm text-[var(--ink-dim)]">
                {t("models:machine.paramUnit")}
              </span>
            </div>
            <div className="text-[11px] text-[var(--ink-dim)] mt-1.5 max-w-[180px]">
              {hasRange
                ? t("models:machine.comfortable", { max: range.max })
                : t("models:machine.gaugeHint")}
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
