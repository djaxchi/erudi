import React, { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import ChatCollapsibleSection from "../components/ChatCollapsibleSection";
import QuestionInput from "../components/QuestionInput";
import { ask } from "../services/conversationService";
import HeaderBar from "../components/HeaderBar";

export default function ConversationPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  const [messages, setMessages] = useState([]);
  const [conversations, setConversations] = useState([]);
  const scrollRef = useRef(null);

  const[showPromptModal, setShowPromptModal] = useState(false);
  const[customPrompt, setCustomPrompt] = useState("");
  const [initialHandled, setInitialHandled] = useState(false);

  const [settings, setSettings] = useState({
    temperature : 0.5,
    topP : 0.9,
    maxTokens : 3074
  })

  const fetchMessagesAndConversations = useCallback(async () => {
    try {
      const [msgRes, convRes] = await Promise.all([
        fetch(`http://127.0.0.1:8000/conversations/${id}/messages`),
        fetch("http://127.0.0.1:8000/conversations"),
      ]);
      const msgs = await msgRes.json();
      const convs = await convRes.json();
      convs.sort(
        (a, b) =>
          new Date(b.last_message_time) - new Date(a.last_message_time)
      );
      setMessages(msgs);
      setConversations(convs);
    } catch (err) {
      console.error("Fetch error:", err);
    }
  }, [id]);

  const handleAsk = useCallback(
    async (question) => {
      const userMessage = {
        id: Date.now(),
        sender: "user",
        content: question,
      };

      const assistantMessage = {
        id: Date.now() + 1,
        sender: "llm",
        content: "",
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);

      try {
        await ask({
          question,
          conversationId: Number(id),
        temperature : settings.temperature,
        topP : settings.topP,
        maxTokens : settings.maxTokens,
          customPrompt,
        onStreamChunk: (chunk) => {
            assistantMessage.content += chunk;
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMessage.id
                  ? { ...msg, content: assistantMessage.content }
                  : msg
              )
            );
          },
        });
      } catch (err) {
        console.error("Failed to send message:", err);
      }

      await fetch(`http://127.0.0.1:8000/conversations/${id}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          conversation_id: Number(id),
          sender: "llm",
          content: assistantMessage.content,
        }),
      });

      await fetchMessagesAndConversations();
    },
    [id, settings, customPrompt, fetchMessagesAndConversations]
  );

  useEffect(() => {
  const run = async () => {
    if (location.state && location.state.initialQuestion && !initialHandled) {
      setInitialHandled(true);

      await handleAsk(location.state.initialQuestion);

      navigate(location.pathname, { replace: true, state: {} });
    } else if (!location.state || !location.state.initialQuestion) {
      try {
        const [msgRes, convRes] = await Promise.all([
          fetch(`http://127.0.0.1:8000/conversations/${id}/messages`),
          fetch(`http://127.0.0.1:8000/conversations`),
        ]);
        const msgs = await msgRes.json();
        const convs = await convRes.json();
        convs.sort(
          (a, b) =>
            new Date(b.last_message_time) - new Date(a.last_message_time)
        );
        setMessages(msgs);
        setConversations(convs);
      } catch (err) {
        console.error("Fetch error:", err);
      }
    }
  };

  run();
}, [id, location.state, handleAsk, navigate, location.pathname, initialHandled]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages]);

  const handleConversationClick = (newId) =>
    navigate(`/main_window/conversations/${newId}`);

  const handleRename = (cid, newName) =>
    setConversations((prev) =>
      prev.map((c) => (c.id === cid ? { ...c, name: newName } : c))
    );

  const handleDelete = (cid) => {
    setConversations((prev) => prev.filter((conv) => conv.id !== cid));
    if (cid === Number(id)) {
      navigate("/main_window/chat");
    }
  };

  return (
    <div className="flex h-screen">
      <Sidebar />

      <aside className="w-80 bg-[#272727] text-white flex flex-col p-6 space-y-6">
        <h1 className="text-3xl font-bold">History</h1>
        <ChatCollapsibleSection title="Hot Chats" />
        <ChatCollapsibleSection
          title="Previous Chats"
          items={conversations}
          selectedId={Number(id)}
          onSelect={handleConversationClick}
          onRename={handleRename}
          onDelete={handleDelete}
        />
      </aside>

      {/* ---------- Chat column ---------- */}
      
      <main className="flex-1 flex flex-col bg-gradient-to-br from-[#041915] to-[#0f2d27] overflow-hidden">
        
        <div className="relative flex justify-center w-full">
          <HeaderBar
        initialTemperature={settings.temperature}
        initialTopP={settings.topP}
        initialMaxTokens={settings.maxTokens}
        onApply={(newSettings) => setSettings(newSettings)}
        onCustomizePrompt={() => setShowPromptModal(true)}
        />
        </div>
        




        {showPromptModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg shadow-lg w-11/12 max-w-md p-6">
              <h2 className="text-xl font-semibold mb-4">Personnaliser le prompt</h2>
              <textarea
                className="w-full h-40 border rounded p-2 mb-4"
                value={customPrompt}
                onChange={(e) => setCustomPrompt(e.target.value)}
              />
              <div className="flex justify-end space-x-2">
                <button
                  onClick={() => setShowPromptModal(false)}
                  className="px-4 py-2 bg-gray-300 rounded hover:bg-gray-400"
                >
                  Annuler
                </button>
                <button
                  onClick={() => {
                    setShowPromptModal(false);
                    // customPrompt contient maintenant la saisie utilisateur
                  }}
                  className="px-4 py-2 bg-emerald-600 text-white rounded hover:bg-emerald-700"
                >
                  Enregistrer
                </button>
              </div>
            </div>
          </div>
        )}




        {/* message list */}
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto px-10 pt-10 pb-4"
          style={{
            scrollbarWidth: "none",
            msOverflowStyle: "none",
          }}
        >
          <style>{`::-webkit-scrollbar { display: none; }`}</style>

          <div className="flex flex-col gap-6">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`break-words w-fit max-w-[75%] p-4 rounded-2xl text-white whitespace-pre-wrap overflow-wrap break-word ${
                  msg.sender === "user"
                    ? "bg-[#191919] ml-auto rounded-tr-none"
                    : "mr-auto rounded-tl-none"
                }`}
              >
                {msg.content}
              </div>
            ))}
          </div>
        </div>

        






        {/* sticky question bar */}
        <div className="sticky bottom-0 left-0 right-0 px-10 py-10 backdrop-blur-md flex justify-center w-full">
          <div className="w-full max-w-lg">
            <QuestionInput
              onSend={handleAsk}
              backgroundClass="bg-emerald-900"
            />
          </div>
        </div>
      </main>
    </div>
  );
}
