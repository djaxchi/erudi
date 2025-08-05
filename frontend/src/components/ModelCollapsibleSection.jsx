
// src/components/CollapsibleSection.jsx
import React, { useState, useEffect, forwardRef, useImperativeHandle, useRef } from "react";
import {
  ChevronDown,
  ChevronRight,
  Cog,
  RefreshCcw,
  Plus,
  X,
  HelpCircle,
  Trash2,
} from "lucide-react";
import { useDownloadModal } from "../contexts/DownloadModalContext";
import { API_BASE_URL } from "../config/api";

const CollapsibleSection = forwardRef(({ title, onLocalModelRefresh }, ref) => {
  const [openSection, setOpenSection] = useState(true);
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [tooltipVisible, setTooltipVisible] = useState(false);
  const [tooltipPosition, setTooltipPosition] = useState({ top: 0, left: 0 });
  const [deleteConfirmation, setDeleteConfirmation] = useState({ show: false, model: null });
  const [successMessage, setSuccessMessage] = useState("");

  const { open: openDownload } = useDownloadModal();

  // Expose reloadLocalModels to parent via ref
  useImperativeHandle(ref, () => ({
    reloadLocalModels
  }));

  // TooltipIcon component
  const TooltipIcon = () => {
    const iconRef = useRef(null);
    
    const handleMouseEnter = () => {
      if (iconRef.current) {
        const rect = iconRef.current.getBoundingClientRect();
        const tooltipWidth = 300; // Approximate tooltip width
        const windowWidth = window.innerWidth;
        
        // Check if tooltip would go off-screen to the right
        const wouldOverflow = rect.right + 8 + tooltipWidth > windowWidth;
        
        setTooltipPosition({
          top: rect.top + window.scrollY + (rect.height / 2), // Center vertically with the icon
          left: wouldOverflow 
            ? rect.left + window.scrollX - 8 - tooltipWidth // Position to the left if would overflow
            : rect.right + window.scrollX + 8, // 8px to the right of the icon
          isLeftSide: wouldOverflow
        });
      }
      setTooltipVisible(true);
    };

    const handleMouseLeave = () => {
      setTooltipVisible(false);
    };

    return (
      <div 
        ref={iconRef}
        className="relative"
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      >
        <HelpCircle className="w-3 h-3 sm:w-4 sm:h-4 text-gray-400 hover:text-emerald-400 transition-colors cursor-help" />
      </div>
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
        // Recharger la liste des modèles
        await reloadLocalModels();
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

  return (
    <>
      {/* Global tooltip */}
      {tooltipVisible && (
        <div 
          className="fixed bg-black text-white text-xs rounded-lg px-3 py-2 shadow-xl border border-gray-600 z-[99999]"
          style={{
            top: `${tooltipPosition.top}px`,
            left: `${tooltipPosition.left}px`,
            transform: 'translateY(-50%)', // Center vertically relative to the icon
            width: '280px', // Fixed width for consistent sizing
          }}
        >
          {title === "Local Models" 
            ? "Models downloaded and ready to use on your computer. These are available for chat, and specialization!"
            : "Models available for download. Click on any model to download it to your local storage."
          }
          {/* Arrow pointing left or right depending on position */}
          {tooltipPosition.isLeftSide ? (
            <div className="absolute left-full top-1/2 transform -translate-y-1/2 w-0 h-0 border-t-4 border-b-4 border-l-4 border-transparent border-l-black"></div>
          ) : (
            <div className="absolute right-full top-1/2 transform -translate-y-1/2 w-0 h-0 border-t-4 border-b-4 border-r-4 border-transparent border-r-black"></div>
          )}
        </div>
      )}

      <div className="text-gray-200 w-full">
        {/* Section header */}
        <div
          className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-gray-700/30"
          onClick={() => setOpenSection((prev) => !prev)}
        >
          <div className="flex items-center gap-2">
            {openSection ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronRight className="w-4 h-4" />
            )}
            <span className="font-semibold text-xl sm:text-lg">{title}</span>
            <TooltipIcon />
          </div>
          {
            title === "Local Models" && (
            <RefreshCcw 
              className="w-4 h-4 hover:opacity-70 cursor-pointer" 
              onClick={(e) => {
                e.stopPropagation();
                reloadLocalModels();
              }} 
            />
          )}
        </div>

        {/* Section body */}
        {openSection && (
          <div className="px-10 py-2 text-sm text-gray-500 max-h-[35vh] max-w-full overflow-y-auto overflow-x-visible custom-scroll">
            {loading ? (
              <div className="flex items-center gap-2 py-1">
                <div className="w-3 h-3 border-2 border-gray-400 border-t-transparent rounded-full animate-spin"></div>
              </div>
            ) : models.length > 0 ? (
              models.map((m) => (
                title === "Local Models" ? (
                  <div
                    key={m.id}
                    className="flex items-center justify-between py-1 max-w-full group"
                  >
                    <span className="flex-1">{m.name}</span>
                    <button
                      onClick={(e) => handleDeleteClick(e, m)}
                      className="text-gray-400 hover:text-red-400 transition-colors p-1"
                      title="Delete model"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ) : (
                  <p
                    key={m.id}
                    className="py-1 max-w-full cursor-pointer hover:text-blue-500"
                    onClick={() => handleModelClick(m)}
                  >
                    {m.name}
                  </p>
                )
              ))
            ) : (
              <p className="italic">Nothing here…</p>
            )}
          </div>
        )}
      </div>

      {/* Error Modal */}
      {errorMessage && (
        <div className="fixed inset-0 bg-black bg-opacity-60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-[#2B2B2B] rounded-2xl border border-white/10 shadow-2xl max-w-md w-full">
            {/* Header */}
            <div className="p-4 border-b border-white/10">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold text-white flex items-center gap-3">
                  Error
                </h2>
                <button
                  onClick={closeErrorModal}
                  className="text-gray-400 hover:text-white transition-colors"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>
            </div>

            {/* Content */}
            <div className="p-6">
              <div className="text-red-400 bg-red-900/20 border border-red-600/30 rounded-lg p-4">
                <p className="text-sm">{errorMessage}</p>
              </div>
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-white/10">
              <div className="flex justify-end">
                <button
                  onClick={closeErrorModal}
                  className="bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded-lg transition-colors font-medium"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Success Modal */}
      {successMessage && (
        <div className="fixed inset-0 bg-black bg-opacity-60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-[#2B2B2B] rounded-2xl border border-white/10 shadow-2xl max-w-md w-full">
            {/* Header */}
            <div className="p-4 border-b border-white/10">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold text-white flex items-center gap-3">
                  Success
                </h2>
                <button
                  onClick={closeSuccessModal}
                  className="text-gray-400 hover:text-white transition-colors"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>
            </div>

            {/* Content */}
            <div className="p-6">
              <div className="text-green-400 rounded-lg p-4">
                <p className="text-sm">{successMessage}</p>
              </div>
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-white/10">
              <div className="flex justify-end">
                <button
                  onClick={closeSuccessModal}
                  className="bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded-lg transition-colors font-medium"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirmation.show && (
        <div className="fixed inset-0 bg-black bg-opacity-60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-[#2B2B2B] rounded-2xl border border-white/10 shadow-2xl max-w-md w-full">
            {/* Header */}
            <div className="p-4 border-b border-white/10">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold text-white flex items-center gap-3">
                  Delete Model
                </h2>
                <button
                  onClick={cancelDelete}
                  className="text-gray-400 hover:text-white transition-colors"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>
            </div>

            {/* Content */}
            <div className="p-6">
              <div className="text-white-400 rounded-lg p-4">
                <p className="text-sm">
                  Do you want to delete the model {deleteConfirmation.model?.name} ?
                </p>
              </div>
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-white/10">
              <div className="flex justify-end gap-3">
                <button
                  onClick={cancelDelete}
                  className="bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded-lg transition-colors font-medium"
                >
                  No
                </button>
                <button
                  onClick={confirmDelete}
                  className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg transition-colors font-medium"
                >
                  Yes
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
});

export default CollapsibleSection;