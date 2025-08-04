import React, { useEffect, useState, useRef } from "react";
import Sidebar from "../components/Sidebar";
import DatasetCard from "../components/DatasetCard";
import HardwareInfo from "../components/HardwareInfo";
import ModelLibrary from "../components/ModelLibrary";
import { useDownloadModal } from "../contexts/DownloadModalContext";
import { X } from "lucide-react";

const API_BASE = "http://localhost:8000";

export default function TrainingPage() {
  const { open: openProgressModal, isTraining } = useDownloadModal();
  const [errorMessage, setErrorMessage] = useState("");
  const datasetCardResetRef = useRef(null);
  
  const [hw, setHw] = useState({
    storage_path: "soon...",
    disk_available: "fetching…",
    cpu_model: "fetching…",
    gpu_model: "fetching…",
    chip_model: "fetching…",  // Apple Silicon chip (M1, M2, M3, etc.)
    gpu_cores: "fetching…",  // Number of GPU cores
    estimated_gpu_tflops: "fetching…",  // Estimated GPU performance
    memory_bandwidth_gbs: "fetching…",  // Unified memory bandwidth
    neural_engine_tops: "fetching…",  // Neural Engine performance
    architecture: "fetching…",  // 3nm, 5nm, etc.
    is_apple_silicon: false,
    mps_available: false,  // Metal Performance Shaders
    unified_memory: false,  // Unified memory architecture
    gpu_vram_total: "N/A",  // Not applicable for unified memory
    ram_available: "fetching…",
    total_ram_gb: "fetching…",
    cpu_eval_score: "fetching…",
    gpu_eval_score: "fetching…",
    memory_score: "fetching…",
    global_finetuning_score: "fetching…",
    global_finetuning_label: "fetching…",
  });

  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState(null);
  const [modelName, setModelName] = useState("");

  const fetchModels = () => {
    fetch(`${API_BASE}/main_window/llms/local`)
      .then(res => {
        if (!res.ok) setErrorMessage("Failed to fetch your local models. Please try again. If the issue persists, contact the Erudi team for support.");
        return res.json();
      })
      .then(data => {
        console.log("Fetched models:", data, "Count:", data ? data.length : 0);
        setModels(data || []);
      })
      .catch(err => {
        console.error("Erreur models:", err);
        setErrorMessage("Failed to fetch your local models. Please try again. If the issue persists, contact the Erudi team for support.");
        setModels([]);
      });
  };

  useEffect(() => {
    fetch(`${API_BASE}/hardware/training`)
      .then(res => {
        if (!res.ok) setErrorMessage("Failed to fetch hardware information. Please try again. If the issue persists, contact the Erudi team for support.");
        return res.json();
      })
      .then(data => {
        setHw({
          storage_path: data.storage_path ?? "coming soon...",
          ram_available: `${data.available_ram_gb} GB`,
          total_ram_gb: `${data.total_ram_gb} GB`,
          disk_available: `${data.disk_available_gb} GB`,
          cpu_model: data.cpu_model,
          gpu_model: data.gpu_model ?? "No GPU detected",
          
          // Apple Silicon specific fields
          chip_model: data.chip_model ?? "Unknown",
          gpu_cores: data.gpu_cores ? `${data.gpu_cores} cores` : "N/A",
          estimated_gpu_tflops: data.estimated_gpu_tflops ? `${data.estimated_gpu_tflops} TFLOPS` : "N/A",
          memory_bandwidth_gbs: data.memory_bandwidth_gbs ? `${data.memory_bandwidth_gbs} GB/s` : "N/A",
          neural_engine_tops: data.neural_engine_tops ? `${data.neural_engine_tops} TOPS` : "N/A",
          architecture: data.architecture ?? "Unknown",
          is_apple_silicon: data.is_apple_silicon ?? false,
          mps_available: data.mps_available ?? false,
          unified_memory: data.unified_memory ?? false,
          
          // Legacy field (null for Apple Silicon unified memory)
          gpu_vram_total: data.unified_memory ? "Unified Memory" : (data.gpu_vram_total_gb ? `${data.gpu_vram_total_gb} GB` : "No GPU detected"),
          
          // Performance scores
          global_finetuning_score: data.global_finetuning_score ? `${data.global_finetuning_score}/100` : "N/A",
          global_finetuning_label: data.global_finetuning_label ? data.global_finetuning_label : "N/A",
          cpu_eval_score: data.cpu_eval_score ? `${data.cpu_eval_score}/100` : "N/A",
          gpu_eval_score: data.gpu_eval_score ? `${data.gpu_eval_score}/100` : "N/A",
          memory_score: data.memory_score ? `${data.memory_score}/100` : "N/A",
        });
      })
      .catch(err => {
        console.error("Erreur hardware:", err);
        setErrorMessage("Failed to fetch hardware information. Please try again. If the issue persists, contact the Erudi team for support.");
        // Set default values in case of error
        setHw({
          storage_path: "Error fetching",
          ram_available: "Error fetching",
          disk_available: "Error fetching",
          cpu_model: "Error fetching",
          gpu_model: "Error fetching",
          chip_model: "Error fetching",
          gpu_cores: "Error fetching",
          estimated_gpu_tflops: "Error fetching",
          memory_bandwidth_gbs: "Error fetching",
          neural_engine_tops: "Error fetching",
          architecture: "Error fetching",
          is_apple_silicon: false,
          mps_available: false,
          unified_memory: false,
          gpu_vram_total: "Error fetching",
          global_finetuning_score: "Error fetching",
          global_finetuning_label: "Error fetching",
          cpu_eval_score: "Error fetching",
          gpu_eval_score: "Error fetching",
          memory_score: "Error fetching",
        });
      });
    fetchModels();
  }, []);

  // Handle model selection from ModelLibrary
  const handleModelSelect = (modelId) => {
    setSelectedModel(modelId);
  };

  // Handle model name change from ModelLibrary
  const handleModelNameChange = (name) => {
    setModelName(name);
  };

  const handleStartTraining = (trainingFiles) => {
    if (!selectedModel || !modelName) {
      alert("Please select a model and enter a model name");
      return;
    }

    const fineTuningTask = {
      id: `finetuning_${Date.now()}`,
      name: `${modelName}`,
      size: 'Variable',
      description: `Fine-tuning with ${trainingFiles.length} files`,
      downloadUrl: null,
      trainingFiles: trainingFiles,
      selectedModel: selectedModel,
      modelName: modelName,
    };

    openProgressModal(fineTuningTask, {
      isFineTuning: true,
      onComplete: handleFineTuningComplete,
      onError: handleFineTuningError,
    });
  };

  const handleFineTuningComplete = () => {
    console.log('Fine-tuning completed!');
    setSelectedModel(null);
    setModelName("");
    resetDatasetCard();
    // Force page refresh with a small delay to ensure state reset completes
    setTimeout(() => {
      window.location.href = window.location.href;
    }, 100);
  };

  const handleFineTuningError = (error) => {
    console.error('Fine-tuning error:', error);
    setErrorMessage("Fine-tuning failed. Please try again. If the issue persists, contact the Erudi team for support.");
  };

  const resetDatasetCard = () => {
    if (datasetCardResetRef.current) {
      datasetCardResetRef.current();
    }
  };

  const closeErrorModal = () => {
    setErrorMessage("");
    setSelectedModel(null);
    setModelName("");
    resetDatasetCard();
    console.log('Closing error modal and resetting state');
    // Force page refresh with a small delay to ensure state reset completes
    setTimeout(() => {
      window.location.href = window.location.href;
    }, 100);
  };

  return (
    <>
      <div className="flex h-screen bg-[#071b18]">
        <Sidebar disabled={isTraining} />
        
        <main className="flex-1 p-4 md:p-8 space-y-8 overflow-auto custom-scroll">
          {/* Top Section: Hardware + Model Library */}
          <div className="flex flex-col lg:flex-row 2xl:h-[40%] gap-8">
            <div className="lg:w-3/5">
              <HardwareInfo hw={hw} />
            </div>
            
            <div className="lg:w-2/5">
              <ModelLibrary 
                models={models}
                selectedModel={selectedModel}
                modelName={modelName}
                onModelSelect={handleModelSelect}
                onModelNameChange={handleModelNameChange}
                onRefresh={fetchModels}
              />
            </div>
          </div>

          {/* Bottom Section: Dataset */}
          <div className="flex flex-col lg:h-[50%] 2xl:h-[56%] gap-8">
            <DatasetCard 
              selectedModel={selectedModel} 
              modelName={modelName}
              onStartTraining={handleStartTraining}
              isTraining={isTraining}
              onReset={datasetCardResetRef}
            />
          </div>
        </main>
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
    </>
  );
}
