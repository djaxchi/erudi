// src/components/CollapsibleSection.jsx
import React, { useState, useEffect, forwardRef, useImperativeHandle, useRef } from "react";
import Tooltip from "./Tooltip";
import DeleteModelModal from "./modals/DeleteModelModal";
import MessageModal from "./modals/MessageModal";
import {
  ChevronDown,
  RefreshCcw,
  X,
  HelpCircle,
  Trash2,
  Database,
  Globe,
  Search,
} from "lucide-react";
import { useDownloadModal } from "../contexts/DownloadModalContext";

const API_BASE_URL = "http://127.0.0.1:8000";

// Icon mapping for different section types
const getIconForSection = (title) => {
  switch (title) {
    case "Local Models":
      return <Database className="w-5 h-5 font-bold text-white" />;
    case "Remote Models":
      return <Globe className="w-5 h-5 font-bold text-white" />;
    default:
      return <Database className="w-5 h-5 font-bold text-white" />;
  }
};

const CollapsibleSection = forwardRef(({ title, onLocalModelRefresh, hasSearch = false }, ref) => {
  const [openSection, setOpenSection] = useState(true);
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [deleteConfirmation, setDeleteConfirmation] = useState({ show: false, model: null });
  const [successMessage, setSuccessMessage] = useState("");
  const [searchTerm, setSearchTerm] = useState("");

  const { open: openDownload } = useDownloadModal();

  // Expose reloadLocalModels to parent via ref
  useImperativeHandle(ref, () => ({
    reloadLocalModels
  }));

  // TooltipIcon component - Simple CSS-based tooltip
  const TooltipIcon = () => {
    const tooltipText = title === "Local Models" 
      ? "Models downloaded and ready to use on your computer. These are available for chat, and specialization!"
      : "Models available for download. Click on any model to download it to your local storage.";

    return (
      <Tooltip content={tooltipText} side="right" width="w-80">
        <HelpCircle className="w-3 h-3 sm:w-4 sm:h-4 text-gray-400 hover:text-emerald-400 transition-colors cursor-help" />
      </Tooltip>
    );
  };

  // fetch models
  useEffect(() => {
    async function fetchModels() {
      setLoading(true);
      try {
        const url =
          title === "Local Models"
            ? `${API_BASE_URL}/main_window/llms/local`
            : `${API_BASE_URL}/main_window/llms/remote`;
        const res = await fetch(url);
        if (res.ok) {
          setModels(await res.json());
        }
      } catch (err) {
        console.error("Failed to fetch models:", err);
        setErrorMessage("Failed to fetch available models. Please try again and contact the Erudi team for support.");
      } finally {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        setLoading(false);
      }
    }
    fetchModels();
  }, [title]);
  
  const reloadLocalModels = async () => {
    setLoading(true);
    try {
      const url = `${API_BASE_URL}/main_window/llms/local`;
      const res = await fetch(url);
      if (res.ok) setModels(await res.json());
      else setErrorMessage("Failed to fetch local models. Please try again and contact the Erudi team for support.");
    } 
    catch (err) {
      console.error("Failed to fetch local models:", err);
      setErrorMessage("Failed to fetch local models. Please try again and contact the Erudi team for support.");
    } 
    finally {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      setLoading(false);
    }
  };

  const loadLocalModelsAfterDownload = () => {
    // Si on est dans la section Remote Models et qu'on a un callback pour recharger les locaux
    if (title === "Remote Models" && onLocalModelRefresh) {
      onLocalModelRefresh();
    }
  };

  const handleModelClick = (model) => {
    setErrorMessage("");
    openDownload(model, {
      onComplete: loadLocalModelsAfterDownload,
      onError: (err) => setErrorMessage(err ?? "Download failed."),
    });
  };

  const handleDeleteClick = (e, model) => {
    e.stopPropagation();
    setDeleteConfirmation({ show: true, model });
  };

  const confirmDelete = async () => {
    if (!deleteConfirmation.model) return;
    
    try {
      const response = await fetch(`${API_BASE_URL}/main_window/llms/${deleteConfirmation.model.id}`, {
        method: 'DELETE',
      });
      
      if (response.ok) {
        setSuccessMessage(`Model ${deleteConfirmation.model.name} has been successfully deleted.`);
        // Reload models in this component
        await reloadLocalModels();
        // Also refresh the main page local models
        if (onLocalModelRefresh) {
          onLocalModelRefresh();
        }
      } else {
        throw new Error(`Failed to delete model: ${response.status}`);
      }
    } catch (error) {
      console.error("Failed to delete model:", error);
      setErrorMessage("Failed to delete the model. Please try again and contact the Erudi team for support.");
    } finally {
      setDeleteConfirmation({ show: false, model: null });
    }
  };

  const cancelDelete = () => {
    setDeleteConfirmation({ show: false, model: null });
  };

  const closeErrorModal = () => {
    setErrorMessage("");
  };

  const closeSuccessModal = () => {
    setSuccessMessage("");
  };

  // Filter models based on search term
  const filteredModels = models.filter(model =>
    model.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <>
      <div className="text-gray-200 w-full">
        {/* Section header */}
        <div
          className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-gray-700/30 transition-colors"
          onClick={() => setOpenSection((prev) => !prev)}
        >
          <div className="flex items-center gap-3">
            {getIconForSection(title)}
            <span className="font-bold text-lg text-gray-200">{title}</span>
            <TooltipIcon />
            {title === "Local Models" && (
              <RefreshCcw 
                className="w-4 h-4 text-gray-400 hover:text-gray-200 cursor-pointer transition-colors" 
                onClick={(e) => {
                  e.stopPropagation();
                  reloadLocalModels();
                }} 
              />
            )}
          </div>
          <div className="flex items-center gap-2">
            <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform duration-200 ${!openSection ? '-rotate-90' : ''}`} />
          </div>
        </div>

        {/* Collapsible content */}
        <div className={`grid transition-all duration-300 ease-in-out ${openSection ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'}`}>
          <div className="overflow-hidden">
            {/* Search bar for Remote Models only */}
            {hasSearch && title !== "Local Models" && openSection && (
              <div className="px-4 py-1 pb-3">
                <div className="relative rounded-2xl bg-[#1a1a1a]/60 border-[0.2px] border-white/10">
                  <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 transform -translate-y-1/2" />
                  <input
                    type="text"
                    placeholder="Looking for a model?"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="w-full bg-transparent rounded-2xl pl-10 pr-4 py-1 text-sm text-white placeholder-gray-400 focus:outline-none border-[0.2px] focus:border-white/10"
                  />
                </div>
              </div>
            )}
                  

            {/* Models list */}
            <div className="pl-12 pr-4 pb-2 max-h-[40vh] overflow-y-auto custom-scroll">
              {loading ? (
                <div className="flex items-center gap-2 py-2 text-gray-400">
                  <div className="w-3 h-3 border-2 border-gray-400 border-t-transparent rounded-full animate-spin"></div>
                  <span className="text-sm">Loading models...</span>
                </div>
              ) : (filteredModels.length > 0 || models.length > 0) ? (
                (hasSearch ? filteredModels : models).length > 0 ? (
                  (hasSearch ? filteredModels : models).map((m) => (
                    title === "Local Models" ? (
                      <div
                        key={m.id}
                        className="flex items-center justify-between py-1.5 group hover:bg-gray-700/20 rounded px-2 -ml-2 transition-colors"
                      >
                        <span className="flex-1 text-gray-300 text-sm truncate pr-2">{m.name}</span>
                        <button
                          onClick={(e) => handleDeleteClick(e, m)}
                          className="text-red-400 opacity-0 group-hover:opacity-100 transition-opacity duration-150 hover:text-red-300 p-1 rounded hover:bg-red-900/20"
                          title="Delete model"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    ) : (
                      <div
                        key={m.id}
                        className="py-1.5 px-2 -ml-2 text-sm text-gray-400 cursor-pointer hover:text-gray-200 hover:bg-gray-700/20 rounded transition-colors truncate"
                        onClick={() => handleModelClick(m)}
                      >
                        {m.name}
                      </div>
                    )
                  ))
                ) : (
                  <p className="text-gray-500 text-sm italic py-2">No models found...</p>
                )
              ) : (
                <p className="text-gray-500 text-sm italic py-2">
                  {title === "Local Models" ? "No models here..." : "No models available..."}
                </p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Error Modal */}
      <MessageModal
        isOpen={!!errorMessage}
        title="Error"
        message={errorMessage}
        type="error"
        onClose={closeErrorModal}
      />

      {/* Success Modal */}
      <MessageModal
        isOpen={!!successMessage}
        title="Success"
        message={successMessage}
        type="success"
        onClose={closeSuccessModal}
      />

      {/* Delete Confirmation Modal */}
      <DeleteModelModal
        isOpen={deleteConfirmation.show}
        model={deleteConfirmation.model}
        onConfirm={confirmDelete}
        onCancel={cancelDelete}
      />
    </>
  );
});

export default CollapsibleSection;