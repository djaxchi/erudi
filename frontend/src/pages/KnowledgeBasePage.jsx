import React, { useEffect, useState } from "react";
import { HelpCircle } from "lucide-react";
import { useSearchParams, useNavigate } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import ModelLibrary from "../components/ModelLibrary";
import InfoRow from "../components/InfoRow";
import DragDropArea from "../components/DragDropArea";
import { useKnowledgeBase } from "../contexts/KnowledgeBaseContext";
import ErrorModal from "../components/modals/ErrorModal";
import apiClient from "../services/api/client";
import EmbeddingModelGateModal from "../components/modals/EmbeddingModelGateModal";
import { GATE, gateStateFromStatus, shouldPoll, isGateBlocking } from "../utils/embeddingGate";
import { createLogger } from "../utils/logger";

const log = createLogger("KnowledgeBasePage");

export default function KnowledgeBasePage() {
  const { open: openKnowledgeBase, isCreating, isStarting } = useKnowledgeBase();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
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

  // --- Embedding-model gate (#146): the KB needs the e5 model on disk. ---
  const [gateState, setGateState] = useState(GATE.CHECKING);
  const [gateError, setGateError] = useState(null);

  // Handle files dropped from DragDropArea
  const addDroppedFiles = (newPathObjects) => {
    log.log("Received files from drag-drop area", newPathObjects);

    // Handle complete replacement of the file list (for when files are removed)
    // or addition of new files (for when files are added)
    setPaths(() => {
      const newPaths = newPathObjects.map((pathObj) => pathObj.path || pathObj);
      log.log("Setting file paths", newPaths);
      return Array.from(new Set(newPaths)); // Remove duplicates but don't merge with previous
    });
  };

  const closeErrorModal = () => {
    setErrorMessage("");
  };

  /* helper to determine bullet or icon for rating field */
  const getRatingBulletOrIcon = (rating) => {
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
    log.log("Submitting knowledge base form", {
      selectedModel,
      modelName,
      pathCount: paths.length,
    });

    if (!selectedModel || !modelName.trim() || paths.length === 0) {
      log.warn("Knowledge base form validation failed", {
        selectedModel: !selectedModel,
        modelNameEmpty: !modelName.trim(),
        noPaths: paths.length === 0,
      });
      setErrorMessage("Please fill in all required fields");
      return;
    }

    log.log("Validation passed, proceeding with creation");
    setErrorMessage("");

    const task = {
      paths,
      selectedModel,
      modelName: modelName.trim(),
      description: description.trim(),
    };

    openKnowledgeBase(task, {
      onComplete: () => {
        log.log("Knowledge base assistant created successfully");
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
        log.error("Knowledge base creation failed", error);
        setErrorMessage(error);
      },
    });
  };

  const fetchModels = () => {
    apiClient
      .get("/llms/local")
      .then((data) => {
        log.log("Fetched models", { count: data ? data.length : 0 });
        setModels(data || []);
      })
      .catch((err) => {
        log.error("Failed to fetch models", err);
        setModels([]);
      });
  };

  useEffect(() => {
    apiClient
      .get("/hardware/app_startup")
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
        log.error("Failed to fetch hardware info", err);
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
          model.name.toLowerCase() === modelParam.toLowerCase()
      );

      if (foundModel) {
        log.log("Setting model from URL parameter", { name: foundModel.name });
        setSelectedModel(foundModel.id);
        setModelName(foundModel.name);
      } else {
        log.warn("Model not found for parameter", { modelParam });
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

  // --- Embedding-model gate (#146): presence is filesystem-driven; the modal
  // blocks the KB page until the model is on disk. ---
  const refreshGateStatus = async (prev) => {
    try {
      const status = await apiClient.get("/knowledge_base/embedding-model/status");
      setGateError(status.error || null);
      setGateState((current) => gateStateFromStatus(status, prev ?? current));
      return status;
    } catch (err) {
      log.warn("Embedding-model status check failed", err);
      return null;
    }
  };

  // Check presence on mount; if a download is already running, enter the spinner.
  useEffect(() => {
    refreshGateStatus(GATE.CHECKING);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Poll only while a download is in flight (survives leaving/returning to KB).
  useEffect(() => {
    if (!shouldPoll(gateState)) return undefined;
    const id = setInterval(() => refreshGateStatus(), 2000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gateState]);

  const handleGateDownload = async () => {
    setGateState(GATE.DOWNLOADING);
    setGateError(null);
    try {
      await apiClient.post("/knowledge_base/embedding-model/download");
    } catch (err) {
      log.warn("Embedding-model download request failed", err);
      setGateError(String(err?.message || err));
      setGateState(GATE.ERROR);
    }
  };

  // "Not now" / decline: the KB is unusable without the embedding model, so
  // leave the page entirely (back to the landing) rather than sit on a dead KB.
  const handleGateLeave = () => navigate("/erudi/models");
  // "Close" after a successful download: the model is present now, stay on the KB.
  const handleGateClose = () => setGateState(GATE.HIDDEN);

  return (
    <div className="flex h-screen bg-[#071b18]">
      <Sidebar />

      {/* The gate overlay is scoped to this <main> (relative + absolute modal):
          it blurs and blocks the KB content only, keeping the sidebar usable
          while the embedding model downloads. */}
      <main className="relative flex-1 p-4 md:p-6 lg:p-8 flex flex-col gap-4 md:gap-6 overflow-hidden">
        {isGateBlocking(gateState) && (
          <EmbeddingModelGateModal
            state={gateState}
            error={gateError}
            onDownload={handleGateDownload}
            onLeave={handleGateLeave}
            onClose={handleGateClose}
          />
        )}
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
                  personal documents, but don&apos;t need to permanently change how the AI thinks.
                  It&apos;s faster and easier than training a new model, and you can update your
                  knowledge anytime by adding or removing documents.
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
