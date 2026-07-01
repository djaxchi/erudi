import React, { useEffect, useState } from "react";
import PropTypes from "prop-types";

/**
 * Full-screen fallback shown when the local backend fails to start (or never
 * becomes reachable), instead of leaving the user on an endless loading spinner.
 * The descriptor comes from `describeBackendError` (utils/backendStatus).
 */
export default function BackendErrorScreen({ error, onRetry, onQuit }) {
  const { title, detail, hint, raw, code } = error || {};
  // Resolve the OS-correct backend log path from the main process (Windows
  // %TEMP%\erudi-backend.log vs POSIX /tmp/erudi-backend.log) — never hardcode it.
  const [logPath, setLogPath] = useState(null);
  useEffect(() => {
    let cancelled = false;
    window.backendAPI
      ?.getLogPath?.()
      .then((p) => {
        if (!cancelled) setLogPath(p);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div
      className="fixed top-0 left-0 w-screen h-screen flex flex-col justify-center items-center z-[9999] px-8 text-center"
      style={{ backgroundColor: "#02130e" }}
    >
      <img
        src={require("../assets/images/logos/logoerudifinal.png")}
        alt="erudi Logo"
        className="mb-4 object-contain opacity-90"
        style={{ maxWidth: "8rem", maxHeight: "8rem" }}
      />
      <h1 className="text-2xl font-semibold mb-2" style={{ color: "#f4f4f4" }}>
        {title || "Backend failed to start"}
      </h1>
      {detail && (
        <p className="text-base mb-1 max-w-md" style={{ color: "#cfd8d4" }}>
          {detail}
        </p>
      )}
      {hint && (
        <p className="text-sm mb-4 max-w-md" style={{ color: "#9fb0aa" }}>
          {hint}
        </p>
      )}
      {raw && (
        <pre
          className="text-xs mb-4 max-w-lg overflow-auto whitespace-pre-wrap rounded-md px-3 py-2"
          style={{ color: "#8aa39b", backgroundColor: "#04211799" }}
        >
          {raw}
        </pre>
      )}
      <div className="flex gap-3">
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="px-5 py-2 rounded-lg font-medium transition-opacity hover:opacity-90"
            style={{ backgroundColor: "#34d399", color: "#02130e" }}
          >
            Retry
          </button>
        )}
        {onQuit && (
          <button
            type="button"
            onClick={onQuit}
            className="px-5 py-2 rounded-lg font-medium border transition-opacity hover:opacity-90"
            style={{ borderColor: "#2f4a40", color: "#cfd8d4" }}
          >
            Quit
          </button>
        )}
      </div>
      <p className="text-[10px] mt-6 opacity-60 max-w-lg" style={{ color: "#7c8f88" }}>
        {code ? `Error code: ${code} · ` : ""}
        {logPath
          ? `Check the logs in ${logPath} and contact us.`
          : "Check the backend logs and contact us."}
      </p>
    </div>
  );
}

BackendErrorScreen.propTypes = {
  error: PropTypes.shape({
    title: PropTypes.string,
    detail: PropTypes.string,
    hint: PropTypes.string,
    raw: PropTypes.string,
    code: PropTypes.string,
  }),
  onRetry: PropTypes.func,
  onQuit: PropTypes.func,
};
