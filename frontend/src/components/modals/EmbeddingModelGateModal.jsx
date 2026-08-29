import React from "react";
import { useTranslation } from "react-i18next";
import { Loader2, Database, CheckCircle2, AlertTriangle } from "lucide-react";
import { GATE } from "../../utils/embeddingGate";

// Blocking, backdrop-blurred gate over the Knowledge Base page (#146). The KB
// needs the e5 embedding model on disk; this prompts an on-demand download and
// blocks the page until the model is present. Not dismissible by clicking the
// backdrop — "Not now" leaves the KB page (onLeave); once downloaded, "Close"
// (onClose) stays on the now-usable KB.
// Positioned absolute: it must be rendered inside a `relative` container that
// wraps only the KB content, so the sidebar stays usable during a download.
export default function EmbeddingModelGateModal({ state, error, onDownload, onLeave, onClose }) {
  const { t } = useTranslation();
  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-md">
      <div className="w-[92%] max-w-md rounded-2xl border border-[#385B4F] bg-[#0e2621] p-6 text-white shadow-2xl">
        {state === GATE.PROMPT && (
          <>
            <div className="mb-3 flex items-center gap-2 text-emerald-300">
              <Database size={20} />
              <h2 className="text-lg font-semibold">{t("downloads:embeddingGate.promptTitle")}</h2>
            </div>
            <p className="mb-6 text-sm text-gray-300">{t("downloads:embeddingGate.promptBody")}</p>
            <div className="flex justify-end gap-3">
              <button
                onClick={onLeave}
                className="rounded-lg px-4 py-2 text-sm text-gray-300 hover:bg-white/10"
              >
                {t("downloads:embeddingGate.notNow")}
              </button>
              <button
                onClick={onDownload}
                className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium hover:bg-emerald-500"
              >
                {t("common:actions.download")}
              </button>
            </div>
          </>
        )}

        {state === GATE.DOWNLOADING && (
          <div className="flex flex-col items-center gap-4 py-4 text-center">
            <Loader2 className="animate-spin text-emerald-300" size={36} />
            <p className="text-sm text-gray-300">{t("downloads:embeddingGate.downloadingBody")}</p>
          </div>
        )}

        {state === GATE.DONE && (
          <>
            <div className="mb-3 flex items-center gap-2 text-emerald-300">
              <CheckCircle2 size={20} />
              <h2 className="text-lg font-semibold">{t("downloads:embeddingGate.doneTitle")}</h2>
            </div>
            <p className="mb-6 text-sm text-gray-300">{t("downloads:embeddingGate.doneBody")}</p>
            <div className="flex justify-end">
              <button
                onClick={onClose}
                className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium hover:bg-emerald-500"
              >
                {t("common:actions.close")}
              </button>
            </div>
          </>
        )}

        {state === GATE.ERROR && (
          <>
            <div className="mb-3 flex items-center gap-2 text-amber-300">
              <AlertTriangle size={20} />
              <h2 className="text-lg font-semibold">{t("downloads:embeddingGate.errorTitle")}</h2>
            </div>
            <p className="mb-2 text-sm text-gray-300">{t("downloads:embeddingGate.errorBody")}</p>
            {error && <p className="mb-6 break-words text-xs text-gray-500">{error}</p>}
            <div className="flex justify-end gap-3">
              <button
                onClick={onLeave}
                className="rounded-lg px-4 py-2 text-sm text-gray-300 hover:bg-white/10"
              >
                {t("downloads:embeddingGate.notNow")}
              </button>
              <button
                onClick={onDownload}
                className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium hover:bg-emerald-500"
              >
                {t("common:actions.retry")}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
