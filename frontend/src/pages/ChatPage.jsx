import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import ChatCollapsibleSection from "../components/ChatCollapsibleSection";
import GradientBox from "../components/GradientBox";
import QuestionInput from "../components/QuestionInput";
import { ask } from "../services/conversationService";

export default function ChatPage() {
  const navigate = useNavigate();

  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [conversations, setConversations] = useState([]);
  const [errorMessage, setErrorMessage] = useState("");
  const [showErrorPopup, setShowErrorPopup] = useState(false);
  
  // Welcome popup state
  const [showWelcome, setShowWelcome] = useState(() => {
    // Check if user has seen the welcome popup before
    const hasSeenWelcome = localStorage.getItem('erudi_welcome_seen');
    // For testing: always show the popup (comment out the next line to disable testing mode)
    return true; // Always show for testing
    // return !hasSeenWelcome; // Uncomment this line and comment the one above for production
  });
  const [hardwareInfo, setHardwareInfo] = useState(null);
  const [hardwareLoading, setHardwareLoading] = useState(true);

  useEffect(() => {
    // Fetch models
    fetch("http://127.0.0.1:8000/main_window/llms/local")
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setModels(data);
          setSelectedModel(data[0].name);
        }
      })
      .catch((err) => {
        console.error("Erreur lors du fetch des modèles:", err);
        setErrorMessage(`Failed to load models: ${err.message || 'Network error'}`);
        setShowErrorPopup(true);
      });

    // Fetch hardware evaluation for welcome popup
    const fetchHardwareEvaluation = async () => {
      try {
        const response = await fetch("http://127.0.0.1:8000/hardware/app_startup");
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
        setHardwareLoading(false);
      }
    };

    // Only fetch hardware info if showing welcome popup
    if (showWelcome) {
      fetchHardwareEvaluation();
    }
  }, [showWelcome]);

  useEffect(() => {
    const fetchConversations = async () => {
      try {
        const res = await fetch("http://127.0.0.1:8000/conversations");
        const data = await res.json();
        const sorted = data.sort(
          (a, b) => new Date(b.last_message_time) - new Date(a.last_message_time)
        );
        setConversations(sorted);
      } catch (err) {
        console.error("Failed to fetch conversations:", err);
        setErrorMessage(`Failed to load conversations: ${err.message || 'Network error'}`);
        setShowErrorPopup(true);
      }
    };

    fetchConversations();
  }, []);

  const handleConversationClick = (id) => {
    navigate(`/main_window/conversation/${id}`);
  };

  const handleAsk = useCallback(
    async (question) => {
      const llm = models.find((m) => m.name === selectedModel);
      if (!llm) {
        console.error("Selected model not found");
        return;
      }
      try {
        // 1. Create a new conversation
        const res = await fetch("http://127.0.0.1:8000/conversations", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ llm_id: llm.id }),
        });
        if (!res.ok) throw new Error("Failed to create conversation");
        const conversation = await res.json();
        // 2. Redirect to ConversationPage and pass the question
        navigate(`/main_window/conversations/${conversation.id}`, { state: { initialQuestion: question } });
      } catch (err) {
        console.error("Failed to start conversation:", err);
        setErrorMessage(`Failed to start conversation: ${err.message || 'Network error'}`);
        setShowErrorPopup(true);
      }
    },
    [models, selectedModel, navigate]
  );

  const closeWelcome = () => {
    // Mark that user has seen the welcome popup
    localStorage.setItem('erudi_welcome_seen', 'true');
    setShowWelcome(false);
  };

  const handleRename = (id, newName) => {
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, name: newName } : c))
    );
  };

  const handleDelete = (id) => {
    setConversations((prev) => prev.filter((conv) => conv.id !== id));
  };

  const handleRefreshConversations = async () => {
    try {
      const res = await fetch("http://127.0.0.1:8000/conversations");
      const data = await res.json();
      const sorted = data.sort(
        (a, b) => new Date(b.last_message_time) - new Date(a.last_message_time)
      );
      setConversations(sorted);
    } catch (err) {
      console.error("Failed to refresh conversations:", err);
      setErrorMessage(`Failed to refresh conversations: ${err.message || 'Network error'}`);
      setShowErrorPopup(true);
    }
  };

  return (
    <div className="flex h-screen">
      <Sidebar />

      {/* barre latérale */}
      <aside className="w-[30%] sm:w-[35%] xl:w-[25%] bg-[#272727] text-white flex flex-col p-6 space-y-6">
        <h1 className="text-3xl font-bold">History</h1>

        {/*<ChatCollapsibleSection title="Hot Chats"
          disabled={loading}
        />} coming in next version*/}
        <ChatCollapsibleSection
          title="Previous Chats"
          items={conversations}
          onItemClick={handleConversationClick}
          onRename={handleRename}
          onDelete={handleDelete}
          onRefresh={handleRefreshConversations}
        />
      </aside>

      {/* zone centrale */}
      <main className="flex-1 bg-[#071b18] flex items-center justify-center relative overflow-auto">
        {/* Si aucun modèle local */}
        {models.length === 0 ? (
          <GradientBox className="w-[700px] max-w-full">
            <div className="text-white text-center py-10">
              Aucun modèle local disponible. Veuillez en ajouter un.
            </div>
          </GradientBox>
        ) : (
          /* Interface de création de chat */
          <GradientBox className="w-[700px] mx-[60px] max-w-full">
            <div className="space-y-6 ">
              {/* header row */}
              <div className="flex items-center mx-[10px] gap-2 flex-wrap">
                <h2 className="text-white text-3xl font-bold whitespace-nowrap">
                  Chat with
                </h2>
                <div className="relative">
                  <select
                    className="appearance-none pr-8 pl-4 py-1 rounded-full border border-emerald-400 bg-transparent text-white focus:outline-none text-sm"
                    onChange={(e) => setSelectedModel(e.target.value)}
                    value={selectedModel}
                  >
                    {models.map((model) => (
                      <option
                        key={model.id}
                        value={model.name}
                        className="text-black"
                      >
                        {model.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* question input */}
              <QuestionInput onSend={handleAsk} />
            </div>
          </GradientBox>
        )}
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
                      
                      {hardwareLoading ? (
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

      {/* Error Popup */}
      {showErrorPopup && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md mx-4 shadow-xl">
            <div className="flex items-center mb-4">
              <div className="bg-red-100 rounded-full p-2 mr-3">
                <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-gray-900">Error</h3>
            </div>
            <p className="text-gray-700 mb-4">{errorMessage}</p>
            <div className="flex justify-end">
              <button
                onClick={() => setShowErrorPopup(false)}
                className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}