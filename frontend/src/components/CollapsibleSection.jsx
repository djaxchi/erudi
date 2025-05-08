import React, { useState, useEffect } from "react";
import { ChevronDown, ChevronRight, Cog, RefreshCcw, Plus } from "lucide-react";
import ConfirmationModal from "./ConfirmationModal";

export default function CollapsibleSection({ title }) {
  const [open, setOpen] = useState(true);
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedModel, setSelectedModel] = useState(null); // Track the selected LLM

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
    setSelectedModel(model); // Set the selected LLM
    setIsModalOpen(true); // Open the modal
  };

  const handleConfirmDownload = async () => {
    if (!selectedModel) return;

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/main_window/llms/${selectedModel.id}/download`,
        {
          method: "POST",
        }
      );
      if (response.ok) {
        console.log(`Download started for ${selectedModel.name}`);
      } else {
        console.error("Failed to start download");
      }
    } catch (error) {
      console.error("Error downloading model:", error);
    } finally {
      setIsModalOpen(false); // Close the modal
      setSelectedModel(null); // Clear the selected model
    }
  };

  return (
    <div className="text-gray-200">
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
                onClick={() => handleModelClick(model)} // Handle click
              >
                {model.name}
              </p>
            ))
          ) : (
            <p className="italic">Nothing here…</p>
          )}
        </div>
      )}

      {/* Confirmation Modal */}
      <ConfirmationModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onConfirm={handleConfirmDownload}
        title="Confirm Download"
        message={`Are you sure you want to download "${selectedModel?.name}"?`}
      />
    </div>
  );
}