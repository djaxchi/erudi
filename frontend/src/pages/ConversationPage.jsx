import React, { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import ChatCollapsibleSection from "../components/ChatCollapsibleSection";
import QuestionInput from "../components/QuestionInput";
import { ask } from "../services/conversationService";


export default function ConversationPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [messages, setMessages] = useState([]);
  const [conversations, setConversations] = useState([]);

  useEffect(() => {
    (async () => {
      try {
        const [msgRes, convRes] = await Promise.all([
          fetch(`http://127.0.0.1:8000/conversations/${id}/messages`),
          fetch("http://127.0.0.1:8000/conversations"),
        ]);
        const msgs = await msgRes.json();
        const convs = await convRes.json();
        convs.sort(
          (a, b) => new Date(b.last_message_time) - new Date(a.last_message_time)
        );
        setMessages(msgs);
        setConversations(convs);
      } catch (err) {
        console.error("Fetch error:", err);
      }
    })();
  }, [id]);

  const handleConversationClick = (newId) => navigate(`/main_window/conversations/${newId}`);

  const handleAsk = useCallback(async (question) => {
    const userMessage = {
      id: Date.now(),
      sender: "user",
      content: question,
    };
  
    const assistantMessage = {
      id: Date.now() + 1, // unique id
      sender: "llm",
      content: "",
    };
  
    setMessages((prev) => [...prev, userMessage, assistantMessage]);
  
    try {
      await ask({
        question,
        conversationId: Number(id),
        onStreamChunk: (chunk) => {
          assistantMessage.content += chunk;
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessage.id ? { ...msg, content: assistantMessage.content } : msg
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
  }, [id]);

  const handleRename = (cid, newName) =>
    setConversations((prev) => prev.map((c) => (c.id === cid ? { ...c, name: newName } : c)));

  const handleDelete = (id) => {
    setConversations((prev) => prev.filter((conv) => conv.id !== id));

    if (id === Number(id)) {
      navigate("/main_window/chat");
    }
  };


  return (
    <div className="flex h-screen">
      <Sidebar />

      {/* ---------- History sidebar ---------- */}
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
      <main className="flex-1 flex flex-col bg-gradient-to-br from-[#041915] to-[#0f2d27] overflow-hidden "
      style={{ scrollbarWidth: "none", msOverflowStyle: "none"}}>
        {/* message list */}
        <div
          className="flex-1 overflow-y-auto space-y-12 px-10 pt-10"
          style={{ maxHeight: "calc(100vh - 10px)",  scrollbarWidth: "none", msOverflowStyle: "none" }}
        >
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`max-w-full p-4 rounded-2xl text-white whitespace-pre-wrap ${msg.sender === "user" ? "bg-[#191919] ml-auto rounded-tr-none max-w-xl" : " mr-auto rounded-tl-none"}`
            }
            >
              {msg.content}
            </div>
          ))}
        </div>

        {/* sticky question bar */}
        <div className="sticky bottom-0 left-0 right-0 px-10 py-10 backdrop-blur-md flex justify-center">
          <QuestionInput onSend={handleAsk} backgroundClass="bg-emerald-900" />
        </div>
      </main>
    </div>
  );
}
