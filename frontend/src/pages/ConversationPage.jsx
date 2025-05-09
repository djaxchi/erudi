import React, { useEffect, useState } from "react";
import Sidebar from "../components/Sidebar";
import CollapsibleSection from "../components/CollapsibleSection";
import { useParams, useNavigate } from "react-router-dom";
import QuestionInput from "../components/QuestionInput";

export default function ConversationPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [messages, setMessages] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [input, setInput] = useState("");

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

  const handleConversationClick = (newId) => {
    navigate(`/main_window/conversation/${newId}`);
  };

  return (
    <div className="flex h-screen">
      <Sidebar />

      {/* Sidebar section with collapsible conversation list */}
      <aside className="w-80 bg-[#272727] text-white flex flex-col p-6 space-y-6">
        <h1 className="text-3xl font-bold">History</h1>
        <CollapsibleSection
          title="Hot Chats"
        />
        <CollapsibleSection
          title="Previous Chats"
          items={conversations}
          selectedId={parseInt(id)}
          onItemClick={handleConversationClick}
        />
      </aside>

      <main className="flex-1 bg-gradient-to-br from-[#041915] to-[#0f2d27] p-10 overflow-auto">
        {/* <div className="flex items-center gap-4 mb-8">
          <h2 className="text-white text-3xl font-bold">Chat with</h2>
          <select className="px-4 py-1 rounded-full border border-emerald-400 bg-transparent text-white focus:outline-none text-sm">
            <option className="text-black">Mistral-7b-AO</option>
          </select>
        </div> */}

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
        <QuestionInput
          onSend={() => {}}
          backgroundClass="bg-emerald-900"
        />
        </div>
      </main>
    </div>
  );
}
