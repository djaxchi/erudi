import React, { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import ChatCollapsibleSection from "../components/ChatCollapsibleSection";
import QuestionInput from "../components/QuestionInput";
import { ask } from "../services/conversationService";
import HeaderBar from "../components/HeaderBar";
import { Copy, Check, Star } from "lucide-react";
import { API_BASE_URL } from "../config/api";

export default function ConversationPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  const [messages, setMessages] = useState([]);
  const [copiedMessageId, setCopiedMessageId] = useState(null);
  const [starredIds, setStarredIds] = useState({});
  const [conversations, setConversations] = useState([]);
  const scrollRef = useRef(null);
  const [currentTitle, setCurrentTitle] = useState("");

  const [showPromptModal, setShowPromptModal] = useState(false);
  const [customPrompt, setCustomPrompt] = useState("");
  const [initialHandled, setInitialHandled] = useState(false);
  const [loading, setLoading] = useState(false);
  const [models, setModels] = useState([]);
  const [currentModel, setCurrentModel] = useState("");
  const [settings, setSettings] = useState({
    temperature: 0.9,
    topP: 0.9,
    maxTokens: 200
  })

  // Utility function to clean error messages for display
  const getDisplayContent = (content) => {
    if (content.includes("[ERROR_MESSAGE_SYSTEM]")) {
      return content.replace("[ERROR_MESSAGE_SYSTEM] ", "❌ ");
    }
    return content;
  };

  useEffect(() => {
    fetch(`${API_BASE_URL}/main_window/llms/local`)
      .then(res => res.json())
      .then(data => {
        setModels(data);
        if (conversations.length > 0) {
          const conv = conversations.find(c => c.id === Number(id));
          if (conv) {
            const model = data.find(m => m.id === conv.llm_id);
            if (model) setCurrentModel(model.name);
          }
        }
      });
  }, [id, conversations]);

  const handleModelChange = async (modelName) => {
    setCurrentModel(modelName);
    const model = models.find(m => m.name === modelName);
    if (!model) return;
    // Call API to update conversation's llm_id
    await fetch(`${API_BASE_URL}/conversations/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ llm_id: model.id }),
    });
    // // Optionally, refresh conversations state here
    // fetchMessagesAndConversations();
  };

  const fetchMessagesAndConversations = useCallback(async () => {
    try {
      const [msgRes, convRes] = await Promise.all([
        fetch(`${API_BASE_URL}/conversations/${id}/fetch_messages`),
        fetch(`${API_BASE_URL}/conversations`),
      ]);
      const msgs = await msgRes.json();
      // initialize starred state from backend
      const starredMap = {};
      msgs.forEach(m => { if (m.starred) starredMap[m.id] = true; });
      setStarredIds(starredMap);
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
      setLoading(true);
      
      const isFirstMessage = messages.length === 0;
      
      if (isFirstMessage) {
        setCurrentTitle("");
      }

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
        if (isFirstMessage) {
          try {
            const titleRes = await fetch(`${API_BASE_URL}/conversations/${id}/generate_title`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ question }),
            });
            
            if (titleRes.ok) {
              const reader = titleRes.body.getReader();
              const decoder = new TextDecoder("utf-8");
              let fullTitle = "";

              while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                fullTitle += chunk;
                
                setCurrentTitle(prev => {
                  const newTitle = prev + chunk;
                  setConversations(prevConvs => 
                    prevConvs.map(conv => 
                      conv.id === Number(id) 
                        ? { ...conv, name: newTitle.trim() || "New Conversation" }
                        : conv
                    )
                  );
                  return newTitle;
                });
              }
            }
          } catch (err) {
            console.error("Title generation failed:", err);
          }
        }

        const responseRes = await fetch(`${API_BASE_URL}/conversations/${id}/query`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            question,
            temperature: settings.temperature,
            top_p: settings.topP,
            max_new_tokens: settings.maxTokens,
            custom_prompt: customPrompt,
          }),
        });
        
        if (responseRes.ok) {
          const reader = responseRes.body.getReader();
          const decoder = new TextDecoder("utf-8");

          try {
            while (true) {
              const { done, value } = await reader.read();
              if (done) break;

              const chunk = decoder.decode(value, { stream: true });
              assistantMessage.content += chunk;
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessage.id
                    ? { ...msg, content: assistantMessage.content }
                    : msg
                )
              );
            }          } catch (streamError) {
            console.error("Streaming error:", streamError);
            
            // If streaming failed mid-way, append an error note with robust header
            assistantMessage.content += "\n\n[ERROR_MESSAGE_SYSTEM] Connection interrupted while generating response.";
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMessage.id
                  ? { ...msg, content: assistantMessage.content }
                  : msg
              )
            );
            
            try {
              await fetch(`${API_BASE_URL}/conversations/${id}/store_error_message`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
              });
            } catch (storeError) {
              console.error("Failed to store error message:", storeError);
            }
          }
        } else {
          console.error("Server error during response generation:", responseRes.status);
          
          try {
            await fetch(`${API_BASE_URL}/conversations/${id}/store_error_message`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
            });
            console.log("Error message stored in database");
          } catch (storeError) {
            console.error("Failed to store error message:", storeError);
          }
            // Update the assistant message with error content using robust header
          assistantMessage.content = "[ERROR_MESSAGE_SYSTEM] I apologize, but I encountered an error while generating a response. Please try asking your question again.";
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessage.id
                ? { ...msg, content: assistantMessage.content }
                : msg
            )
          );
        }

      } catch (err) {
        console.error("Failed to send message:", err);
      }

      await fetchMessagesAndConversations();
      
      if (isFirstMessage) {
        setTimeout(() => setCurrentTitle(""), 3000);
      }
      
      setLoading(false);
    },
    [id, settings, customPrompt, fetchMessagesAndConversations, messages.length]
  );

  useEffect(() => {
    const run = async () => {
      try {
        const convRes = await fetch(`${API_BASE_URL}/conversations`);
        const convs = await convRes.json();
        convs.sort(
          (a, b) => new Date(b.last_message_time) - new Date(a.last_message_time)
        );
        setConversations(convs);
      } catch (err) {
        console.error("Fetch error (conversations):", err);
      }

      if (location.state && location.state.initialQuestion && !initialHandled) {
        setInitialHandled(true);
        await handleAsk(location.state.initialQuestion);
        navigate(location.pathname, { replace: true, state: {} });
      } else if (!location.state || !location.state.initialQuestion) {
        try {
          const msgRes = await fetch(`${API_BASE_URL}/conversations/${id}/fetch_messages`);
          const msgs = await msgRes.json();
          // initialize starred state on initial load
          const starredMap = {};
          msgs.forEach(m => { if (m.starred) starredMap[m.id] = true; });
          setStarredIds(starredMap);
          setMessages(msgs);
        } catch (err) {
          console.error("Fetch error (messages):", err);
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

  const handleDelete = async (cid) => {
    setConversations((prev) => prev.filter((conv) => conv.id !== cid));
    await fetch(`${API_BASE_URL}/conversations/${cid}`, { method: "DELETE" });
    await fetchMessagesAndConversations();
    if (cid === Number(id)) {
      navigate("/main_window/chat");
    }
  };

  // Toggle star state and send appropriate POST
  const toggleStar = async (msgId, content) => {
    const isStarred = starredIds[msgId];
    const url = `${API_BASE_URL}/conversations/${isStarred ? 'unstar_message' : 'star_message'}`;
    try {
      await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message : content }),
      });
      setStarredIds(prev => ({ ...prev, [msgId]: !isStarred }));
    } catch (err) {
      console.error('Star toggle failed:', err);
    }
  };

  return (
    <div className="flex h-screen">
      <Sidebar disabled = {loading} />

      <aside className="w-80 bg-[#272727] text-white flex flex-col p-6 space-y-6">
        <h1 className="text-3xl font-bold">History</h1>
        {/*<ChatCollapsibleSection title="Hot Chats"
          disabled={loading}
        />} coming in next version*/}
        <ChatCollapsibleSection
          title="Previous Chats"
          items={conversations}
          selectedId={Number(id)}
          onSelect={handleConversationClick}
          onRename={handleRename}
          onDelete={handleDelete}
          disabled={loading}
        />
      </aside>
      <main className="flex-1 flex flex-col bg-gradient-to-br from-[#041915] to-[#0f2d27] overflow-hidden">        <div className="relative flex justify-center w-full">
          <HeaderBar
            initialTemperature={settings.temperature}
            initialTopP={settings.topP}
            initialMaxTokens={settings.maxTokens}
            onApply={(newSettings) => setSettings(newSettings)}
            onCustomizePrompt={() => setShowPromptModal(true)}
            disabled={loading}
            models={models}
            currentModel={currentModel}
            onModelChange={handleModelChange}
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
                  }}
                  className="px-4 py-2 bg-emerald-600 text-white rounded hover:bg-emerald-700"
                >
                  Enregistrer
                </button>
              </div>
            </div>
          </div>
        )}
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto px-10 pt-10 pb-4"
          style={{
            scrollbarWidth: "none",
            msOverflowStyle: "none",
          }}
        >
          <style>{`::-webkit-scrollbar { display: none; }`}</style>          <div className="flex flex-col gap-6">
            {messages.map((msg) => {
              const isUser = msg.sender === 'user';
              const alignmentClass = isUser ? 'items-end' : 'items-start';
              const bubbleClass = isUser
                ? 'bg-[#191919] ml-auto rounded-tr-none text-white'
                : msg.content.includes('[ERROR_MESSAGE_SYSTEM]')
                ? 'text-red-400 mr-auto rounded-tl-none'
                : ' text-white mr-auto rounded-tl-none';
              return (
                <div key={msg.id} className={`group flex flex-col mb-2 ${alignmentClass}`}>  
                  <div
                    className={`break-words w-fit max-w-[75%] p-4 rounded-2xl whitespace-pre-wrap overflow-wrap break-word ${bubbleClass}`}
                  >
                    {getDisplayContent(msg.content)}
                  </div>
                  <div className="flex mt-1 space-x-2 opacity-0 group-hover:opacity-100">
                    {/* Copy button */}
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(msg.content).then(() => {
                          setCopiedMessageId(msg.id);
                          setTimeout(() => setCopiedMessageId(null), 1000);
                        });
                      }}
                      className="text-gray-400 hover:text-white transition-colors"
                      title="Copy message"
                    >
                      {copiedMessageId === msg.id ? (
                        <Check size={16} className="text-green-400" />
                      ) : (
                        <Copy size={16} />
                      )}
                    </button>
                    {/* Star button */}
                    <button
                      onClick={() => toggleStar(msg.id, msg.content)}
                      className="text-gray-400 hover:text-white transition-colors"
                      title="Star message"
                    >
                      <Star
                        size={16}
                        className={starredIds[msg.id] ? 'text-yellow-400' : ''}
                        fill={starredIds[msg.id] ? 'currentColor' : 'none'}
                      />
                    </button>
                  </div>
                 </div>
               );
             })}
          </div>
        </div>
        <div className="sticky bottom-0 left-0 right-0 px-10 py-10 backdrop-blur-md flex justify-center w-full">
          <div className="w-full max-w-lg">
            <QuestionInput
              onSend={handleAsk}
              backgroundClass="bg-emerald-900"
              disabled={loading}
            />
          </div>
        </div>
      </main>
    </div>
  );
}
