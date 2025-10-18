import React, { useState, useRef, useEffect } from "react";
import DragDropArea from "./DragDropArea";
import { Loader, X } from "lucide-react";
import ErrorModal from "./modals/ErrorModal";
import ComingSoonModal from "./modals/ComingSoonModal";
import API_BASE_URL from "../config/api.js"

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
      const newPaths = newPathObjects.map(pathObj => pathObj.path || pathObj);
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
    is_apple_silicon: false,
    mps_available: false,
    unified_memory: false,
    chip_model: null,
  });

  /* Fetch hardware info on component mount */
  useEffect(() => {
    const fetchHardwareInfo = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/hardware/training_info`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const data = await response.json();
        
        // Determine device to use: Apple Silicon GPU with MPS if available, otherwise CPU
        let deviceUsed = "CPU";
        let memoryInfo = "Unknown";
        
        if (data.is_apple_silicon && data.mps_available) {
          // Apple Silicon with MPS support
          deviceUsed = data.gpu_model || "Apple Silicon GPU";
          if (data.unified_memory) {
            memoryInfo = `${data.total_ram_gb} GB Unified Memory`;
          } else {
            memoryInfo = `${data.available_ram_gb} GB`;
          }
        } else if (data.gpu_model && data.gpu_model !== "No GPU detected" && !data.gpu_model.includes("fetching")) {
          // Traditional GPU
          deviceUsed = `${data.gpu_model}`;
          memoryInfo = data.gpu_vram_total_gb ? `${data.gpu_vram_total_gb} GB VRAM` : "Unknown";
        } else if (data.cpu_model && !data.cpu_model.includes("fetching")) {
          // CPU fallback
          deviceUsed = `${data.cpu_model}`;
          memoryInfo = data.available_ram_gb ? `${data.available_ram_gb} GB RAM` : "Unknown";
        }
        
        setHardwareInfo({
          available_vram: memoryInfo,
          device_used: deviceUsed,
          is_apple_silicon: data.is_apple_silicon || false,
          mps_available: data.mps_available || false,
          unified_memory: data.unified_memory || false,
          chip_model: data.chip_model || null,
        });
      } catch (error) {
        console.error("Error fetching hardware info:", error);
        setHardwareInfo({
          available_vram: "Error fetching",
          device_used: "Error fetching",
          is_apple_silicon: false,
          mps_available: false,
          unified_memory: false,
          chip_model: null,
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
      if (d.status === "failed") {
        setTrainingError("Training failed: " + (d.error_message || "Unknown error"));
      }
      return ["failed", "completed"].includes(d.status);
    } catch (e) {
      setTrainingError("Error fetching training status: " + String(e));
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

          <ErrorModal errorMessage={trainingError} onClose={() => setTrainingError("")} />
        </div>

        {/* RIGHT */}
        <div className="h-[100%] w-3/5">
          <DragDropArea onFilesAdded={addDroppedFiles}/>
        </div>
      </div>

      {/* Coming Soon Modal */}
      <ComingSoonModal
        showComingSoonModal={showComingSoonModal}
        onClose={() => setShowComingSoonModal(false)}
        featureName="Dataset evaluation"
        featureDescription="This feature will help you assess the quality and suitability of your training data."
      />
    </>
  );
}