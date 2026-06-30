import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import ModelCollapsibleSection from "../components/ModelCollapsibleSection";
import ModelCard from "../components/ModelCard";
import ExploreModelCard from "../components/ExploreModelCard";
import MachineReadout from "../components/MachineReadout";
import HuggingFaceSearchPanel from "../components/HuggingFaceSearchPanel";
import CategorySections from "../components/CategorySections";
import CatalogFilters from "../components/CatalogFilters";
import ExploreIndex from "../components/ExploreIndex";
import ConnectionStatus from "../components/ConnectionStatus";
import ModelInfoModal from "../components/modals/ModelInfoModal";
import DeleteModelModal from "../components/modals/DeleteModelModal";
import MessageModal from "../components/modals/MessageModal";
import { useDownloadModal } from "../contexts/DownloadModalContext";
import HardwareLoadingPopup from "../components/LoadingPopup";
import { RefreshCcw } from "lucide-react";
import WelcomeModal from "../components/modals/WelcomeModal";
import logoErudi from "../assets/images/logos/logoerudifinal.png";
import { API_BASE_URL } from "../config/api";
import { transformAppStartupInfo } from "../utils/hardwareTransform";
import { downloadErrorMessage } from "../utils/downloadStatus";
import { createLogger } from "../utils/logger";
import { splitByBase } from "../utils/modelCatalog";
import { rankByFit, pickFlagships, applyCatalogFilters } from "../utils/hardwareFit";

export default function LandingPage() {
  const log = createLogger("LandingPage");

  const { open } = useDownloadModal();
  const navigate = useNavigate();
  const [showWelcome, setShowWelcome] = useState(false);
  const [showLoadingPopup, setShowLoadingPopup] = useState(false);
  const [hardwareInfo, setHardwareInfo] = useState(null);
  const [machineDetail, setMachineDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [localModels, setLocalModels] = useState([]);
  const [remoteModels, setRemoteModels] = useState([]);
  const [modelsLoading, setModelsLoading] = useState(true);
  const [selectedModelInfo, setSelectedModelInfo] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [deleteConfirmation, setDeleteConfirmation] = useState({ show: false, model: null });
  const [brainSidebarCollapsed, setBrainSidebarCollapsed] = useState(false);
  const [communityOpen, setCommunityOpen] = useState(false);
  const [filters, setFilters] = useState({ size: "any", fitOnly: false });
  const localModelsRef = useRef(null);

  // Helper function to parse model metadata
  const parseMetadata = (metadataString) => {
    if (!metadataString) {
      return {};
    }
    try {
      const lines = metadataString.split("\n");
      const metadata = {};
      lines.forEach((line) => {
        const trimmedLine = line.trim();
        if (trimmedLine.includes(":")) {
          const [key, ...valueParts] = trimmedLine.split(":");
          const value = valueParts.join(":").trim();
          const cleanKey = key.trim().toLowerCase().replace(/\s+/g, "_");
          metadata[cleanKey] = value;
        }
      });
      return metadata;
    } catch (error) {
      return {};
    }
  };

  const transformRemote = (model) => {
    const metadata = parseMetadata(model.model_metadata);
    return {
      id: model.id,
      name: model.name,
      size: metadata.size || "Unknown",
      // Fields the details modal reads, derived from the parsed metadata.
      parameters: metadata.parameters || (model.param_size ? `${model.param_size}B` : "Unknown"),
      downloads: metadata.downloads || "Unknown",
      likes: metadata.likes || "Unknown",
      author: metadata.author || "Unknown",
      library: metadata.library || "Unknown",
      pipeline: metadata.pipeline || "Unknown",
      lastUpdate: metadata.last_modified || "Unknown",
      description: model.description,
      runnable: model.runnable !== false,
      is_base: model.is_base === true,
      category: model.category || "general",
      type: model.type,
      param_size: model.param_size,
      link: model.link,
      quantized: model.quantized,
      metadata,
      rawMetadata: model.model_metadata,
    };
  };

  const transformLocal = (model) => {
    const metadata = parseMetadata(model.model_metadata);
    return {
      id: model.id,
      name: model.name,
      size: metadata.size || "Unknown",
      parameters: metadata.parameters || "Unknown",
      lastUpdate: metadata.last_modified || "Unknown",
      isOnline: false,
      description: model.description,
      metadata,
      rawMetadata: model.model_metadata,
    };
  };

  useEffect(() => {
    const fetchWelcomePopupStatus = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/startup/welcome-popup`);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        setShowWelcome(!data.has_already_displayed);
      } catch (error) {
        log.error("Error fetching welcome popup status:", error);
      }
    };

    const fetchHardwareEvaluation = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/hardware/app_startup`);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        setHardwareInfo(transformAppStartupInfo(data));
      } catch (error) {
        setHardwareInfo({
          backend_type: "unknown",
          error:
            "Failed to evaluate hardware capabilities. Please contact the Erudi team for support.",
        });
      } finally {
        setLoading(false);
      }
    };

    // Richer hardware detail for the machine readout (chip, memory, GPU cores).
    const fetchMachineDetail = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/hardware/detailed`);
        if (response.ok) {
          const data = await response.json();
          setMachineDetail(data.hardware || null);
        }
      } catch (error) {
        log.error("Error fetching hardware detail:", error);
      }
    };

    const fetchModels = async () => {
      setModelsLoading(true);
      try {
        const localResponse = await fetch(`${API_BASE_URL}/llms/local`);
        if (localResponse.ok) {
          const localData = await localResponse.json();
          setLocalModels(localData.map(transformLocal));
        }
        const remoteResponse = await fetch(`${API_BASE_URL}/llms/remote`);
        if (remoteResponse.ok) {
          const remoteData = await remoteResponse.json();
          setRemoteModels(remoteData.map(transformRemote));
        }
      } catch (error) {
        log.error("Error fetching models:", error);
      } finally {
        setModelsLoading(false);
      }
    };

    fetchWelcomePopupStatus();
    fetchHardwareEvaluation();
    fetchMachineDetail();
    fetchModels();
  }, []);

  const closeWelcome = () => {
    if (loading) {
      setShowLoadingPopup(true);
      return;
    }
    setShowWelcome(false);
  };

  const closeLoadingOnly = () => setShowLoadingPopup(false);

  const handleMainPageRefresh = async () => {
    await reloadLocalModels();
  };

  const reloadLocalModels = async () => {
    setModelsLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/llms/local`);
      if (res.ok) {
        const localData = await res.json();
        setLocalModels(localData.map(transformLocal));
      } else {
        setErrorMessage(
          "Failed to fetch local models. Please try again and contact the Erudi team for support."
        );
      }
    } catch (err) {
      setErrorMessage(
        "Failed to fetch local models. Please try again and contact the Erudi team for support."
      );
    } finally {
      await new Promise((resolve) => setTimeout(resolve, 600));
      setModelsLoading(false);
    }
  };

  // Derived: Base vs Community (backend is_base), hardware-fit window, and the
  // best-fitting base models for the recommendation rail (#122 redesign).
  const { base: baseModels, community: communityModels } = splitByBase(remoteModels);
  const range = hardwareInfo
    ? { min: hardwareInfo.recommended_param_min, max: hardwareInfo.recommended_param_max }
    : null;
  const recommended = pickFlagships(baseModels, range, 3);
  const filteredBase = applyCatalogFilters(baseModels, filters, range);
  const filteredCommunity = applyCatalogFilters(communityModels, filters, range);
  const filtersActive = filters.size !== "any" || filters.fitOnly;

  const machine = {
    chip: machineDetail?.mlx_chip_model
      ? `Apple ${machineDetail.mlx_chip_model}`
      : machineDetail?.gpu_name || machineDetail?.cpu_model || "Your hardware",
    backend: (hardwareInfo?.backend_type || "").toUpperCase(),
    memoryGb: machineDetail?.total_memory_gb ? Math.round(machineDetail.total_memory_gb) : null,
    gpuCores: machineDetail?.mlx_gpu_cores || null,
    bandwidth: machineDetail?.memory_bandwidth_gbs
      ? Math.round(machineDetail.memory_bandwidth_gbs)
      : null,
    inferenceLabel: hardwareInfo?.global_inference_label,
    inferenceScore: hardwareInfo?.global_inference_score,
    range,
  };

  const handleDownload = (model) => {
    if (open) {
      open(model, {
        onComplete: async () => {
          await reloadLocalModels();
          if (localModelsRef.current) {
            localModelsRef.current.reloadLocalModels();
          }
        },
        onError: (reason) => {
          const msg = downloadErrorMessage(reason);
          if (msg) setErrorMessage(msg);
        },
      });
    }
  };

  const handleInfo = (model) => setSelectedModelInfo(model);
  const handleChat = (model) => navigate(`/erudi/chat?model=${encodeURIComponent(model.name)}`);
  const handleKnowledgeBase = (model) =>
    navigate(`/erudi/attach_knowledge_base?model=${encodeURIComponent(model.name)}`);
  const handleDelete = (model) => setDeleteConfirmation({ show: true, model });

  const confirmDelete = async () => {
    if (!deleteConfirmation.model) {
      return;
    }
    const modelToDelete = deleteConfirmation.model;
    setDeleteConfirmation({ show: false, model: null });
    try {
      const response = await fetch(`${API_BASE_URL}/llms/${modelToDelete.id}`, {
        method: "DELETE",
      });
      if (response.ok) {
        setSuccessMessage(`Model ${modelToDelete.name} has been successfully deleted.`);
        await reloadLocalModels();
        if (localModelsRef.current) {
          localModelsRef.current.reloadLocalModels();
        }
      } else {
        throw new Error(`Failed to delete model: ${response.status}`);
      }
    } catch (error) {
      log.error("Failed to delete model:", error);
      setErrorMessage(
        "Failed to delete the model. Please try again and contact the Erudi team for support."
      );
    }
  };

  const cancelDelete = () => setDeleteConfirmation({ show: false, model: null });
  const handleToggleBrainSidebar = () => setBrainSidebarCollapsed(!brainSidebarCollapsed);

  // Left-rail Explore index scrolls the main panel to a section.
  const scrollToSection = (id) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="flex h-screen">
      <Sidebar
        showBrainCollapsible={true}
        onToggleBrainSidebar={handleToggleBrainSidebar}
        brainCollapsed={brainSidebarCollapsed}
      />

      <aside
        className={`${brainSidebarCollapsed ? "w-0 opacity-0 overflow-hidden" : "w-64 opacity-100 p-6 overflow-visible"} bg-[#272727] text-white flex flex-col transition-all duration-300`}
      >
        <div className="flex items-center justify-start mb-6 flex-shrink-0">
          <img
            src={logoErudi}
            alt="Erudi"
            className="h-[40px] ml-2 w-auto cursor-pointer hover:opacity-80 transition-opacity"
            onClick={() => setShowWelcome(true)}
            onError={(e) => log.error("Failed to load logo:", e.target.src)}
          />
        </div>
        <div className="mb-6 flex-shrink-0">
          <ModelCollapsibleSection
            title="Local Models"
            ref={localModelsRef}
            onLocalModelRefresh={handleMainPageRefresh}
          />
        </div>
        <div className="flex-1 min-h-0 overflow-y-auto custom-scroll">
          <ExploreIndex
            models={filteredBase}
            communityCount={filteredCommunity.length}
            hasRecommended={recommended.length > 0}
            loading={modelsLoading}
            onJump={scrollToSection}
          />
        </div>
        <div className="flex-shrink-0">
          <ConnectionStatus />
        </div>
      </aside>

      {/* Main explore panel */}
      <main className="flex-1 bg-[var(--canvas)] relative custom-scroll overflow-auto">
        <div className="mx-auto max-w-6xl px-8 py-8 space-y-9">
          {/* Hero: machine readout — the spine of the panel */}
          <MachineReadout machine={machine} loading={loading} />

          {/* Local models */}
          <section>
            <div className="flex items-center justify-between mb-4">
              <span className="eyebrow">Installed</span>
              <button
                onClick={() => reloadLocalModels()}
                title="Refresh installed models"
                className="text-[var(--ink-dim)] hover:text-[var(--ink)] transition-colors"
              >
                <RefreshCcw className="w-4 h-4" />
              </button>
            </div>
            {modelsLoading ? (
              <div className="flex items-center gap-2 text-[var(--ink-faint)] mono text-xs py-6">
                <span className="w-2 h-2 rounded-full bg-[var(--fit-good)] animate-pulse" />
                loading installed models…
              </div>
            ) : localModels.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
                {localModels.map((model) => (
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
              </div>
            ) : (
              <p className="text-[var(--ink-dim)] text-sm">
                No models installed yet. Pick one below. Your machine handles {""}
                <span className="mono text-[var(--fit-good)]">
                  {range ? `${range.min}–${range.max}B` : "small"}
                </span>{" "}
                comfortably.
              </p>
            )}
          </section>

          {/* Recommended for your machine — flagship, instruct-only picks */}
          {recommended.length > 0 && (
            <section id="explore-recommended" className="rise scroll-mt-6">
              <span className="eyebrow !text-[var(--fit-good)]">Recommended for your machine</span>
              <p className="text-[13px] text-[var(--ink-dim)] mt-1.5 mb-4">
                Popular, ready-to-chat models that run well on your {machine.chip}.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
                {recommended.map((model) => (
                  <ExploreModelCard
                    key={`rec-${model.id ?? model.link}`}
                    model={model}
                    range={range}
                    onDownload={handleDownload}
                    onInfo={handleInfo}
                  />
                ))}
              </div>
            </section>
          )}

          {/* Live Hugging Face search — the research tool */}
          <div id="explore-search" className="scroll-mt-6">
            <HuggingFaceSearchPanel range={range} onDownload={handleDownload} onInfo={handleInfo} />
          </div>

          {/* Browse by capability */}
          <section>
            <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
              <span className="eyebrow">Browse by capability</span>
              <CatalogFilters value={filters} onChange={setFilters} hasRange={!!range} />
            </div>
            {filtersActive && filteredBase.length === 0 ? (
              <p className="text-[var(--ink-dim)] text-sm py-8 text-center">
                No models match these filters. Widen the size range or turn off “Fits my machine”.
              </p>
            ) : (
              <CategorySections
                models={filteredBase}
                range={range}
                loading={modelsLoading}
                onDownload={handleDownload}
                onInfo={handleInfo}
              />
            )}
          </section>

          {/* Community fine-tunes — collapsed by default to keep the panel calm */}
          {filteredCommunity.length > 0 && (
            <section id="explore-community" className="scroll-mt-6">
              <button
                className="flex items-center gap-3 w-full text-left mb-4 group"
                onClick={() => setCommunityOpen((o) => !o)}
              >
                <span className="eyebrow group-hover:text-[var(--ink)] transition-colors">
                  Community fine-tunes
                </span>
                <span className="mono text-[11px] text-[var(--ink-faint)]">
                  {filteredCommunity.length}
                </span>
                <span className="h-px flex-1 bg-white/10" />
                <span className="mono text-[11px] text-[var(--ink-dim)] group-hover:text-[var(--fit-good)] transition-colors">
                  {communityOpen ? "Hide" : "Show all"}
                </span>
              </button>
              {communityOpen && (
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3 max-h-[640px] overflow-y-auto custom-scroll pr-1">
                  {rankByFit(filteredCommunity, range).map((model) => (
                    <ExploreModelCard
                      key={`com-${model.id ?? model.link}`}
                      model={model}
                      range={range}
                      onDownload={handleDownload}
                      onInfo={handleInfo}
                    />
                  ))}
                </div>
              )}
            </section>
          )}
        </div>
      </main>

      <WelcomeModal
        isOpen={showWelcome}
        onClose={closeWelcome}
        hardwareInfo={hardwareInfo}
        loading={loading}
      />
      <ModelInfoModal
        modelInfo={selectedModelInfo}
        isOpen={!!selectedModelInfo}
        onClose={() => setSelectedModelInfo(null)}
        onDownload={handleDownload}
      />
      <DeleteModelModal
        isOpen={deleteConfirmation.show}
        model={deleteConfirmation.model}
        onConfirm={confirmDelete}
        onCancel={cancelDelete}
      />
      <MessageModal
        isOpen={!!successMessage}
        title="Success"
        message={successMessage}
        type="success"
        onClose={() => setSuccessMessage("")}
      />
      <MessageModal
        isOpen={!!errorMessage}
        title="Error"
        message={errorMessage}
        type="error"
        onClose={() => setErrorMessage("")}
      />
      <HardwareLoadingPopup show={showLoadingPopup} loading={loading} onClose={closeLoadingOnly} />
    </div>
  );
}
