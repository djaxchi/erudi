// src/contexts/DownloadModalContext.jsx
import React, { createContext, useContext, useState, useCallback, useRef } from "react";
import ReactDOM from "react-dom";
import ConfirmationModal from "../components/modals/ConfirmationModal";
import ErrorModal from "../components/modals/ErrorModal";
import SpinnerDots from "../components/Spinner";
import { X, ChevronLeft, ChevronRight } from "lucide-react";
import { API_BASE_URL } from "../config/api.js";
import { tracedFetch } from "../services/api/client";
import { createLogger } from "../utils/logger";
import { DOWNLOAD_CANCELLED } from "../utils/downloadStatus";
const log = createLogger("DownloadModalContext");

const DownloadModalContext = createContext();

// Helper function to format time with appropriate units
const formatTimeLeft = (seconds) => {
  if (!seconds || seconds <= 0) {
    return "--";
  }

  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (days > 0) {
    return `${days}d ${hours}h`;
  } else if (hours > 0) {
    return `${hours}h ${minutes}m`;
  } else if (minutes > 0) {
    return `${minutes}m ${secs}s`;
  } else {
    return `${secs}s`;
  }
};

export function DownloadModalProvider({ children }) {
  const [model, setModel] = useState(null);
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(true);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState("idle");
  const [timeLeft, setTimeLeft] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [jobId, setJobId] = useState(null);
  // Completion exposed as observable context STATE, not only as a stored callback.
  // A per-download onComplete can be overwritten by another opener (the ref is a
  // singleton) or lost when the page that registered it unmounts mid-download.
  // A monotonic counter lets any mounted consumer react to "a download finished"
  // regardless of who started it or whether it remounted since (#205).
  const [completionCount, setCompletionCount] = useState(0);
  const [lastCompletedAt, setLastCompletedAt] = useState(null);

  const intervalRef = useRef(null);
  const callbacksRef = useRef({ onComplete: null, onError: null });

  const toggleCollapse = useCallback(() => {
    setIsCollapsed((c) => !c);
  }, []);

  const open = useCallback((selectedModel, { onComplete, onError } = {}) => {
    setModel(selectedModel);
    callbacksRef.current = { onComplete, onError };
    setErrorMessage("");
    setIsConfirmOpen(true);
  }, []);

  const cancelConfirm = useCallback(() => setIsConfirmOpen(false), []);

  const checkDownloadStatus = useCallback(async (id) => {
    try {
      const res = await tracedFetch(`${API_BASE_URL}/llms/downloads/${id}/status`);
      if (!res.ok) {
        if (res.status === 404) {
          // Le job n'existe plus (probablement annulé et nettoyé)
          clearInterval(intervalRef.current);
          setIsDownloading(false);
          setProgress(0);
          setStatus(DOWNLOAD_CANCELLED);
          return;
        }
        throw new Error(`Server responded with ${res.status}: ${res.statusText}`);
      }
      const data = await res.json();
      setProgress(data.progress);
      setStatus(data.status);
      setTimeLeft(data.time_left);

      if (
        data.status === "completed" ||
        data.status === "failed" ||
        data.status === DOWNLOAD_CANCELLED
      ) {
        clearInterval(intervalRef.current);
        setIsDownloading(false);
        if (data.status === "completed") {
          setCompletionCount((c) => c + 1);
          setLastCompletedAt(Date.now());
          callbacksRef.current.onComplete?.();
        } else if (data.status === DOWNLOAD_CANCELLED) {
          callbacksRef.current.onError?.(DOWNLOAD_CANCELLED);
        } else {
          const errorMsg = data.error_message || "Download failed unexpectedly";
          setErrorMessage(errorMsg);
          callbacksRef.current.onError?.(errorMsg);
        }
      }
    } catch (err) {
      log.error("Status check error:", err);
      clearInterval(intervalRef.current);
      setIsDownloading(false);
      const errorMsg =
        "An error occured during download. Please check your connection and try again. If the problem persists, please contact the Erudi team.";
      setErrorMessage(errorMsg);
      callbacksRef.current.onError?.(errorMsg);
    }
  }, []);

  const handleConfirm = useCallback(async () => {
    setIsConfirmOpen(false);
    setIsDownloading(true);
    setStatus("pending");
    setProgress(0);
    setErrorMessage("");

    setTimeout(() => setIsCollapsed(false), 2000);

    try {
      // Catalog models download by id; HF live-search hits have no id, so they
      // download by repo link via the dedicated endpoint (#122). Either way the
      // backend returns a DownloadJob we poll identically.
      const res =
        typeof model.id === "number"
          ? await tracedFetch(`${API_BASE_URL}/llms/${model.id}/download`, { method: "POST" })
          : await tracedFetch(`${API_BASE_URL}/llms/download/huggingface`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                link: model.link,
                name: model.name,
                type: model.type || null,
                // Preserve an unmeasured size as null instead of laundering it into
                // a plausible 7.0 (#201); the backend stores NULL = size unknown.
                param_size: model.param_size ?? null,
                quantized: model.quantized !== false,
                category: model.category || "general",
              }),
            });
      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(`Failed to start download (${res.status}): ${errorText}`);
      }
      const job = await res.json();

      // Sauvegarder le jobId pour l'annulation
      setJobId(job.id);

      intervalRef.current = setInterval(() => {
        checkDownloadStatus(job.id);
      }, 2000);
    } catch (err) {
      log.error("Download start error:", err);
      const errorMsg = err.message || err.toString() || "An unexpected error occurred";
      setErrorMessage(errorMsg);
      setIsDownloading(false);
      callbacksRef.current.onError?.(errorMsg);
    }
  }, [model, checkDownloadStatus]);

  const cancelDownload = useCallback(async () => {
    if (!jobId) {
      // Si pas de jobId, on fait juste le nettoyage local
      clearInterval(intervalRef.current);
      setIsDownloading(false);
      setProgress(0);
      setStatus(DOWNLOAD_CANCELLED);
      callbacksRef.current.onError?.(DOWNLOAD_CANCELLED);
      return;
    }

    try {
      // Appeler l'endpoint d'annulation
      const response = await tracedFetch(`${API_BASE_URL}/llms/downloads/${jobId}/cancel`, {
        method: "POST",
      });

      if (!response.ok) {
        throw new Error(`Server responded with ${response.status}: ${response.statusText}`);
      }

      setStatus("cancelling");
      log.log(`Download cancelled for job ${jobId}`);

      // Le statut final sera mis à jour par le polling
    } catch (error) {
      log.error("Failed to cancel download:", error);
      setErrorMessage("Failed to cancel download: " + error.message);

      // Dans tous les cas, on nettoie localement
      clearInterval(intervalRef.current);
      setIsDownloading(false);
      setProgress(0);
      setStatus(DOWNLOAD_CANCELLED);
      callbacksRef.current.onError?.(DOWNLOAD_CANCELLED);
    }
  }, [jobId]);

  const closeErrorModal = () => {
    setErrorMessage("");
  };

  return (
    <DownloadModalContext.Provider
      value={{
        open,
        isDownloading,
        completionCount,
        lastCompletedAt,
      }}
    >
      {children}

      {(isConfirmOpen || isDownloading) &&
        ReactDOM.createPortal(
          <>
            {isConfirmOpen && (
              <ConfirmationModal
                isOpen
                onCancel={cancelConfirm}
                onConfirm={handleConfirm}
                text={model?.name}
              />
            )}
            {isDownloading && (
              <>
                <div className="fixed bottom-7 left-[1.5%]">
                  <SpinnerDots className="w-6 h-6 text-emerald-400 animate-spin" />
                </div>
                <div
                  className={`fixed bottom-0 bg-[#121212]/50 p-4 flex items-center rounded-r-3xl z-50 ${
                    isCollapsed
                      ? "left-[4.5%] w-0 bg-transparent"
                      : "left-[4.5%] w-[35%] sm:w-[38%] xl:w-[28%] gap-3"
                  }`}
                >
                  <div className="flex-1">
                    {!isCollapsed && (
                      <>
                        <div className="flex items-center justify-between w-full">
                          <p className="text-white font-semibold truncate flex-1">
                            {errorMessage ? "Error:" : "Downloading:"} {model?.name}
                          </p>
                          <button
                            onClick={cancelDownload}
                            className="ml-2 p-1.5 bg-red-500/20 hover:bg-red-500/30 rounded transition-colors"
                            aria-label="Cancel"
                          >
                            <X className="w-4 h-4 text-red-400" />
                          </button>
                        </div>

                        {errorMessage ? (
                          <ErrorModal errorMessage={errorMessage} onClose={closeErrorModal} />
                        ) : (
                          <div className="flex gap-4 text-sm text-gray-300 mt-2">
                            <span>
                              Time Left:{" "}
                              <span className="font-semibold">
                                {status === "running" ? formatTimeLeft(timeLeft) : "--"}
                              </span>
                            </span>
                            <span>
                              Progress:{" "}
                              <span className="font-semibold">
                                {status === "running" ? `${progress?.toFixed(1) || 0} %` : "--"}
                              </span>
                            </span>
                          </div>
                        )}

                        {/* Progress bar at bottom - only show if no error */}
                        {!errorMessage && (
                          <div className="absolute left-0 bottom-0 w-[96%] h-1 bg-gray-800/50 rounded-b-3xl overflow-hidden">
                            <div
                              className="h-full bg-gradient-to-r from-emerald-600 via-emerald-500 to-emerald-400 transition-all duration-300 ease-out"
                              style={{ width: `${progress}%` }}
                            />
                          </div>
                        )}
                      </>
                    )}
                  </div>
                  <button
                    className="absolute bottom-8 right-0"
                    onClick={toggleCollapse}
                    aria-label={isCollapsed ? "Expand" : "Collapse"}
                  >
                    {isCollapsed ? (
                      <ChevronRight className="w-6 h-6 text-gray-300 hover:text-white" />
                    ) : (
                      <ChevronLeft className="w-6 h-6 text-gray-300 hover:text-white" />
                    )}
                  </button>
                </div>
              </>
            )}
          </>,
          document.getElementById("modal-root")
        )}
    </DownloadModalContext.Provider>
  );
}

export function useDownloadModal() {
  return useContext(DownloadModalContext);
}
