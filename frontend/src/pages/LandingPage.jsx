import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import ModelCollapsibleSection from "../components/ModelCollapsibleSection";
import ModelCard from "../components/ModelCard";
import ModelInfoModal from "../components/modals/ModelInfoModal";
import DeleteModelModal from "../components/modals/DeleteModelModal";
import MessageModal from "../components/modals/MessageModal";
import { useDownloadModal } from "../contexts/DownloadModalContext";
import HardwareLoadingPopup from "../components/LoadingPopup";
import { RefreshCcw } from "lucide-react";
import logoErudi from "../img/logo-erudi.png";

const API_BASE_URL = "http://127.0.0.1:8000";

export default function LandingPage() {
  const { open } = useDownloadModal();
  const navigate = useNavigate();
  const [showWelcome, setShowWelcome] = useState(false);
  const [showLoadingPopup, setShowLoadingPopup] = useState(false);
  const [hardwareInfo, setHardwareInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [localModels, setLocalModels] = useState([]);
  const [remoteModels, setRemoteModels] = useState([]);
  const [modelsLoading, setModelsLoading] = useState(true);
  const [selectedModelInfo, setSelectedModelInfo] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [deleteConfirmation, setDeleteConfirmation] = useState({ show: false, model: null });
  const [brainSidebarCollapsed, setBrainSidebarCollapsed] = useState(false);
  const localModelsRef = useRef(null);

  useEffect(() => {
    // To know if it should spawn the welcome popup
    const fetchWelcomePopupStatus = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/main_window/welcome-popup`);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        setShowWelcome(!data.has_already_displayed);
      } catch (error) {
        console.error("Error fetching welcome popup status:", error);
      }
    };

    // Fetch hardware evaluation on component mount
    const fetchHardwareEvaluation = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/hardware/app_startup`);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        setHardwareInfo(data);
      } catch (error) {
        setHardwareInfo({
          error: "Failed to evaluate hardware capabilities. Please contact the Erudi team for support."
        });
      } finally {
        setLoading(false);
      }
    };
fetchWelcomePopupStatus();
  // Helper function to parse model metadata
  const parseMetadata = (metadataString) => {
    if (!metadataString) return {};
    
    try {
      const lines = metadataString.split('\n');
      const metadata = {};
      
      lines.forEach(line => {
        const trimmedLine = line.trim();
        if (trimmedLine.includes(':')) {
          const [key, ...valueParts] = trimmedLine.split(':');
          const value = valueParts.join(':').trim();
          
          // Clean up the key
          const cleanKey = key.trim().toLowerCase().replace(/\s+/g, '_');
          metadata[cleanKey] = value;
        }
      });
      
      return metadata;
    } catch (error) {
      return {};
    }
  };

  // Fetch models from backend
  const fetchModels = async () => {
      setModelsLoading(true);
      try {
        // Fetch local models
        const localResponse = await fetch(`${API_BASE_URL}/main_window/llms/local`);
        if (localResponse.ok) {
          const localData = await localResponse.json();
          // Transform API data to match our UI format
          const transformedLocalModels = localData.map(model => {
            const metadata = parseMetadata(model.model_metadata);
            return {
              id: model.id,
              name: model.name,
              size: metadata.size || "Unknown",
              parameters: metadata.parameters || "Unknown", 
              lastUpdate: metadata.last_modified || "Unknown",
              isOnline: false, // Default to offline
              description: model.description,
              metadata: metadata,
              rawMetadata: model.model_metadata
            };
          });
          setLocalModels(transformedLocalModels);
        }

        // Fetch remote models
        const remoteResponse = await fetch(`${API_BASE_URL}/main_window/llms/remote`);
        if (remoteResponse.ok) {
          const remoteData = await remoteResponse.json();
          // Transform API data to match our UI format
          const transformedRemoteModels = remoteData.map(model => {
            const metadata = parseMetadata(model.model_metadata);
            return {
              id: model.id,
              name: model.name,
              size: metadata.size || "Unknown",
              parameters: metadata.parameters || "Unknown", 
              downloads: metadata.downloads || model.description || "Unknown",
              lastUpdate: metadata.last_modified || "Unknown",
              author: metadata.author || "Unknown",
              library: metadata.library || "Unknown",
              pipeline: metadata.pipeline || "Unknown",
              likes: metadata.likes || "Unknown",
              description: model.description,
              metadata: metadata,
              rawMetadata: model.model_metadata
            };
          });
          setRemoteModels(transformedRemoteModels);
        }
      } catch (error) {
        // Error fetching models
        console.error("Error fetching models:", error);
      } finally {
        setModelsLoading(false);
      }
    };

    fetchHardwareEvaluation();
    fetchModels();
  }, []);

  const closeWelcome = () => {
    // If hardware info is still loading, show intermediate popup
    if (loading) {
      setShowLoadingPopup(true);
      return;
    }
    // Otherwise, close normally
    setShowWelcome(false);
  };

  const closeLoadingOnly = () => {
    // Close only the loading popup, keep welcome popup open
    setShowLoadingPopup(false);
  };

  const handleLocalModelRefresh = () => {
    if (localModelsRef.current) {
      localModelsRef.current.reloadLocalModels();
    }
  };

  const handleMainPageRefresh = async () => {
    // This function refreshes the main page local models when called from ModelCollapsibleSection
    await reloadLocalModels();
  };

  const reloadLocalModels = async () => {
    setModelsLoading(true);
    try {
      const url = `${API_BASE_URL}/main_window/llms/local`;
      const res = await fetch(url);
      if (res.ok) setLocalModels(await res.json());
      else
        setErrorMessage(
          "Failed to fetch local models. Please try again and contact the Erudi team for support."
        );
    } catch (err) {
      setErrorMessage(
        "Failed to fetch local models. Please try again and contact the Erudi team for support."
      );
    } finally {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      setModelsLoading(false);
    }
  };

  const scrollToExplore = () => {
    const exploreSection = document.getElementById('explore-models');
    if (exploreSection) {
      exploreSection.scrollIntoView({ behavior: 'smooth' });
    } else {
      console.warn('Explore models section not found');
    }
  };

  // Derived data from fetched models
  const baseModelNames = [
    "Mistral-7B-Instruct-v0.3",
    "Mistral-7B-v0.3", 
    "Gemma-3-1B-it",
    "Gemma-2-2B-it",
    "Gemma-3-4B-it"
  ];
  
  const baseModels = remoteModels.filter(model => 
    baseModelNames.includes(model.name)
  );
  
  const communityModels = remoteModels.filter(model => 
    !baseModelNames.includes(model.name)
  );
  
  const modelsForYou = baseModels.slice(0, 6); // First 6 base models

  // Search functionality
  const filterModels = (models, query) => {
    if (!query.trim()) return models;
    
    return models.filter(model => 
      model.name.toLowerCase().includes(query.toLowerCase()) ||
      (model.parameters && model.parameters.toLowerCase().includes(query.toLowerCase())) ||
      (model.size && model.size.toLowerCase().includes(query.toLowerCase()))
    );
  };

  // Filtered models based on search query
  const filteredLocalModels = filterModels(localModels, searchQuery);
  const filteredBaseModels = filterModels(baseModels, searchQuery);
  const filteredModelsForYou = filterModels(modelsForYou, searchQuery);
  const filteredCommunityModels = filterModels(communityModels, searchQuery);

  // Check if any models match the search
  const hasSearchResults = filteredLocalModels.length > 0 ||
                          filteredBaseModels.length > 0 || 
                          filteredModelsForYou.length > 0 || 
                          filteredCommunityModels.length > 0;

  // Event handlers
  const handleDownload = (model) => {
    // Implement download logic or use existing download modal
    if (open) {
      open(model, {
        onComplete: async () => {
          // Refresh local models on both main page and sidebar
          await reloadLocalModels();
          if (localModelsRef.current) {
            localModelsRef.current.reloadLocalModels();
          }
        },
        onError: (err) => {
          setErrorMessage("Download failed. Please try again.");
        }
      });
    }
  };

  const handleInfo = (model) => {
    setSelectedModelInfo(model);
  };

  const handleChat = (model) => {
    // Navigate to chat page with model parameter
    navigate(`/main_window/chat?model=${encodeURIComponent(model.name)}`);
  };

  const handleKnowledgeBase = (model) => {
    // Navigate to knowledge base page with model parameter
    navigate(`/main_window/attach_knowledge_base?model=${encodeURIComponent(model.name)}`);
  };

  const handleDelete = (model) => {
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
        // Reload local models on both main page and sidebar
        await reloadLocalModels();
        if (localModelsRef.current) {
          localModelsRef.current.reloadLocalModels();
        }
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

  const handleToggleBrainSidebar = () => {
    setBrainSidebarCollapsed(!brainSidebarCollapsed);
  };

  return (
    <div className="flex h-screen">
      {/* Left mini sidebar */}
      <Sidebar 
        showBrainCollapsible={true}
        onToggleBrainSidebar={handleToggleBrainSidebar}
        brainCollapsed={brainSidebarCollapsed}
      />

      {/* Main sidebar */}
      <aside className={`${brainSidebarCollapsed ? 'w-0 opacity-0' : 'w-[30%] sm:w-[35%] xl:w-[25%] opacity-100 p-6 space-y-6 '} bg-[#272727] text-white flex flex-col transition-all duration-300 overflow-hidden`}>
        <div className="flex items-center justify-start">
          <img 
            src={logoErudi} 
            alt="Erudi" 
            className="h-[55px] ml-2 w-auto" 
            onError={(e) => {
              console.error('Failed to load logo:', e.target.src);
            }}
            onLoad={() => console.log('Logo loaded successfully')}
          />
        </div>
        <ModelCollapsibleSection 
          title="Local Models" 
          ref={localModelsRef}
          onLocalModelRefresh={handleMainPageRefresh}
        />
        <ModelCollapsibleSection
          title="Remote Models"
         hasSearch={true}
         onDownload={handleDownload}
         onLocalModelRefresh={handleMainPageRefresh}
        />
      </aside>

      {/* Main content */}
      <main className="flex-1 bg-[#071b18] relative overflow-auto">
        <div className="p-8 space-y-8">
          {/* Local Models Section */}
          <section>
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-2xl font-bold text-white">Local Models</h2>
              <RefreshCcw
                className="w-4 h-4 hover:opacity-70  text-white cursor-pointer"
                onClick={(e) => {
                  e.stopPropagation();
                  reloadLocalModels();
                }}
              />
            </div>
            <div className="grid grid-cols-3 gap-4 max-h-[480px] overflow-y-auto pr-2">
              {modelsLoading ? (
                <div className="col-span-3 text-center py-8">
                  <div className="flex items-center justify-center">
                    <div className="w-6 h-6 border-2 border-white/20 border-t-white rounded-full animate-spin mr-3"></div>
                    <p className="text-gray-400">Loading local models...</p>
                  </div>
                </div>
              ) : filteredLocalModels.length > 0 ? (
                <>
                  {filteredLocalModels.map((model) => (
                    <ModelCard
                      key={model.id}
                      model={model}
                      type="local"
                      onChat={handleChat}
                      onInfo={handleInfo}
                      onKnowledgeBase={handleKnowledgeBase}
                      onDelete={handleDelete}
                    />
                  ))}
                  {!searchQuery && (
                    <ModelCard type="add" onDownload={scrollToExplore} />
                  )}
                </>
              ) : searchQuery ? (
                <div className="col-span-3 text-center py-8">
                  <p className="text-gray-400">No local models found for "{searchQuery}"</p>
                </div>
              ) : (
                <ModelCard type="add" onDownload={scrollToExplore} />
              )}
            </div>
          </section>

          {/* Sticky Header for Explore Models */}
          <div className="sticky top-0 bg-[#071b18] backdrop-blur-md z-10 py-6 border-b border-white/10">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-2xl font-bold text-white">Explore Models</h2>
              <div className="flex items-center gap-3">
                <div className="relative">
                  <input 
                    type="text" 
                    placeholder="Looking for a model?"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="bg-[#1a1a1a]/60 border border-white/10 rounded-lg px-3 py-2 pl-8 pr-8 text-sm text-white placeholder-gray-400 focus:outline-none focus:border-white/30"
                  />
                </div>
                <RefreshCcw
                  className="w-4 h-4 hover:opacity-70 text-white cursor-pointer"
                  onClick={(e) => {
                    e.stopPropagation();
                    reloadLocalModels();
                  }}
                />
              </div>
            </div>
          </div>

          {/* Explore Models Section */}
          <section id="explore-models">

            {/* Base Models Subsection */}
            <div className="mb-6 pt-3">
              <h3 className="text-lg font-semibold text-white mb-3">
                Base Models
                {searchQuery && (
                  <span className="text-xs text-gray-400 ml-2">
                    ({filteredBaseModels.length} results)
                  </span>
                )}
              </h3>
              <div className="grid grid-cols-3 gap-4 max-h-[480px] overflow-y-auto pr-2">
                {modelsLoading ? (
                  <div className="col-span-3 text-center py-8">
                    <div className="flex items-center justify-center">
                      <div className="w-6 h-6 border-2 border-white/20 border-t-white rounded-full animate-spin mr-3"></div>
                      <p className="text-gray-400">Loading base models...</p>
                    </div>
                  </div>
                ) : filteredBaseModels.length > 0 ? (
                  filteredBaseModels.map((model) => (
                    <ModelCard
                      key={model.id}
                      model={model}
                      type="base"
                      onDownload={handleDownload}
                      onInfo={handleInfo}
                    />
                  ))
                ) : searchQuery ? (
                  <div className="col-span-3 text-center py-8">
                    <p className="text-gray-400">No base models found for "{searchQuery}"</p>
                  </div>
                ) : (
                  <div className="col-span-3 text-center py-8">
                    <p className="text-gray-400">No base models available</p>
                  </div>
                )}
              </div>
            </div>
          </section>

          {/* Models For You Section */}
          <section>
            <h3 className="text-xl font-semibold text-white mb-4">
              Models For You
              {searchQuery && (
                <span className="text-sm text-gray-400 ml-2">
                  ({filteredModelsForYou.length} results)
                </span>
              )}
            </h3>
            <div className="grid grid-cols-3 gap-6 max-h-[600px] overflow-y-auto pr-2">
              {modelsLoading ? (
                <div className="col-span-3 text-center py-8">
                  <div className="flex items-center justify-center">
                    <div className="w-6 h-6 border-2 border-white/20 border-t-white rounded-full animate-spin mr-3"></div>
                    <p className="text-gray-400">Loading recommended models...</p>
                  </div>
                </div>
              ) : filteredModelsForYou.length > 0 ? (
                filteredModelsForYou.map((model) => (
                  <ModelCard
                    key={`foryou-${model.id}`}
                    model={model}
                    type="base"
                    onDownload={handleDownload}
                    onInfo={handleInfo}
                  />
                ))
              ) : searchQuery ? (
                <div className="col-span-3 text-center py-8">
                  <p className="text-gray-400">No recommended models found for "{searchQuery}"</p>
                </div>
              ) : (
                <div className="col-span-3 text-center py-8">
                  <p className="text-gray-400">No recommended models available</p>
                </div>
              )}
            </div>
          </section>

          {/* Community Models Section */}
          <section>
            <h3 className="text-lg font-semibold text-white mb-3">
              Community Models
              {searchQuery && (
                <span className="text-xs text-gray-400 ml-2">
                  ({filteredCommunityModels.length} results)
                </span>
              )}
            </h3>
            <div className="grid grid-cols-3 gap-4 max-h-[480px] overflow-y-auto pr-2">
              {modelsLoading ? (
                <div className="col-span-3 text-center py-8">
                  <div className="flex items-center justify-center">
                    <div className="w-6 h-6 border-2 border-white/20 border-t-white rounded-full animate-spin mr-3"></div>
                    <p className="text-gray-400">Loading community models...</p>
                  </div>
                </div>
              ) : filteredCommunityModels.length > 0 ? (
                filteredCommunityModels.map((model) => (
                  <ModelCard
                    key={`community-${model.id}`}
                    model={model}
                    type="base"
                    onDownload={handleDownload}
                    onInfo={handleInfo}
                  />
                ))
              ) : searchQuery ? (
                <div className="col-span-3 text-center py-8">
                  <p className="text-gray-400">No community models found for "{searchQuery}"</p>
                </div>
              ) : (
                <div className="col-span-3 text-center py-8">
                  <p className="text-gray-400">No community models available</p>
                </div>
              )}
            </div>
          </section>

          {/* No Results Message */}
          {searchQuery && !hasSearchResults && (
            <div className="text-center py-12">
              <div className="text-gray-400 text-lg mb-2">No models found</div>
              <p className="text-gray-500">
                No models match your search for "{searchQuery}". Try a different search term.
              </p>
              <button
                onClick={() => setSearchQuery("")}
                className="mt-4 px-4 py-2 bg-white/10 hover:bg-white/20 text-white rounded-lg transition-colors"
              >
                Clear Search
              </button>
            </div>
          )}
        </div>
      </main>

      {/* Welcome Popup */}
      {showWelcome && (
        <div className="fixed inset-0 bg-black bg-opacity-60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-[#2B2B2B] rounded-2xl border border-white/10 shadow-2xl max-w-4xl w-full h-[85vh] flex flex-col">
            {/* Header */}
            <div className="p-4 border-b border-white/10 flex-shrink-0">
              <div className="flex items-center justify-between">
                <h2 className="text-2xl font-bold text-white flex items-center gap-3">
                  🎉 Welcome to Erudi!
                </h2>
                <button
                  onClick={closeWelcome}
                  className="text-gray-400 hover:text-white transition-colors"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
                  </svg>
                </button>
              </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto flex flex-col">
              {/* Logo Section */}
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                  <div className="text-6xl font-bold text-white mb-2">
                    erudi
                  </div>
                  <div className="text-lg text-gray-400">
                    Personal AI Training Platform
                  </div>
                </div>
              </div>
              
              {/* Bottom Content */}
              <div className="p-4 text-white">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {/* Left Column */}
                  <div className="space-y-4">
                    <p className="text-lg">
                      Welcome to your personal AI training platform! Get ready to chat and specialize your own AI models.
                    </p>
                    
                    <div className="bg-amber-900/20 border border-amber-600/30 rounded-lg p-4">
                      <div className="flex items-start gap-3">
                        <span className="text-xl">⚠️</span>
                        <div>
                          <p className="text-amber-200 font-medium mb-2">Important Notice</p>
                          <p className="text-amber-100 text-sm mb-3">
                            Erudi is in early alpha stage and optimized for Apple Silicon Macs. 
                            Features may change, and you might encounter bugs.
                          </p>
                          
                          {/* System Requirements */}
                          <div className="bg-[#1a1a1a] rounded-lg p-3 border border-white/10">
                            <p className="text-amber-200 font-medium mb-2">System Requirements:</p>
                            <div className="space-y-1.5 text-sm">
                              <div className="flex items-center justify-between">
                                <span className="text-amber-100">Apple Silicon Chip Required</span>
                                <span className="text-lg">🍏</span>
                              </div>
                              <div className="flex items-center justify-between">
                                <span className="text-amber-100">Minimum 8GB Memory for Small Models</span>
                                <span className="text-lg">🧠</span>
                              </div>
                              <div className="flex items-center justify-between">
                                <span className="text-amber-100">10+ GB Disk Space</span>
                                <span className="text-lg">💾</span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Right Column */}
                  <div className="space-y-4">
                    {/* Hardware Evaluation */}
                    <div className="bg-[#1a1a1a] rounded-lg p-4 border border-white/10">
                      <h3 className="text-lg font-semibold mb-3 text-emerald-400">
                        🖥️ Hardware Evaluation
                      </h3>
                      
                      {loading ? (
                        <div className="flex items-center justify-center py-8">
                          <div className="w-8 h-8 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin"></div>
                          <span className="ml-3 text-gray-300">We are evaluating your hardware...</span>
                        </div>
                      ) : hardwareInfo?.error ? (
                        <div className="text-red-400 bg-red-900/20 border border-red-600/30 rounded-lg p-3">
                          <p className="font-medium">⚠️ Evaluation Failed</p>
                          <p className="text-sm mt-1">{hardwareInfo.error}</p>
                        </div>
                      ) : hardwareInfo ? (
                        <div className="space-y-3">
                          {/* Performance Scores */}
                          <div className="grid grid-cols-1 gap-3">
                            <div className="bg-[#242424] rounded-lg p-3 border border-white/5">
                              <p className="text-sm text-gray-400">Chat Performance</p>
                              <div className="flex items-center gap-2">
                                <p className="font-medium">{Math.round(hardwareInfo.global_inference_score)}%</p>
                                <span className={`text-xs px-2 py-1 rounded-full ${
                                  hardwareInfo.global_inference_score >= 70 ? 'bg-green-900/30 text-green-400' :
                                  hardwareInfo.global_inference_score >= 50 ? 'bg-yellow-900/30 text-yellow-400' :
                                  'bg-red-900/30 text-red-400'
                                }`}>
                                  {hardwareInfo.global_inference_label || 'Unknown'}
                                </span>
                              </div>
                              <p className="text-xs text-gray-500 mt-1">AI model chat performance</p>
                            </div>

                            <div className="bg-[#242424] rounded-lg p-3 border border-white/5">
                              <p className="text-sm text-gray-400">Training Performance</p>
                              <div className="flex items-center gap-2">
                                <p className="font-medium">{Math.round(hardwareInfo.global_finetuning_score)}%</p>
                                <span className={`text-xs px-2 py-1 rounded-full ${
                                  hardwareInfo.global_finetuning_score >= 70 ? 'bg-green-900/30 text-green-400' :
                                  hardwareInfo.global_finetuning_score >= 50 ? 'bg-yellow-900/30 text-yellow-400' :
                                  'bg-red-900/30 text-red-400'
                                }`}>
                                  {hardwareInfo.global_finetuning_label || 'Unknown'}
                                </span>
                              </div>
                              <p className="text-xs text-gray-500 mt-1">AI model training performance</p>
                            </div>
                          </div>

                          {/* Performance Summary */}
                          <div className="bg-[#242424] rounded-lg p-3 border border-white/5">
                            <div className="flex items-start gap-2">
                              <span className="text-lg">
                                {(hardwareInfo.global_inference_score >= 70 && hardwareInfo.global_finetuning_score >= 70) ? '🚀' :
                                 (hardwareInfo.global_inference_score >= 50 || hardwareInfo.global_finetuning_score >= 50) ? '⚡' : '⚠️'}
                              </span>
                              <div>
                                <p className="font-medium text-white mb-1">Summary</p>
                                <p className="text-xs text-gray-300">
                                  {(hardwareInfo.global_inference_score >= 70 && hardwareInfo.global_finetuning_score >= 70) 
                                    ? 'Excellent performance for AI workloads!'
                                    : (hardwareInfo.global_inference_score >= 50 || hardwareInfo.global_finetuning_score >= 50)
                                    ? 'Good performance, some operations may be slower.'
                                    : 'Limited performance. Consider hardware upgrades.'
                                  }
                                </p>
                              </div>
                            </div>
                          </div>
                        </div>
                      ) : null}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-white/10 flex-shrink-0">
              <div className="flex justify-end">
                <button
                  onClick={closeWelcome}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white px-6 py-2 rounded-lg transition-colors font-medium"
                >
                  Get Started
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Model Info Modal */}
      <ModelInfoModal
        modelInfo={selectedModelInfo}
        isOpen={!!selectedModelInfo}
        onClose={() => setSelectedModelInfo(null)}
        onDownload={handleDownload}
      />

      {/* Delete Confirmation Modal */}
      <DeleteModelModal
        isOpen={deleteConfirmation.show}
        model={deleteConfirmation.model}
        onConfirm={confirmDelete}
        onCancel={cancelDelete}
      />

      {/* Success Message Modal */}
      <MessageModal
        isOpen={!!successMessage}
        title="Success"
        message={successMessage}
        type="success"
        onClose={() => setSuccessMessage("")}
      />

      {/* Error Message Modal */}
      <MessageModal
        isOpen={!!errorMessage}
        title="Error"
        message={errorMessage}
        type="error"
        onClose={() => setErrorMessage("")}
      />

      {/* Loading Popup (appears on top of welcome popup when hardware is still loading) */}
      <HardwareLoadingPopup show={showLoadingPopup} loading={loading} onClose={closeLoadingOnly} />

    </div>
  );
}