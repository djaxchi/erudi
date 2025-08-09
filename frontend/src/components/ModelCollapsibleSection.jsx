// src/components/CollapsibleSection.jsx
import React, {
  useState,
  useEffect,
  forwardRef,
  useImperativeHandle,
  useRef,
} from "react";
import Tooltip from "./Tooltip";
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
import { Trash2 } from "lucide-react";

const API_BASE = "http://127.0.0.1:8000";

const CollapsibleSection = forwardRef(({ title, onLocalModelRefresh }, ref) => {
  const [openSection, setOpenSection] = useState(true);
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [deleteConfirmation, setDeleteConfirmation] = useState({
    show: false,
    model: null,
  });
  const [successMessage, setSuccessMessage] = useState("");

  const { open: openDownload } = useDownloadModal();

  // Expose reloadLocalModels to parent via ref
  useImperativeHandle(ref, () => ({
    reloadLocalModels,
  }));

  // TooltipIcon component - Simple CSS-based tooltip
  const TooltipIcon = () => {
    const tooltipText =
      title === "Local Models"
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
            ? `${API_BASE}/main_window/llms/local`
            : `${API_BASE}/main_window/llms/remote`;
        const res = await fetch(url);
        if (res.ok) {
          setModels(await res.json());
        }
      } catch (err) {
        console.error("Failed to fetch models:", err);
        setErrorMessage(
          "Failed to fetch available models. Please try again and contact the Erudi team for support."
        );
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
      else
        setErrorMessage(
          "Failed to fetch local models. Please try again and contact the Erudi team for support."
        );
    } catch (err) {
      console.error("Failed to fetch local models:", err);
      setErrorMessage(
        "Failed to fetch local models. Please try again and contact the Erudi team for support."
      );
    } finally {
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
          {title === "Local Models" && (
            <RefreshCcw
              className="w-4 h-4 hover:opacity-70 cursor-pointer"
              onClick={(e) => {
                e.stopPropagation();
                reloadLocalModels();
              }}
            />
          )}
        </div>

        <div
          className={`grid transition-all duration-300 ease-in-out ${
            openSection
              ? "grid-rows-[1fr] opacity-100"
              : "grid-rows-[0fr] opacity-0"
          }`}
        >
          <div className="px-10 py-2 text-sm text-gray-500 max-h-[35vh] max-w-full overflow-y-auto overflow-x-visible custom-scroll">
            {loading ? (
              <div className="flex items-center gap-2 py-1">
                <div className="w-3 h-3 border-2 border-gray-400 border-t-transparent rounded-full animate-spin"></div>
              </div>
            ) : models.length > 0 ? (
              models.map((m) =>
                title === "Local Models" ? (
                  <div
                    key={m.id}
                    className="flex items-center justify-between py-1 max-w-full group"
                  >
                    <span className="flex-1 pr-2 truncate">{m.name}</span>
                    <button
                      onClick={(e) => handleDeleteClick(e, m)}
                      className="text-red-500 opacity-0 group-hover:opacity-100 transition-opacity duration-150 hover:text-red-400 p-1"
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
              )
            ) : (
              <p className="italic">Nothing here…</p>
            )}
          </div>
        </div>
      </div>

      {/* Error Modal */}
      <ErrorModal errorMessage={errorMessage} onClose={closeErrorModal} />
    </>
  );
});

export default CollapsibleSection;
