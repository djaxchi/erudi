import React, { useState, useEffect } from "react";
import { Download, RefreshCw, X } from "lucide-react";
import { Trans, useTranslation } from "react-i18next";
import { formatPercent } from "../i18n/format";

/**
 * Non-intrusive update notification banner.
 *
 * Lifecycle:
 *   1. Hidden until main process emits "update-available"
 *   2. Shows "Downloading vX.Y.Z…" with progress during download
 *   3. Shows "Restart to install" button once download is complete
 *   4. User can dismiss — they'll get the update on next natural quit anyway
 *      (autoInstallOnAppQuit is enabled in main.js)
 */
export default function UpdateBanner() {
  const { t } = useTranslation();
  const [state, setState] = useState(null);
  // state shape:
  //   { phase: "available", version }
  //   { phase: "downloading", version, percent }
  //   { phase: "ready", version }

  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const handlePayload = (payload) => {
      switch (payload.event) {
        case "update-available":
          setState({ phase: "available", version: payload.version });
          setDismissed(false);
          break;
        case "download-progress":
          setState((prev) => ({
            phase: "downloading",
            version: prev?.version ?? "",
            percent: payload.percent,
          }));
          break;
        case "update-downloaded":
          setState({ phase: "ready", version: payload.version });
          break;
        default:
          break;
      }
    };

    // Production: receive events from main process via preload bridge
    let cleanupIPC = null;
    if (window.updaterAPI) {
      cleanupIPC = window.updaterAPI.onUpdaterEvent(handlePayload);
    }

    // DEV TESTING ONLY — remove before shipping.
    // In the browser console, trigger any phase with:
    //   window.dispatchEvent(new CustomEvent("__test_updater__", { detail: { event: "update-available", version: "1.2.0" } }))
    //   window.dispatchEvent(new CustomEvent("__test_updater__", { detail: { event: "download-progress", version: "1.2.0", percent: 60 } }))
    //   window.dispatchEvent(new CustomEvent("__test_updater__", { detail: { event: "update-downloaded", version: "1.2.0" } }))
    const testHandler = (e) => handlePayload(e.detail);
    window.addEventListener("__test_updater__", testHandler);

    return () => {
      if (cleanupIPC) {
        cleanupIPC();
      }
      window.removeEventListener("__test_updater__", testHandler);
    };
  }, []);

  if (!state || dismissed) {
    return null;
  }

  const handleInstall = () => {
    window.updaterAPI?.installNow();
  };

  return (
    <div
      className={[
        "fixed bottom-4 right-4 z-50 flex items-center gap-3 px-4 py-3 rounded-xl",
        "bg-[rgba(22,40,36,0.92)] backdrop-blur-[12px] saturate-[1.3]",
        "border border-[#00B574]/30",
        "shadow-[0_4px_20px_rgba(0,0,0,0.4)]",
        "text-sm text-white max-w-sm",
        "animate-in slide-in-from-bottom-2 duration-300",
      ].join(" ")}
    >
      {/* Icon */}
      <div className="shrink-0">
        {state.phase === "ready" ? (
          <RefreshCw className="w-4 h-4 text-[#00B574]" />
        ) : (
          <Download className="w-4 h-4 text-[#00B574]" />
        )}
      </div>

      {/* Text + progress */}
      <div className="flex-1 min-w-0">
        {state.phase === "available" && (
          <p className="text-gray-200">
            <Trans
              i18nKey="common:update.available"
              values={{ version: state.version }}
              components={{ v: <span className="text-[#00B574] font-semibold" /> }}
            />
          </p>
        )}

        {state.phase === "downloading" && (
          <>
            <p className="text-gray-200 mb-1">
              <Trans
                i18nKey="common:update.downloading"
                values={{ version: state.version, percent: formatPercent(state.percent) }}
                components={{
                  v: <span className="text-[#00B574] font-semibold" />,
                  pct: <span className="text-gray-400" />,
                }}
              />
            </p>
            <div className="w-full h-1 bg-white/10 rounded-full overflow-hidden">
              <div
                className="h-full bg-[#00B574] rounded-full transition-all duration-300"
                style={{ width: `${state.percent}%` }}
              />
            </div>
          </>
        )}

        {state.phase === "ready" && (
          <p className="text-gray-200">
            <Trans
              i18nKey="common:update.ready"
              values={{ version: state.version }}
              components={{
                v: <span className="text-[#00B574] font-semibold" />,
                install: (
                  <button
                    onClick={handleInstall}
                    className="underline text-[#00B574] hover:text-white transition-colors"
                  />
                ),
              }}
            />
          </p>
        )}
      </div>

      {/* Dismiss — only on "available" and "ready" phases; not during download */}
      {state.phase !== "downloading" && (
        <button
          onClick={() => setDismissed(true)}
          className="shrink-0 text-gray-500 hover:text-gray-300 transition-colors"
          aria-label={t("common:update.dismiss")}
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}
