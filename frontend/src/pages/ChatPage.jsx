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

  useEffect(() => {
    fetch("http://127.0.0.1:8000/main_window/llms/local")
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setModels(data);
          setSelectedModel(data[0].name);
        }
      })
      .catch((err) => console.error("Erreur lors du fetch des modèles:", err));
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
      }
    },
    [models, selectedModel, navigate]
  );

  const handleRename = (id, newName) => {
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, name: newName } : c))
    );
  };

  return (
    <div className="flex h-screen">
      <Sidebar />

      {/* barre latérale */}
      <aside className="w-80 bg-[#272727] text-white flex flex-col p-6 space-y-6">
        <h1 className="text-3xl font-bold">History</h1>

        <ChatCollapsibleSection title="Hot Chats" />
        <ChatCollapsibleSection
          title="Previous Chats"
          items={conversations}
          onItemClick={handleConversationClick}
          onRename={handleRename}
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
    </div>
  );
}