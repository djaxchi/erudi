import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import CollapsibleSection from "../components/CollapsibleSection";
import NewChatCard from "../components/NewChatCard";

export default function ChatPage() {
  const [conversations, setConversations] = useState([]);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchConversations = async () => {
      try {
        const response = await fetch("http://127.0.0.1:8000/conversations");
        const data = await response.json();
        const sorted = data.sort(
          (a, b) => new Date(b.last_message_time) - new Date(a.last_message_time)
        );
        setConversations(sorted);
      } catch (error) {
        console.error("Failed to fetch conversations:", error);
      }
    };

    fetchConversations();
  }, []);

  const handleConversationClick = (id) => {
    navigate(`/main_window/conversation/${id}`);
  };

  return (
    <div className="flex h-screen">
      <Sidebar />

      <aside className="w-80 bg-[#272727] text-white flex flex-col p-6 space-y-6">
        <h1 className="text-3xl font-bold">History</h1>
        <CollapsibleSection title="Hot Chats" />
        <CollapsibleSection
          title="Previous Chats"
          items={conversations}
          onItemClick={handleConversationClick}
        />
      </aside>

      <main className="flex-1 bg-[#071b18] flex items-center justify-center relative overflow-auto">
        <NewChatCard />
      </main>
    </div>
  );
}
