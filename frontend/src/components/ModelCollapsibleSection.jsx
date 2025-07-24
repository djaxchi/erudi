import React, { useState, useEffect, useRef } from "react";
import { ChevronDown, ChevronRight, Cog, RefreshCcw, Plus } from "lucide-react";
import ConfirmationModal from "./modals/ConfirmationModal";
import SpinnerDots from "./Spinner";
import PreparingModal from "./modals/PreparingModal";

const API_BASE = "http://127.0.0.1:8000/main_window";

export default function CollapsibleSection({ title }) {
  const [open, setOpen] = useState(true);
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(false);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedModel, setSelectedModel] = useState(null);

  // download states
  const [isPreparing, setIsPreparing] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState(0);
  const [downloadStatus, setDownloadStatus] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");

  // ref for polling interval
  const pollingRef = useRef(null);

  useEffect(() => {
    // cleanup on unmount
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, []);

  useEffect(() => {
    async function fetchModels() {
      setLoading(true);
      try {
        const url =
          title === "Local Models"
            ? `${API_BASE}/llms/local`
            : `${API_BASE}/llms/remote`;
        const res = await fetch(url);
        if (res.ok) setModels(await res.json());
      } catch (err) {
        console.error("Failed to fetch models:", err);
      } finally {
        setLoading(false);
      }
    }
    fetchModels();
  }, [title]);

  const handleModelClick = (model) => {
    setSelectedModel(model);
    setIsModalOpen(true);
    setErrorMessage("");
  };

  const checkDownloadStatus = async (llmId) => {
    try {
      const res = await fetch(
        `${API_BASE}/llms/${llmId}/download/status`
      );
      if (!res) throw new Error("status fetch failed");
      const data = await res.json();
      setDownloadProgress(data.progress);
      setDownloadStatus(data.status);

      if (data.status === "completed") {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
        setIsDownloading(false);
        setIsPreparing(false);
        reloadModels();
      } else if (data.status === "failed") {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
        setErrorMessage("Download failed.");
        setIsDownloading(false);
        setIsPreparing(false);
      }
    } catch (err) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
      setErrorMessage("Error checking download status.");
      setIsDownloading(false);
      setIsPreparing(false);
    }
  };

  const reloadModels = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/llms/local`);
      if (res.ok) setModels(await res.json());
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmDownload = async () => {
    if (!selectedModel) return;
    setIsModalOpen(false);
    setIsPreparing(true);
    setIsDownloading(true);
    setDownloadProgress(0);
    setDownloadStatus("pending");
    setErrorMessage("");

    // start the job
    const res = await fetch(
      `${API_BASE}/llms/${selectedModel.id}/download`,
      { method: "POST" }
    );
    if (!res.ok) {
      setErrorMessage("Failed to start download.");
      setIsDownloading(false);
      setIsPreparing(false);
      return;
    }

    // begin polling every 2s
    pollingRef.current = setInterval(() => {
      checkDownloadStatus(selectedModel.id);
    }, 2000);
  };

  return (
    <div className="text-gray-200 w-full">
      {errorMessage && (
        <div className="text-red-500 text-sm mb-2">{errorMessage}</div>
      )}

      <div
        className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-gray-700/30"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center gap-2">
          {open ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
          <span className="font-semibold text-xl sm:text-lg">{title}</span>
        </div>
        <div className="flex gap-3">
          <Cog className="w-4 h-4 hover:opacity-70" />
          <RefreshCcw
            className="w-4 h-4 hover:opacity-70 cursor-pointer"
            onClick={reloadModels}
          />
          <Plus className="w-4 h-4 hover:opacity-70" />
        </div>
      </div>

      {open && (
        <div className="px-10 py-2 text-sm text-gray-500">
          {loading ? (
            <p className="italic">Loading...</p>
          ) : title === "Local Models" && models.length > 0 ? (
            models.map((m) => <p key={m.id} className="py-1">{m.name}</p>)
          ) : title === "Available Models" && models.length > 0 ? (
            models.map((m) => (
              <p
                key={m.id}
                className="py-1 cursor-pointer hover:text-blue-500"
                onClick={() => handleModelClick(m)}
              >
                {m.name}
              </p>
            ))
          ) : (
            <p className="italic">Nothing here…</p>
          )}
        </div>
      )}

      <ConfirmationModal
        isOpen={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        onConfirm={handleConfirmDownload}
        text={selectedModel?.name}
      />

      <PreparingModal isOpen={isPreparing} onClose={() => {}} />

      {isDownloading && (
        <div className="fixed bottom-0 left-0 w-full px-4 pb-4 z-50">
          <div className="w-full bg-gray-700 rounded h-2 overflow-hidden">
            <div
              className="bg-emerald-500 h-2"
              style={{ width: `${downloadProgress}%` }}
            />
          </div>
          <p className="text-xs text-white mt-1">
            Downloading... {downloadProgress}%
          </p>
        </div>
      )}
    </div>
  );
}