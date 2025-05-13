import React, { useState, useEffect } from "react";
import { ChevronDown, ChevronRight, Cog, RefreshCcw, Plus } from "lucide-react";
import ConfirmationModal from "./ConfirmationModal";
import SpinnerDots from "./Spinner";


export default function CollapsibleSection({ title }) {
  const [open, setOpen] = useState(true);
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedModel, setSelectedModel] = useState(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    const fetchModels = async () => {
      setLoading(true);
      try {
        const endpoint =
          title === "Local Models"
            ? "http://127.0.0.1:8000/main_window/llms/local"
            : "http://127.0.0.1:8000/main_window/llms/remote";
        const response = await fetch(endpoint);
        if (response.ok) {
          const data = await response.json();
          setModels(data);
        } else {
          console.error(`Failed to fetch ${title.toLowerCase()}`);
        }
      } catch (error) {
        console.error("Error fetching models:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchModels();
  }, [title]);

  const handleModelClick = (model) => {
    setSelectedModel(model);
    setIsModalOpen(true);
  };

  const handleConfirmDownload = async () => {
    if (!selectedModel) return;

    setIsDownloading(true);
    setErrorMessage("");
    try {
      const response = await fetch(
        `http://127.0.0.1:8000/main_window/llms/${selectedModel.id}/download`,
        { method: "POST" }
      );
      if (response.ok) {
        const eventSource = new EventSource(
          `http://127.0.0.1:8000/main_window/llms/${selectedModel.id}/status/stream`
        );

        eventSource.onmessage = (event) => {
          if (event.data === "installed") {
            setIsDownloading(false);
            eventSource.close();
          }
          if (event.data.startsWith("error")) {
            setErrorMessage("Download failed.");
            setIsDownloading(false);
            eventSource.close();
          }
        };

        eventSource.onerror = () => {
          setErrorMessage("Error during download stream.");
          setIsDownloading(false);
          eventSource.close();
        };
      } else {
        setErrorMessage("Failed to start download. Please try again.");
        setIsDownloading(false);
      }
    } catch (error) {
      console.error("Error downloading model:", error);
      setErrorMessage("An error occurred while starting the download.");
      setIsDownloading(false);
    } finally {
      setIsModalOpen(false);
      setSelectedModel(null);
    }
  };

  return (
    <div className="text-gray-200">
      {errorMessage && (
        <div className="text-red-500 text-sm mb-2">{errorMessage}</div>
      )}

      <div
        className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-gray-700/30"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center gap-2">
          {open ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}          
          <span className="font-semibold">{title}</span>
        </div>

        <div className="flex gap-3">
          <Cog className="w-4 h-4 hover:opacity-70" />
          <RefreshCcw className="w-4 h-4 hover:opacity-70" />
          <Plus className="w-4 h-4 hover:opacity-70" />
        </div>
      </div>

      {open && (
        <div className="px-10 py-2 text-sm text-gray-500">
          {loading ? (
            <p className="italic">Loading...</p>
          ) : title === "Local Models" && models.length > 0 ? (
            models.map((model) => (
              <p key={model.id} className="py-1">
                {model.name}
              </p>
            ))
          ) : title === "Available Models" && models.length > 0 ? (
            models.map((model) => (
              <p
                key={model.id}
                className="py-1 cursor-pointer hover:text-blue-500"
                onClick={() => handleModelClick(model)}
              >
                {model.name}
              </p>
            ))
          ) : (
            <p className="italic">Nothing here…</p>
          )}
        </div>
      )}

      <ConfirmationModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onConfirm={handleConfirmDownload}
        title="Confirm Download"
        message={`Are you sure you want to download "${selectedModel?.name}"?`}
      />

      {isDownloading && (
        <div className="fixed bottom-0 left-0 w-full flex items-center gap-2 pb-4 pl-4 z-50">
          <SpinnerDots size={30} dotSize={4} colorClass="bg-green-400" />
        </div>
      )}
    </div>
  );
}


