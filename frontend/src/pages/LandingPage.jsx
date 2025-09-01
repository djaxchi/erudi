import React, { useState, useEffect, useRef } from "react";
import Sidebar from "../components/Sidebar";
import ModelCollapsibleSection from "../components/ModelCollapsibleSection";
import TrainNewModelCard from "../components/TrainNewModelCard";
import { useDownloadModal } from "../contexts/DownloadModalContext";

const API_BASE_URL = "http://127.0.0.1:8000";

export default function LandingPage() {
  const { open } = useDownloadModal();
  const [showWelcome, setShowWelcome] = useState(false);
  const [showLoadingPopup, setShowLoadingPopup] = useState(false);
  const [hardwareInfo, setHardwareInfo] = useState(null);
  const [loading, setLoading] = useState(true);
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

    fetchWelcomePopupStatus();
    fetchHardwareEvaluation();
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

  return (
    <div className="flex h-screen">
      {/* Left mini sidebar */}
      <Sidebar />

      {/* Main sidebar */}
      <aside className="w-[30%] sm:w-[35%] xl:w-[25%]  bg-[#272727] text-white flex flex-col p-6 space-y-6">
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


      {/* Loading Popup (appears on top of welcome popup when hardware is still loading) */}
      {showLoadingPopup && (
        <div className="fixed inset-0 bg-black bg-opacity-80 backdrop-blur-sm flex items-center justify-center z-[60] p-4">
          <div className="bg-[#1B1B1B] rounded-2xl border border-white/20 shadow-2xl max-w-md w-full">
            {/* Header */}
            <div className="p-6 border-b border-white/10">
              <div className="flex items-center justify-between">
                <h3 className="text-xl font-bold text-white flex items-center gap-3">
                  ⏳ Please Wait
                </h3>
                <button
                  onClick={closeLoadingOnly}
                  className="text-gray-400 hover:text-white transition-colors"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
                  </svg>
                </button>
              </div>
            </div>

            {/* Content */}
            <div className="p-6">
              <div className="text-center">
                <div className="w-12 h-12 border-3 border-emerald-400 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                <p className="text-white font-medium mb-2">
                  Evaluating Hardware
                </p>
                <p className="text-gray-400 text-sm mb-4">
                  We're still checking your system capabilities. This will only take a moment.
                </p>
                <div className="space-y-2 text-xs text-gray-500">
                  <div className="flex items-center justify-between">
                    <span>Hardware Evaluation</span>
                    {loading ? (
                      <span className="text-yellow-400">⏳ Loading...</span>
                    ) : (
                      <span className="text-green-400">✅ Complete</span>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-white/10">
              <div className="flex justify-between">
                <button
                  onClick={closeLoadingOnly}
                  className="text-gray-400 hover:text-white transition-colors text-sm"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}


    </div>
  );
}