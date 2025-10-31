import React, { useEffect, useState, useRef } from "react";
import { HelpCircle, X } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import DatasetCard from "../components/DatasetCard";
import HardwareInfo from "../components/HardwareInfo";
import ModelLibrary from "../components/ModelLibrary";
import InfoRow from "../components/InfoRow";
import DragDropArea from "../components/DragDropArea";
import Dropdown from "../components/Dropdown";
import { useKnowledgeBase } from "../contexts/KnowledgeBaseContext";
import ErrorModal from "../components/modals/ErrorModal";
import { API_BASE_URL } from "../config/api.js";

export default function KnowledgeBasePage() {
  const { open: openKnowledgeBase, isCreating, isStarting } = useKnowledgeBase();
  const [searchParams] = useSearchParams();
  const [errorMessage, setErrorMessage] = useState("");
  const [isValidated, setIsValidated] = useState(false);

  const [hw, setHw] = useState({
    storage_path: "soon...",
    disk_available: "fetching…",
    cpu_model: "fetching…",
    gpu_model: "fetching…",
    chip_model: "fetching…", // Apple Silicon chip
    gpu_cores: "fetching…",
    estimated_gpu_tflops: "fetching…",
    memory_bandwidth_gbs: "fetching…",
    neural_engine_tops: "fetching…",
    architecture: "fetching…",
    is_apple_silicon: false,
    mps_available: false,
    unified_memory: false,
    gpu_vram_total: "N/A", // Not applicable for unified memory
    gpu_vram_free: "N/A", // Not applicable for unified memory
    ram_available: "fetching…",
    total_ram_gb: "fetching…",
    global_inference_score: "fetching…",
    global_inference_label: "fetching…",
  });

  const [selectedModel, setSelectedModel] = useState(null);
  const [modelName, setModelName] = useState("");
  const [description, setDescription] = useState("");
  const [paths, setPaths] = useState([]);
  const [models, setModels] = useState([]);

  // Handle files dropped from DragDropArea
  const addDroppedFiles = (newPathObjects) => {
    console.log("KnowledgeBasePage received files:", newPathObjects);

    // Handle complete replacement of the file list (for when files are removed)
    // or addition of new files (for when files are added)
    setPaths(() => {
      const newPaths = newPathObjects.map((pathObj) => pathObj.path || pathObj);
      console.log("Setting paths to:", newPaths);
      return Array.from(new Set(newPaths)); // Remove duplicates but don't merge with previous
    });
  };

  const closeErrorModal = () => {
    setErrorMessage("");
  };

  /* helper to determine bullet or icon for rating field */
  const getRatingBulletOrIcon = (rating) => {
    console.log("Rating received:", rating);

    // If it's still "fetching..." show question mark icon
    if (rating && rating.includes("fetching")) {
      return {
        type: "icon",
        value: <HelpCircle className="w-3 h-3 sm:w-4 sm:h-4 text-gray-400" />,
      };
    }

    // Color code based on rating
    if (rating === "Amazing" || rating === "Excellent" || rating === "Very High") {
      return { type: "bullet", value: "bg-emerald-400" };
    } else if (rating === "Good" || rating === "Medium" || rating === "Bad" || rating === "High") {
      return { type: "bullet", value: "bg-orange-400" };
    } else {
      return { type: "bullet", value: "bg-red-500" };
    }
  };

  const submitTrainForm = async () => {
    console.log("submitTrainForm called");
    console.log("selectedModel:", selectedModel);
    console.log("modelName:", modelName);
    console.log("paths:", paths);
    console.log("paths.length:", paths.length);

    if (!selectedModel || !modelName.trim() || paths.length === 0) {
      console.log("Validation failed:");
      console.log("  !selectedModel:", !selectedModel);
      console.log("  !modelName.trim():", !modelName.trim());
      console.log("  paths.length === 0:", paths.length === 0);
      setErrorMessage("Please fill in all required fields");
      return;
    }

    console.log("Validation passed, proceeding with creation");
    setErrorMessage("");

    const task = {
      paths,
      selectedModel,
      modelName: modelName.trim(),
      description: description.trim(),
    };

    openKnowledgeBase(task, {
      onComplete: () => {
        console.log("Assistant created successfully");
        setIsValidated(true);
        // Reset form after a delay
        setTimeout(() => {
          setIsValidated(false);
          setPaths([]);
          setModelName("");
          setDescription("");
        }, 3000);
      },
      onError: (error) => {
        console.error("Assistant creation failed:", error);
        setErrorMessage(error);
      },
    });
  };

  const handleKnowledgeBaseComplete = () => {
    console.log("Knowledge base creation completed!");
    setSelectedModel(null);
    setModelName("");
    setDescription("");
    setPaths([]);
    setErrorMessage("");
    // Force page refresh with a small delay to ensure state reset completes
    setTimeout(() => {
      window.location.href = window.location.href;
    }, 100);
  };

  const handleKnowledgeBaseError = (error) => {
    console.error("Knowledge base creation error:", error);
    setErrorMessage(
      "Assistant creation failed. Please try again. If the issue persists, contact the Erudi team for support.",
    );
  };

  const fetchModels = () => {
    fetch(`${API_BASE_URL}/llms/local`)
      .then((res) => {
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        return res.json();
      })
      .then((data) => {
        console.log("Fetched models:", data, "Count:", data ? data.length : 0);
        setModels(data || []);
      })
      .catch((err) => {
        console.error("Erreur models:", err);
        setModels([]);
      });
  };

  useEffect(() => {
    fetch(`${API_BASE_URL}/hardware/app_startup`)
      .then((res) => {
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        return res.json();
      })
      .then((data) => {
        setHw((prevHw) => ({
          ...prevHw,
          global_inference_score: data.global_inference_score
            ? `${data.global_inference_score}/100`
            : "N/A",
          global_inference_label: data.global_inference_label ? data.global_inference_label : "N/A",
        }));
      })
      .catch((err) => {
        console.error("Erreur hardware:", err);
        setHw((prevHw) => ({
          ...prevHw,
          global_inference_score: "Error fetching",
          global_inference_label: "Error fetching",
        }));
      });
    fetchModels();
  }, []);

  // Handle URL parameter for model selection
  useEffect(() => {
    const modelParam = searchParams.get("model");
    if (modelParam && models.length > 0) {
      // Find the model by name or id
      const foundModel = models.find(
        (model) =>
          model.name === modelParam ||
          model.id === modelParam ||
          model.name.toLowerCase() === modelParam.toLowerCase(),
      );

      if (foundModel) {
        console.log("Setting model from URL parameter:", foundModel);
        setSelectedModel(foundModel.id);
        setModelName(foundModel.name);
      } else {
        console.warn("Model not found for parameter:", modelParam);
      }
    }
  }, [searchParams, models]); // Re-run when searchParams or models change

  // Handle model selection from ModelLibrary
  const handleModelSelect = (modelId) => {
    setSelectedModel(modelId);
  };

  // Handle model name change from ModelLibrary
  const handleModelNameChange = (name) => {
    setModelName(name);
  };

  return (
    <div className="flex h-screen bg-[#071b18]">
      <Sidebar />

      <main className="flex-1 p-4 md:p-6 lg:p-8 flex flex-col gap-4 md:gap-6 overflow-hidden">
        {/* Top Section: Hardware + Model Library */}
        <div className="flex flex-col lg:flex-row gap-4 md:gap-6 flex-1 min-h-0">
          <div className="relative rounded-2xl overflow-hidden shadow-xl flex-1 min-w-[340px] border border-[#385B4F] border-[0.3px] bg-[rgba(22,40,36,0.45)] flex flex-col">
            <div
              className="absolute inset-0 opacity-[11%] pointer-events-none"
              style={{
                background:
                  "linear-gradient(135deg,rgba(217,217,217,1) 0%,rgba(217,217,217,0.26) 26%,rgba(0,204,133,1) 100%)",
              }}
            />
            <div className="absolute inset-0 mix-blend-overlay pointer-events-none" />
            <div className="relative z-10 px-4 py-3 sm:px-6 sm:py-4 md:px-8 md:py-5 flex flex-col h-full overflow-hidden">
              {/* Title */}
              <h2 className="text-white text-xl sm:text-2xl md:text-3xl font-bold mb-3 md:mb-4 flex-shrink-0">
                Knowledge Base
              </h2>

              {/* Knowledge Base description - scrollable */}
              <div className="flex-1 overflow-y-auto custom-scroll pr-2">
                <p className="text-gray-300 text-sm sm:text-base md:text-lg leading-relaxed">
                  A Knowledge Base lets you teach your AI about your specific documents, files, and
                  information without changing the AI model itself.
                  <br />
                  <br />
                  Think of it like giving your AI a personal library to reference when answering
                  questions. Upload your PDFs, documents, notes, or any text files, and your AI will
                  use them to give more accurate and relevant answers about your specific topics.
                  <br />
                  <br />
                  This is perfect when you want your AI to know about your business, research, or
                  personal documents, but don't need to permanently change how the AI thinks. It's
                  faster and easier than training a new model, and you can update your knowledge
                  anytime by adding or removing documents.
                  <br />
                  <br />
                  Use Knowledge Bases for: company documents, research papers, manuals, personal
                  notes, or any information you want your AI to reference when chatting with you.
                </p>
              </div>

              {/* Rating - fixed at bottom */}
              <div className="flex-shrink-0 mt-3 md:mt-4">
                <InfoRow
                  label="Chat Capabilities Rating :"
                  isHeader={true}
                  {...(getRatingBulletOrIcon(hw.global_inference_label).type === "bullet"
                    ? { bullet: getRatingBulletOrIcon(hw.global_inference_label).value }
                    : { icon: getRatingBulletOrIcon(hw.global_inference_label).value })}
                >
                  <div className="flex items-center gap-2">
                    <span>{hw.global_inference_label || "Poor"}</span>
                    {hw.global_inference_score && (
                      <span className="text-xs text-gray-400 bg-gray-800/50 px-2 py-0.5 rounded-full border border-gray-600/30">
                        {hw.global_inference_score}
                      </span>
                    )}
                  </div>
                </InfoRow>
              </div>
            </div>
          </div>

          <ModelLibrary
            models={models}
            selectedModel={selectedModel}
            modelName={modelName}
            onModelSelect={handleModelSelect}
            onModelNameChange={handleModelNameChange}
            onRefresh={fetchModels}
          />
        </div>

        {/* Bottom Section: Dataset */}
        <div className="flex flex-col flex-1 min-h-0">
          <div className="bg-[#2B2B2B] rounded-2xl p-4 md:p-6 lg:p-8 text-white flex flex-col lg:flex-row gap-4 md:gap-6 shadow-lg h-full overflow-hidden">
            <div className="flex flex-col gap-3 md:gap-4 w-full lg:w-[44%] overflow-hidden">
              <div className="flex flex-col w-full h-full overflow-hidden">
                {/* Title */}
                <h3 className="text-white text-lg sm:text-xl md:text-2xl font-semibold mb-3 md:mb-4 text-center flex-shrink-0">
                  Tell your assistant what you would use it for!
                </h3>

                {/* Description input */}
                <textarea
                  className="w-full flex-1 bg-[#1A1A1A] text-white rounded-lg p-3 md:p-4 resize-none border border-white/10 focus:outline-none focus:ring-2 focus:ring-emerald-400/60 focus:border-emerald-400/60 transition-all placeholder-gray-400 text-sm sm:text-base"
                  placeholder="Write a description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>

              <div className="flex flex-col items-center gap-3 flex-shrink-0">
                {isValidated ? (
                  <div className="w-full text-center">
                    <div className="text-emerald-400 text-sm">
                      Data attached to your Assistant successfully!
                    </div>
                    <div className="inline-flex items-center gap-2 py-3"></div>
                  </div>
                ) : (
                  <button
                    className="py-2 md:py-3 px-6 md:px-8 rounded-full bg-emerald-500 text-white font-semibold shadow-lg hover:bg-emerald-400 transition disabled:opacity-50 text-sm sm:text-base"
                    onClick={() => {
                      console.log("Button clicked!");
                      submitTrainForm();
                    }}
                    disabled={isCreating || isStarting}
                  >
                    {isCreating ? "Creating Assistant..." : "Create Assistant"}
                  </button>
                )}

                {/* Error Modal */}
                <ErrorModal errorMessage={errorMessage} onClose={closeErrorModal} />
              </div>
            </div>

            <div className="w-full lg:w-[56%] h-full overflow-hidden">
              <DragDropArea onFilesAdded={addDroppedFiles} />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
