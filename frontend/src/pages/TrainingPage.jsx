import React, { useEffect, useState, useRef } from "react";
import Sidebar from "../components/Sidebar";
import DatasetCard from "../components/DatasetCard";
import HardwareInfo from "../components/HardwareInfo";
import ModelLibrary from "../components/ModelLibrary";
import { useDownloadModal } from "../contexts/DownloadModalContext";
import { X } from "lucide-react";
import ErrorModal from "../components/modals/ErrorModal";
import { API_BASE_URL } from "../config/api";
import { transformTrainingInfo } from "../utils/hardwareTransform";
import { createLogger } from "../utils/logger";

export default function TrainingPage() {
  const log = createLogger("TrainingPage");

  const { open: openProgressModal, isTraining } = useDownloadModal();
  const [errorMessage, setErrorMessage] = useState("");
  const datasetCardResetRef = useRef(null);

  const [hw, setHw] = useState({
    storage_path: "soon...",
    disk_available: "fetching…",
    cpu_model: "fetching…",
    gpu_model: "fetching…",
    chip_model: "fetching…", // Apple Silicon chip (M1, M2, M3, etc.)
    gpu_cores: "fetching…", // Number of GPU cores
    estimated_gpu_tflops: "fetching…", // Estimated GPU performance
    memory_bandwidth_gbs: "fetching…", // Unified memory bandwidth
    neural_engine_tops: "fetching…", // Neural Engine performance
    architecture: "fetching…", // 3nm, 5nm, etc.
    is_apple_silicon: false,
    mps_available: false, // Metal Performance Shaders
    unified_memory: false, // Unified memory architecture
    gpu_vram_total: "N/A", // Not applicable for unified memory
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
    fetch(`${API_BASE_URL}/llms/local`)
      .then((res) => {
        if (!res.ok) {
          setErrorMessage(
            "Failed to fetch your local models. Please try again. If the issue persists, contact the Erudi team for support."
          );
        }
        return res.json();
      })
      .then((data) => {
        log.log("Fetched models:", data, "Count:", data ? data.length : 0);
        setModels(data || []);
      })
      .catch((err) => {
        log.error("Erreur models:", err);
        setErrorMessage(
          "Failed to fetch your local models. Please try again. If the issue persists, contact the Erudi team for support."
        );
        setModels([]);
      });
  };

  useEffect(() => {
    fetch(`${API_BASE_URL}/hardware/training_info`)
      .then((res) => {
        if (!res.ok) {
          setErrorMessage(
            "Failed to fetch hardware information. Please try again. If the issue persists, contact the Erudi team for support."
          );
        }
        return res.json();
      })
      .then((data) => {
        // Transform new API structure to UI format
        const transformed = transformTrainingInfo(data);
        setHw(transformed);
      })
      .catch((err) => {
        log.error("Erreur hardware:", err);
        setErrorMessage(
          "Failed to fetch hardware information. Please try again. If the issue persists, contact the Erudi team for support."
        );
        // Set default values in case of error
        setHw({
          backend_type: "unknown",
          storage_path: "Error fetching",
          ram_available: "Error fetching",
          total_ram_gb: "Error fetching",
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
          is_mlx: false,
          is_cuda: false,
          is_cpu: false,
          mps_available: false,
          unified_memory: false,
          gpu_vram_total: "Error fetching",
          global_finetuning_score: "Error fetching",
          global_finetuning_label: "Error fetching",
          cpu_score: "Error fetching",
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
      size: "Variable",
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
    log.log("Fine-tuning completed!");
    setSelectedModel(null);
    setModelName("");
    resetDatasetCard();
    // Force page refresh with a small delay to ensure state reset completes
    setTimeout(() => {
      window.location.href = window.location.href;
    }, 100);
  };

  const handleFineTuningError = (error) => {
    log.error("Fine-tuning error:", error);
    setErrorMessage(
      "Fine-tuning failed. Please try again. If the issue persists, contact the Erudi team for support."
    );
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
    log.log("Closing error modal and resetting state");
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

      <ErrorModal errorMessage={errorMessage} onClose={closeErrorModal} />
    </>
  );
}
