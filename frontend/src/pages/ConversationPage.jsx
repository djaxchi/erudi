import React, { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import CollapsibleSection from "../components/CollapsibleSection";
import QuestionInput from "../components/QuestionInput";
import { ask } from "../services/conversationService";

/**
 * Affiche une conversation existante et permet d'ajouter de nouveaux messages.
 */
export default function ConversationPage() {
  const { id } = useParams(); // id de la conversation courante
  const navigate = useNavigate();

  const [messages, setMessages] = useState([]);
  const [conversations, setConversations] = useState([]);

  /* ------------------------------------------------------------------ */
  /* CHARGEMENT INITIAL                                                 */
  /* ------------------------------------------------------------------ */
  useEffect(() => {
    const fetchMessages = async () => {
      try {
        const res = await fetch(`http://127.0.0.1:8000/conversations/${id}/messages`);
        const data = await res.json();
        setMessages(data);
      } catch (err) {
        console.error("Failed to fetch messages:", err);
      }
    };

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

    fetchMessages();
    fetchConversations();
  }, [id]);

  /* ------------------------------------------------------------------ */
  /* NAVIGATION ENTRE CONVERSATIONS                                     */
  /* ------------------------------------------------------------------ */
  const handleConversationClick = (newId) => {
    navigate(`/main_window/conversations/${newId}`);
  };

  /* ------------------------------------------------------------------ */
  /* ENVOI D'UN NOUVEAU MESSAGE                                         */
  /* ------------------------------------------------------------------ */
  const handleAsk = useCallback(
    async (question) => {
      try {
        const { message } = await ask({ question, conversationId: parseInt(id) });

        // 1️⃣ Met à jour l'affichage immédiatement
        setMessages((prev) => [...prev, message]);

        // 2️⃣ Actions supplémentaires (décommenter / remplacer)
        // await callLLM(message);   // 🔮 obtenir la réponse du modèle & l'ajouter
        // playSendSound();          // 🔊 feedback audio
        // scrollToBottom();         // 📜 défilement automatique
        // refreshConversations();   // 🔄 remettre à jour la sidebar
      } catch (err) {
        console.error("Failed to send message:", err);
      }
    },
    [id]
  );

  /* ------------------------------------------------------------------ */
  /* RENDER                                                             */
  /* ------------------------------------------------------------------ */
  return (
    <div className="flex h-screen">
      <Sidebar />

      <aside className="w-80 bg-[#272727] text-white flex flex-col p-6 space-y-6">
        <h1 className="text-3xl font-bold">History</h1>
        <CollapsibleSection title="Hot Chats" />
        <CollapsibleSection
          title="Previous Chats"
          items={conversations}
          selectedId={parseInt(id)}
          onItemClick={handleConversationClick}
        />
      </aside>

      <main className="flex-1 bg-gradient-to-br from-[#041915] to-[#0f2d27] p-10 overflow-auto">
        <div className="space-y-6">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`max-w-3xl p-6 rounded-2xl text-white whitespace-pre-wrap ${
                msg.sender === "user" ? "bg-[#191919] ml-auto" : "bg-[#272727] mr-auto"
              }`}
            >
              {msg.content}
            </div>
          ))}
        </div>

        <div className="mt-10 flex justify-center">
          <QuestionInput onSend={handleAsk} backgroundClass="bg-emerald-900" />
        </div>
      </main>
    </div>
  );
}
