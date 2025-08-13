import React, { useState, useRef, useEffect } from "react";
import DragDropArea from "./DragDropArea";
import { Loader, X } from "lucide-react";
import { API_BASE_URL } from "../config/api";

/* ─────────────── Recap small table ─────────────── */
function RecapTable({ recap }) {
  const rows = [
    ["Model", recap.model || "—"],
    ["Device used", recap.device || "—"],
    ["Available RAM", recap.ram || "—"],
    ["Dataset size", recap.datasetSize || "—"],
    ["Estimate", recap.estimate || "Coming soon"],
    ["Recap", recap.notes || "Coming soon"],
  ];
  return (
    <div className="rounded-lg border border-white/20 overflow-hidden">
      <table className="w-full text-[10px] sm:text-xs lg:text-sm leading-3 sm:leading-4 lg:leading-5 bg-transparent">
        <tbody>
          {rows.map(([label, val], idx) => (
          <tr
            key={label}
            className={`${idx % 2 === 0 ? "bg-[#3B3B3B]" : "bg-black/20"}`}
          >
            <th className="px-1.5 sm:px-2 lg:px-3 py-0.5 sm:py-1 lg:py-1.5 text-left font-semibold text-white w-[44%]">{label}</th>
            <td className="px-1.5 sm:px-2 lg:px-3 py-0.5 sm:py-1 lg:py-1.5 text-center text-white/90 truncate">{val}</td>
          </tr>
        ))}
      </tbody>
    </table>
    </div>
  );
}

/* ─────────────── Main component ─────────────── */
export default function DatasetCard({ selectedModel, modelName, onStartTraining, isTraining = false, onReset }) {
  /* Paths - now handling objects with metadata */
  const [paths, setPaths] = useState([]);
  /* Modal state */
  const [showComingSoonModal, setShowComingSoonModal] = useState(false);
  
  const addDroppedFiles = (newPathObjects) => {
    console.log('DatasetCard received files:', newPathObjects);
    
    // Handle complete replacement of the file list (for when files are removed)
    // or addition of new files (for when files are added)
    setPaths(() => {
      const newPaths = newPathObjects.map(pathObj => {
        const path = pathObj.path || pathObj;
        // Normalize Windows paths: replace backslashes with forward slashes
        // This ensures proper JSON serialization and cross-platform compatibility
        return typeof path === 'string' ? path.replace(/\\/g, '/') : path;
      });
      console.log('Setting paths to:', newPaths);
      return Array.from(new Set(newPaths)); // Remove duplicates but don't merge with previous
    });
  };

  /* Training state */
  const [trainingStatus, setTrainingStatus] = useState(null);
  const [trainingError, setTrainingError] = useState("");
  const [progress, setProgress] = useState(0);
  const pollingRef = useRef(null);

  /* Hardware info state */
  const [hardwareInfo, setHardwareInfo] = useState({
    available_vram: "fetching...",
    device_used: "fetching...",
  });

  /* Fetch hardware info on component mount */
  useEffect(() => {
    const fetchHardwareInfo = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/hardware/training`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const data = await response.json();
        
        setHardwareInfo({
          total_ram: data.total_ram_gb ? `${data.total_ram_gb} GB` : "Unknown",
          device_used: data.cpu_model ? `${data.cpu_model}` : "CPU",
        });
      } catch (error) {
        console.error("Error fetching hardware info:", error);
        setHardwareInfo({
          total_ram: "Error fetching",
          device_used: "Error fetching",
        });
      }
    };

    fetchHardwareInfo();
  }, []);

  /* Handle reset from parent component */
  const resetDatasetCardState = () => {
    console.log('Resetting DatasetCard state');
    setPaths([]);
    setTrainingStatus(null);
    setTrainingError("");
    setProgress(0);
    // Clear any polling intervals
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    // Reset the DragDropArea by calling addDroppedFiles with empty array
    addDroppedFiles([]);
  };

  useEffect(() => {
    if (onReset) {
      // Store our reset function so parent can call it
      onReset.current = resetDatasetCardState;
    }
  }, [onReset]);

  /* Recap info */
  const recap = {
    model: modelName || "—",
    device: hardwareInfo.device_used,
    ram: hardwareInfo.available_vram,
    datasetSize: paths.length ? `${paths.length} files` : "—",
    estimate: "Coming soon",
    notes: "Coming soon",
  };

  /* Polling helpers */
  const checkTrainingStatus = async (id) => {
    try {
      const res = await fetch(`${API_BASE_URL}/training/${id}/status`);
      if (!res.ok) throw new Error(res.status);
      const d = await res.json();
      setTrainingStatus(d.status);
      setProgress(d.progress || 0);
      return ["failed", "completed"].includes(d.status);
    } catch (e) {
      setTrainingError(String(e));
      return true;
    }
  };
  const startPolling = (id) => {
    pollingRef.current && clearInterval(pollingRef.current);
    pollingRef.current = setInterval(async () => {
      (await checkTrainingStatus(id)) && (clearInterval(pollingRef.current), (pollingRef.current = null));
    }, 30_000);
  };
  useEffect(() => () => pollingRef.current && clearInterval(pollingRef.current), []);

  /* Launch training */
  const submitTrain = async () => {
    if (!selectedModel || !modelName || !paths.length || modelName.trim() === "") return;
    
    if (onStartTraining) {
      onStartTraining(paths);
    }
  };

  /* ─────────────── Render ─────────────── */
  return (
    <>
      <div className="flex-1 bg-[#2B2B2B] rounded-2xl p-4 sm:p-6 shadow-lg text-white flex gap-4 sm:gap-6 w-full border border-white/20 border-[0.5px]">
        {/* LEFT */}
        <div className="w-2/5 flex flex-col gap-3 sm:gap-4">
          {/* Recap table */}
          <div>
            <h3 className="text-xl md:text-2xl font-bold mb-1.5 sm:mb-2">Recap</h3>
            <RecapTable recap={recap} />
          </div>

          {/* Action buttons */}
          <div className="flex gap-3 sm:gap-4 mt-6">
            <button
              className="flex-1 py-2 sm:py-3 rounded-full border border-white/30 text-white font-semibold hover:bg-white/10 transition disabled:opacity-40 text-xs sm:text-sm"
              disabled={!paths.length || isTraining}
              onClick={() => setShowComingSoonModal(true)}
            >
              Evaluate dataset
            </button>

            {isTraining ? (
              <div className="flex-1 flex flex-col items-center gap-3 py-2">
                
                {/* Status text with enhanced styling */}
                <div className="flex items-center gap-2 bg-emerald-950/30 px-3 py-2 rounded-full border border-emerald-500/20">
                  <div className="relative">
                    <Loader className="w-4 h-4 text-emerald-400 animate-spin" />
                    <div className="absolute inset-0 w-4 h-4 bg-emerald-400/20 rounded-full animate-pulse"></div>
                  </div>
                  <span className="text-emerald-300 font-medium text-sm">
                    {trainingStatus === "running" ? "Training in Progress" : "Initializing Training"}
                  </span>
                </div>
              </div>
            ) : (
              <button
                className="flex-1 py-2 sm:py-3 rounded-full bg-emerald-500 text-white font-semibold shadow-lg hover:bg-emerald-400 transition disabled:opacity-50 text-xs sm:text-sm"
                disabled={!paths.length || !selectedModel || !modelName || modelName.trim() === ""}
                onClick={submitTrain}
              >
                Train
              </button>
            )}
          </div>

          {trainingError && <p className="text-red-400 text-xs sm:text-sm mt-1.5 sm:mt-2">{trainingError}</p>}
        </div>

        {/* RIGHT */}
        <div className="h-[100%] w-3/5">
          <DragDropArea onFilesAdded={addDroppedFiles}/>
        </div>
      </div>

      {/* Coming Soon Modal */}
      {showComingSoonModal && (
        <div className="fixed inset-0 bg-black bg-opacity-60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-[#2B2B2B] rounded-2xl border border-white/10 shadow-2xl max-w-md w-full">
            {/* Header */}
            <div className="p-4 border-b border-white/10">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold text-white flex items-center gap-3">
                  🚧 Coming Soon
                </h2>
                <button
                  onClick={() => setShowComingSoonModal(false)}
                  className="text-gray-400 hover:text-white transition-colors"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>
            </div>

            {/* Content */}
            <div className="p-6">
              <div className="text-gray-300 text-center">
                <p className="text-sm mb-4">
                  Dataset evaluation feature is currently under development and will be available in a future update.
                </p>
                <p className="text-xs text-gray-400">
                  This feature will help you assess the quality and suitability of your training data.
                </p>
              </div>
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-white/10">
              <div className="flex justify-end">
                <button
                  onClick={() => setShowComingSoonModal(false)}
                  className="bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded-lg transition-colors font-medium"
                >
                  Got it
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}