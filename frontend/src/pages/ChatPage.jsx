import React, { useEffect, useState, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import ChatCollapsibleSection from "../components/ChatCollapsibleSection";
import GradientBox from "../components/GradientBox";
import QuestionInput from "../components/QuestionInput";
import { ask } from "../services/conversationService";
import { API_BASE_URL } from "../config/api";

export default function ChatPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [conversations, setConversations] = useState([]);
  const [errorMessage, setErrorMessage] = useState("");
  const [showErrorPopup, setShowErrorPopup] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  const toggleSidebar = () => {
    setCollapsed((prev) => !prev);
  };

  useEffect(() => {
    fetch(`${API_BASE_URL}/main_window/llms/local`)
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
  }, []);

  useEffect(() => {
    const fetchConversations = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/conversations`);
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

  // Handle URL parameter for model selection
  useEffect(() => {
    const modelParam = searchParams.get('model');
    if (modelParam && models.length > 0) {
      // Find the model by name or id
      const foundModel = models.find(model => 
        model.name === modelParam || 
        model.id === modelParam ||
        model.name.toLowerCase() === modelParam.toLowerCase()
      );
      
      if (foundModel) {
        console.log('Setting model from URL parameter:', foundModel);
        setSelectedModel(foundModel.name);
      } else {
        console.warn('Model not found for parameter:', modelParam);
      }
    }
  }, [searchParams, models]); // Re-run when searchParams or models change

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
        const res = await fetch(`${API_BASE_URL}/conversations`, {
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
      const res = await fetch(`${API_BASE_URL}/conversations`);
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
    <div className="flex h-screen overflow-hidden">
      <Sidebar 
        showCollapsible={true}
        onToggleSidebar={toggleSidebar}
        collapsed={collapsed}
      />

      {/* barre latérale */}
      <aside className={`relative bg-[#272727] text-white transition-all duration-300 ease-in-out ${
        collapsed ? "w-0 p-0" : "w-80 p-6 space-y-6"
      }`}>
        {/* Content only when expanded */}
        {!collapsed && (
          <>
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
          </>
        )}
      </aside>

      {/* zone centrale */}
      <main className="flex-1 bg-[#071b18] flex items-center justify-center relative overflow-hidden py-12 px-8">
        {/* Si aucun modèle local */}
        {models.length === 0 ? (
          <GradientBox className="w-[700px] max-w-full">
            <div className="text-white text-center py-10">
              Aucun modèle local disponible. Veuillez en ajouter un.
            </div>
          </GradientBox>
        ) : (
          /* Interface de création de chat */
          <GradientBox className="w-[700px] max-w-full">
            <div className="space-y-6">
              {/* header row */}
              <div className="flex items-center gap-4 flex-wrap mt-2">
                <h2 className="text-white text-3xl font-bold whitespace-nowrap">
                  Chat with
                </h2>
                <div className="relative">
                  <select
                    className="appearance-none pr-8 pl-4 py-2 rounded-full border border-emerald-400 bg-transparent text-white focus:outline-none text-sm min-w-[200px]"
                    style={{
                      backgroundImage: 'none',
                      WebkitAppearance: 'none',
                      MozAppearance: 'none',
                      msAppearance: 'none'
                    }}
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
                  {/* Custom chevron */}
                  <div className="absolute right-3 top-1/2 transform -translate-y-1/2 pointer-events-none">
                    <svg 
                      className="w-4 h-4 text-emerald-400" 
                      fill="none" 
                      stroke="currentColor" 
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                </div>
              </div>

              {/* question input */}
              <QuestionInput onSend={handleAsk} />
            </div>
          </GradientBox>
        )}
      </main>

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