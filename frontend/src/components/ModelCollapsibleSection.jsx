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
} from "lucide-react";
import { useDownloadModal } from "../contexts/DownloadModalContext";
import ErrorModal from "./modals/ErrorModal";

const API_BASE = "http://127.0.0.1:8000";

const CollapsibleSection = forwardRef(({ title, onLocalModelRefresh }, ref) => {
  const [openSection, setOpenSection] = useState(true);
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [tooltipVisible, setTooltipVisible] = useState(false);
  const [tooltipPosition, setTooltipPosition] = useState({ top: 0, left: 0 });

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
            ? `${API_BASE}/main_window/llms/local`
            : `${API_BASE}/main_window/llms/remote`;
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
      const url = `${API_BASE}/main_window/llms/local`;
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

  const closeErrorModal = () => {
    setErrorMessage("");
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
                <p
                  key={m.id}
                  className={`py-1 max-w-full ${
                    title !== "Local Models"
                      ? "cursor-pointer hover:text-blue-500"
                      : ""
                  }`}
                  onClick={() =>
                    title !== "Local Models" && handleModelClick(m)
                  }
                >
                  {m.name}
                </p>
              ))
            ) : (
              <p className="italic">Nothing here…</p>
            )}
          </div>
        )}
      </div>

      {/* Error Modal */}
      <ErrorModal errorMessage={errorMessage} onClose={closeErrorModal} />
    </>
  );
});

export default CollapsibleSection;