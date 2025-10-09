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
import logoErudi from "../../assets/erudi.png";



export default function LandingPage() {
  const { open } = useDownloadModal();
  const [showWelcome, setShowWelcome] = useState(false);
  const [showLoadingPopup, setShowLoadingPopup] = useState(false);
  const [hardwareInfo, setHardwareInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [cudaStatus, setCudaStatus] = useState(null);
  const [cudaLoading, setCudaLoading] = useState(true);
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
        // setShowWelcome(!data.has_already_displayed);
        setShowWelcome(true); // Always show for now for testing
      } catch (error) {
        console.error("Failed to fetch welcome popup status:", error);
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
        console.error("Failed to fetch hardware evaluation:", error);
        setHardwareInfo({
          error: "Failed to evaluate hardware capabilities. Please contact the Erudi team for support."
        });
      } finally {
        setLoading(false);
      }
    };

    // Fetch CUDA status
    const fetchCudaStatus = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/hardware/has_cuda`);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        setCudaStatus(data);
      } catch (error) {
        console.error("Failed to fetch CUDA status:", error);
        setCudaStatus({ has_cuda: false, error: "Failed to check CUDA status" });
      } finally {
        setCudaLoading(false);
      }
    };
    fetchWelcomePopupStatus();
    fetchHardwareEvaluation();
    fetchCudaStatus();
  }, []);

  const closeWelcome = () => {
    
    // If hardware info is still loading, show intermediate popup
    if (loading || cudaLoading) {
      setShowLoadingPopup(true);
      // Don't close the welcome modal yet, let the loading modal appear on top
      return;
    }
    // Otherwise, close normally
    setShowWelcome(false);
  };

  const closeLoadingOnly = () => {
    // Close only the loading popup, keep welcome popup open
    setShowLoadingPopup(false);
  };

  // Auto-close loading popup when hardware info is ready
  useEffect(() => {
    if (!loading && !cudaLoading && showLoadingPopup) {
      setShowLoadingPopup(false);
      setShowWelcome(false);
    }
  }, [loading, cudaLoading, showLoadingPopup]);

  const handleLocalModelRefresh = () => {
    if (localModelsRef.current) {
      localModelsRef.current.reloadLocalModels();
    }
  };

  return (
    <div className="flex h-screen">
      {/* Left mini sidebar */}
      <Sidebar />

      {/* Main sidebar */}
      <aside className="w-[30%] sm:w-[35%] xl:w-[25%]  bg-[#272727] text-white flex flex-col p-6 space-y-6 transition-all duration-300">
        <h1 className="text-3xl font-bold">Models</h1>
        <ModelCollapsibleSection 
          title="Local Models" 
          ref={localModelsRef}
        />
        <ModelCollapsibleSection
         title="Remote Models"
         onDownload={(model) => open(model)}
         onLocalModelRefresh={handleLocalModelRefresh}
       />
      </aside>

      {/* Main content */}
      <main className="flex-1 bg-[#071b18] relative overflow-auto">
        <TrainNewModelCard />
      </main>

      <LoadingModal 
        show={showLoadingPopup} 
        onClose={closeLoadingOnly}
        loading={loading}
        cudaLoading={cudaLoading}
      />
      <WelcomeModal 
        show={showWelcome} 
        onClose={closeWelcome} 
        hardwareInfo={hardwareInfo}
        loading={loading}
        cudaStatus={cudaStatus}
        cudaLoading={cudaLoading}
      />

    </div>
  );
}