import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import ChatCollapsibleSection from "../components/ChatCollapsibleSection";
import GradientBox from "../components/GradientBox";
import QuestionInput from "../components/QuestionInput";
import { ask } from "../services/conversationService";
import ErrorModal from "../components/modals/ErrorModal";

export default function ChatPage() {
  const navigate = useNavigate();

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
      });
  }, []);

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
      const res = await fetch("http://127.0.0.1:8000/conversations");
      const data = await res.json();
      const sorted = data.sort(
        (a, b) => new Date(b.last_message_time) - new Date(a.last_message_time)
      );
      setConversations(sorted);
    } catch (err) {
      console.error("Failed to refresh conversations:", err);
      setErrorMessage(`Failed to refresh conversations: ${err.message || 'Network error'}`);
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
      <ErrorModal errorMessage={errorMessage} onClose={() => setErrorMessage("")} />
    </div>
  );
}