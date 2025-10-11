import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { RefreshCcw } from "lucide-react";
import Sidebar from "../components/Sidebar";
import ModelCollapsibleSection from "../components/ModelCollapsibleSection";
import ModelCard from "../components/ModelCard";
import WelcomeModal from "../components/modals/WelcomeModal";
import ModelInfoModal from "../components/modals/ModelInfoModal";
import DeleteModelModal from "../components/modals/DeleteModelModal";
import MessageModal from "../components/modals/MessageModal";
import HardwareLoadingPopup from "../components/modals/HardwareLoadingPopup";
import { useDownloadModal } from "../contexts/DownloadModalContext";
import { API_BASE_URL } from "../config/api";
import { Search, MonitorCheck, SearchCode, Blocks, Star, Users } from "lucide-react";
import logoErudi from "../../assets/logoerudifinal.png";


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
              isOnline: false,
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
              lastUpdate: metadata.last_modified || "Unknown",
              isOnline: true,
              description: model.description,
              metadata: metadata,
              rawMetadata: model.model_metadata,
              downloads: metadata.downloads || model.description || "Unknown",
              likes: metadata.likes || "Unknown",
              author: metadata.author || "Unknown",
              library: metadata.library || "Unknown"
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

  const handleMainPageRefresh = async () => {
    // Refresh both the main page and sidebar local models
    await reloadLocalModels();
    if (localModelsRef.current) {
      localModelsRef.current.reloadLocalModels();
    }
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
      <aside className={`${brainSidebarCollapsed ? 'w-0 opacity-0' : 'w-80 opacity-100 p-6 space-y-6 '} bg-[#272727] text-white flex flex-col transition-all duration-300 overflow-hidden`}>
        <div className="flex items-center justify-start">
          <img 
            src={logoErudi} 
            alt="Erudi" 
            className="h-[40px] ml-2 w-auto" 
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
              <div className="flex items-center gap-2">
                <MonitorCheck className="w-6 h-6 text-white" />
                <h2 className="text-2xl font-bold text-white">Local Models</h2>
              </div>
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
              <div className="flex items-center gap-2">
                <SearchCode className="w-6 h-6 text-white" />
                <h2 className="text-2xl font-bold text-white">Explore Models</h2>
              </div>
              <div className="flex items-center gap-3">
                <div className="relative">
                  <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 transform -translate-y-1/2 pointer-events-none" />
                  <input 
                    type="text" 
                    placeholder="Looking for a model?"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="bg-[#1a1a1a]/60 border border-white/10 rounded-2xl px-3 py-1 pl-8 pr-8 text-sm text-white placeholder-gray-400 focus:outline-none focus:border-white/30"
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
              <div className="flex items-center gap-2 mb-4">
                <Blocks className="w-5 h-5 text-white" />
                <h3 className="text-lg font-semibold text-white">
                  Base Models
                  {searchQuery && (
                    <span className="text-xs text-gray-400 ml-2">
                      ({filteredBaseModels.length} results)
                    </span>
                  )}
                </h3>
              </div>
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
            <div className="flex items-center gap-2 mb-4">
              <Star className="w-5 h-5 text-white" />
              <h3 className="text-xl font-semibold text-white">
                Models For You
                {searchQuery && (
                  <span className="text-sm text-gray-400 ml-2">
                    ({filteredModelsForYou.length} results)
                  </span>
                )}
              </h3>
            </div>
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
            <div className="flex items-center gap-2 mb-3">
              <Users className="w-5 h-5 text-white" />
              <h3 className="text-lg font-semibold text-white">
                Community Models
                {searchQuery && (
                  <span className="text-xs text-gray-400 ml-2">
                    ({filteredCommunityModels.length} results)
                  </span>
                )}
              </h3>
            </div>
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

      {/* Welcome Modal */}
      <WelcomeModal
        show={showWelcome}
        onClose={closeWelcome}
        hardwareInfo={hardwareInfo}
        loading={loading}
      />

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
      <HardwareLoadingPopup 
        show={showLoadingPopup} 
        loading={loading} 
        onClose={closeLoadingOnly}
      />
    </div>
  );
}