import React, { useEffect, useState, useRef } from "react";
import { HelpCircle, X } from "lucide-react";
import Sidebar from "../components/Sidebar";
import DatasetCard from "../components/DatasetCard";
import HardwareInfo from "../components/HardwareInfo";
import ModelLibrary from "../components/ModelLibrary";
import InfoRow from "../components/InfoRow";
import DragDropArea from "../components/DragDropArea";
import Dropdown from "../components/Dropdown";
import { useKnowledgeBase } from "../contexts/KnowledgeBaseContext";

const API_BASE = "http://127.0.0.1:8000";

export default function KnowledgeBasePage() {
  const { open: openKnowledgeBase, isCreating, isStarting } = useKnowledgeBase();
  const [errorMsg, setErrorMsg] = useState('');
  const [isValidated, setIsValidated] = useState(false);
  
  const [hw, setHw] = useState({
    storage_path: "soon...",
    disk_available: "fetching…",
    cpu_model: "fetching…",
    gpu_model: "fetching…",
    chip_model: "fetching…",  // Apple Silicon chip
    gpu_cores: "fetching…",
    estimated_gpu_tflops: "fetching…",
    memory_bandwidth_gbs: "fetching…",
    neural_engine_tops: "fetching…",
    architecture: "fetching…",
    is_apple_silicon: false,
    mps_available: false,
    unified_memory: false,
    gpu_vram_total: "N/A",  // Not applicable for unified memory
    gpu_vram_free: "N/A",  // Not applicable for unified memory
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
    console.log('KnowledgeBasePage received files:', newPathObjects);
    
    // Handle complete replacement of the file list (for when files are removed)
    // or addition of new files (for when files are added)
    setPaths(() => {
      const newPaths = newPathObjects.map(pathObj => pathObj.path || pathObj);
      console.log('Setting paths to:', newPaths);
      return Array.from(new Set(newPaths)); // Remove duplicates but don't merge with previous
    });
  };

    /* helper to determine bullet or icon for rating field */
    const getRatingBulletOrIcon = (rating) => {
        console.log("Rating received:", rating);

        // If it's still "fetching..." show question mark icon
        if (rating && rating.includes("fetching")) {
            return { type: 'icon', value: <HelpCircle className="w-3 h-3 sm:w-4 sm:h-4 text-gray-400" /> };
        }

        // Color code based on rating
        if (rating === "Amazing" || rating === "Excellent" || rating === "Very High") {
            return { type: 'bullet', value: "bg-emerald-400" };
        } else if (rating === "Good" || rating === "Medium" || rating === "Bad" || rating === "High") {
            return { type: 'bullet', value: "bg-orange-400" };
        } else {
            return { type: 'bullet', value: "bg-red-500" };
        }
    };

    const submitTrainForm = async () => {
    console.log('submitTrainForm called');
    console.log('selectedModel:', selectedModel);
    console.log('modelName:', modelName);
    console.log('paths:', paths);
    console.log('paths.length:', paths.length);
    
    if (!selectedModel || !modelName.trim() || paths.length === 0) {
      console.log('Validation failed:');
      console.log('  !selectedModel:', !selectedModel);
      console.log('  !modelName.trim():', !modelName.trim());
      console.log('  paths.length === 0:', paths.length === 0);
      setErrorMsg('Please fill in all required fields');
      return;
    }

    console.log('Validation passed, proceeding with creation');
    setErrorMsg('');
    
    const task = {
      paths,
      selectedModel,
      modelName: modelName.trim(),
      description: description.trim(),
    };

    openKnowledgeBase(task, {
      onComplete: () => {
        console.log('Assistant created successfully');
        setIsValidated(true);
        // Reset form after a delay
        setTimeout(() => {
          setIsValidated(false);
          setPaths([]);
          setModelName('');
          setDescription('');
        }, 3000);
      },
      onError: (error) => {
        console.error('Assistant creation failed:', error);
        setErrorMsg(error);
      }
    });
  };

  const handleKnowledgeBaseComplete = () => {
    console.log('Knowledge base creation completed!');
    setSelectedModel(null);
    setModelName("");
    setDescription("");
    setPaths([]);
    setErrorMsg("");
    // Force page refresh with a small delay to ensure state reset completes
    setTimeout(() => {
      window.location.href = window.location.href;
    }, 100);
  };

  const handleKnowledgeBaseError = (error) => {
    console.error('Knowledge base creation error:', error);
    setErrorMessage("Assistant creation failed. Please try again. If the issue persists, contact the Erudi team for support.");
  };

  const fetchModels = () => {
    fetch(`${API_BASE}/main_window/llms/local`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        console.log("Fetched models:", data, "Count:", data ? data.length : 0);
        setModels(data || []);
      })
      .catch(err => {
        console.error("Erreur models:", err);
        setModels([]);
      });
  };

  useEffect(() => {
    fetch(`${API_BASE}/hardware/app_startup`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        setHw(prevHw => ({
          ...prevHw,
          global_inference_score: data.global_inference_score ? `${data.global_inference_score}/100` : "N/A",
          global_inference_label: data.global_inference_label ? data.global_inference_label : "N/A",
        }));
      })
      .catch(err => {
        console.error("Erreur hardware:", err);
        setHw(prevHw => ({
          ...prevHw,
          global_inference_score: "Error fetching",
          global_inference_label: "Error fetching",
        }));
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

  return (
    <div className="flex h-screen bg-[#071b18]">
      <Sidebar />
      
      <main className="flex-1 p-4 md:p-8 space-y-8 overflow-auto custom-scroll">
        {/* Top Section: Hardware + Model Library */}
        <div className="flex flex-col lg:flex-row 2xl:h-[40%] gap-8">
          <div className="relative rounded-2xl overflow-hidden shadow-xl flex-1 min-w-[340px] border border-[#385B4F] border-[0.3px]">
            <div className="absolute inset-0 opacity-[11%] pointer-events-none"
                style={{
                    background:
                        "linear-gradient(135deg,rgba(217,217,217,1) 0%,rgba(217,217,217,0.26) 26%,rgba(0,204,133,1) 100%)",
                }}
            />
            <div className="absolute inset-0 mix-blend-overlay pointer-events-none" />
            <div className="relative z-10 px-3 py-1.5 sm:px-4 sm:py-2 md:px-6 md:py-2.5 lg:py-3 space-y-3 sm:space-y-4">
                
                {/* Title */}
                <h2 className="text-white text-xl md:text-2xl font-bold">Knowledge Base</h2>
                
                {/* Lorem ipsum description */}
                <p className="text-gray-300 text-xs md:text-sm leading-relaxed">
                    Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
                    <br/><br/> 
                    Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.<br/><br/>
                    Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.<br/><br/>
                    Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.
                </p>

                <InfoRow
                    label="Chat Capabilities Rating :"
                    isHeader={true}
                    {...(getRatingBulletOrIcon(hw.global_inference_label).type === 'bullet'
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
        <div className="flex flex-col gap-8">
          <div className="bg-[#2B2B2B] rounded-2xl p-8 text-white flex flex-row gap-6 shadow-lg">
            <div className="flex flex-col gap-4 w-[44%]">
              <div className="flex flex-col w-full">
                {/* Title */}
                <h3 className="text-white text-lg font-semibold mb-4 text-center">
                  Tell your assistant what you would use it for!
                </h3>
                
                {/* Description input */}
                <textarea 
                  className="w-full h-40 bg-[#1A1A1A] text-white rounded-lg p-4 resize-none border border-white/10 focus:outline-none focus:ring-2 focus:ring-emerald-400/60 focus:border-emerald-400/60 transition-all placeholder-gray-400"
                  placeholder="Write a description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>
              
              <div className="flex flex-col items-center gap-4">
                {isValidated ? (
                  <div className="w-full text-center"> 
                    <div className="text-emerald-400 text-sm">
                      Assistant created successfully!
                    </div>
                    <div className="inline-flex items-center gap-2 py-3">
                      
                    </div>
                  </div>
                ) : isCreating ? (
                  <div className="w-full text-center"> 
                    <div className="text-emerald-400 text-sm">
                      We are creating your assistant
                    </div>
                    <div className="inline-flex items-center gap-2 py-3">
                      
                    </div>
                  </div>
                ) : isStarting ? (
                  <button 
                    className="py-2 sm:py-3 px-6 sm:px-8 rounded-full bg-emerald-500 text-white font-semibold shadow-lg flex items-center justify-center gap-2 text-xs sm:text-sm"
                    disabled={true}
                  >
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    Creating...
                  </button>
                ) : (
                  <button 
                    className="py-2 sm:py-3 px-6 sm:px-8 rounded-full bg-emerald-500 text-white font-semibold shadow-lg hover:bg-emerald-400 transition disabled:opacity-50 text-xs sm:text-sm"
                    onClick={() => {
                      console.log('Button clicked!');
                      submitTrainForm();
                    }}
                    disabled={isCreating || isStarting}
                  >
                    Create Assistant
                  </button>
                )}
                
                {errorMsg && (
                  <div className="text-red-400 text-sm text-center w-full">{errorMsg}</div>
                )}
              </div>
            </div>

            <div className="w-[56%] h-[100%]">
              <DragDropArea onFilesAdded={addDroppedFiles} />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
