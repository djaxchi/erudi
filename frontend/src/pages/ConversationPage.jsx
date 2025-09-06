import React, { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import ChatCollapsibleSection from "../components/ChatCollapsibleSection";
import QuestionInput from "../components/QuestionInput";
import { ask } from "../services/conversationService";
import HeaderBar from "../components/HeaderBar";
import CustomizePromptModal from "../components/modals/CustomizePromptModal";
import { Copy, Check, Star } from "lucide-react";

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
    temperature: 0.2,
    topP: 0.5,
    maxTokens: 3074,
    quantize: false,
  });
  const [collapsed, setCollapsed] = useState(false);

  const toggleSidebar = () => {
    setCollapsed((prev) => !prev);
  };

  // Utility function to clean error messages for display
  const getDisplayContent = (content) => {
    if (content.includes("[ERROR_MESSAGE_SYSTEM]")) {
      return content.replace("[ERROR_MESSAGE_SYSTEM] ", "❌ ");
    }
    return content;
  };

  useEffect(() => {
    fetch("http://127.0.0.1:8000/main_window/llms/local")
      .then((res) => res.json())
      .then((data) => {
        setModels(data);
      });
  }, []);

  const handleModelChange = async (modelName) => {
    setCurrentModel(modelName);
    const model = models.find((m) => m.name === modelName);
    if (!model) return;
    // Call API to update conversation's llm_id
    await fetch(`http://127.0.0.1:8000/conversations/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ llm_id: model.id }),
    });
    // // Optionally, refresh conversations state here
    // fetchMessagesAndConversations();
  };

  // Function to save conversation parameters
  const saveConversationParameters = async (newSettings, newCustomPrompt) => {
    try {
      await fetch(`http://127.0.0.1:8000/conversations/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          temperature: newSettings.temperature,
          top_p: newSettings.topP,
          max_tokens: newSettings.maxTokens,
          quantize: newSettings.quantize,
          custom_prompt: newCustomPrompt || customPrompt,
        }),
      });
    } catch (error) {
      console.error("Failed to save conversation parameters:", error);
    }
  };

  const fetchMessagesAndConversations = useCallback(async () => {
    try {
      const [msgRes, convRes] = await Promise.all([
        fetch(`http://127.0.0.1:8000/conversations/${id}/fetch_messages`),
        fetch("http://127.0.0.1:8000/conversations"),
      ]);
      const msgs = await msgRes.json();
      // initialize starred state from backend
      const starredMap = {};
      msgs.forEach((m) => {
        if (m.starred) starredMap[m.id] = true;
      });
      setStarredIds(starredMap);
      const convs = await convRes.json();
      convs.sort(
        (a, b) => new Date(b.last_message_time) - new Date(a.last_message_time)
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
            const titleRes = await fetch(
              `http://127.0.0.1:8000/conversations/${id}/generate_title`,
              {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ question }),
              }
            );

            if (titleRes.ok) {
              const reader = titleRes.body.getReader();
              const decoder = new TextDecoder("utf-8");
              let fullTitle = "";

              while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                fullTitle += chunk;

                setCurrentTitle((prev) => {
                  const newTitle = prev + chunk;
                  setConversations((prevConvs) =>
                    prevConvs.map((conv) =>
                      conv.id === Number(id)
                        ? {
                            ...conv,
                            name: newTitle.trim() || "New Conversation",
                          }
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

        const responseRes = await fetch(
          `http://127.0.0.1:8000/conversations/${id}/query`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              question,
              temperature: settings.temperature,
              top_p: settings.topP,
              max_new_tokens: settings.maxTokens,
              quantize: settings.quantize,
              custom_prompt: customPrompt,
            }),
          }
        );

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
            }
          } catch (streamError) {
            console.error("Streaming error:", streamError);

            // If streaming failed mid-way, append an error note with robust header
            assistantMessage.content +=
              "\n\n[ERROR_MESSAGE_SYSTEM] Connection interrupted while generating response.";
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMessage.id
                  ? { ...msg, content: assistantMessage.content }
                  : msg
              )
            );

            try {
              await fetch(
                `http://127.0.0.1:8000/conversations/${id}/store_error_message`,
                {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                }
              );
            } catch (storeError) {
              console.error("Failed to store error message:", storeError);
            }
          }
        } else {
          console.error(
            "Server error during response generation:",
            responseRes.status
          );

          try {
            await fetch(
              `http://127.0.0.1:8000/conversations/${id}/store_error_message`,
              {
                method: "POST",
                headers: { "Content-Type": "application/json" },
              }
            );
            console.log("Error message stored in database");
          } catch (storeError) {
            console.error("Failed to store error message:", storeError);
          }
          // Update the assistant message with error content using robust header
          assistantMessage.content =
            "[ERROR_MESSAGE_SYSTEM] I apologize, but I encountered an error while generating a response. Please try asking your question again.";
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

  // Load conversation data when ID changes
  useEffect(() => {
    if (!id) return;

    const loadConversationData = async () => {
      try {
        const [convRes, msgRes, convDetailRes] = await Promise.all([
          fetch("http://127.0.0.1:8000/conversations"),
          fetch(`http://127.0.0.1:8000/conversations/${id}/fetch_messages`),
          fetch(`http://127.0.0.1:8000/conversations/${id}`),
        ]);

        // Load conversations
        const convs = await convRes.json();
        convs.sort(
          (a, b) =>
            new Date(b.last_message_time) - new Date(a.last_message_time)
        );
        setConversations(convs);

        // Load messages
        const msgs = await msgRes.json();
        const starredMap = {};
        msgs.forEach((m) => {
          if (m.starred) starredMap[m.id] = true;
        });
        setStarredIds(starredMap);
        setMessages(msgs);

        // Load conversation parameters
        if (convDetailRes.ok) {
          const conversation = await convDetailRes.json();
          setSettings({
            temperature: conversation.temperature,
            topP: conversation.top_p,
            maxTokens: conversation.max_tokens,
            quantize: conversation.quantize || false,
          });
          setCustomPrompt(conversation.custom_prompt || "");

          // Set current model
          if (models.length > 0) {
            const model = models.find((m) => m.id === conversation.llm_id);
            if (model) setCurrentModel(model.name);
          }
        }
      } catch (err) {
        console.error("Fetch error:", err);
      }
    };

    loadConversationData();
  }, [id, models]);

  // Handle initial question from ChatPage
  useEffect(() => {
    if (location.state?.initialQuestion && !initialHandled) {
      const handleInitialQuestion = async () => {
        setInitialHandled(true);

        if (location.state.initialSettings) {
          setSettings(location.state.initialSettings);
        }

        if (location.state.initialCustomPrompt) {
          setCustomPrompt(location.state.initialCustomPrompt);
        }

        await handleAsk(location.state.initialQuestion);
        navigate(location.pathname, { replace: true, state: {} });
      };

      handleInitialQuestion();
    }
  }, [location.state, initialHandled]);

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
    await fetch(`http://127.0.0.1:8000/conversations/${cid}`, {
      method: "DELETE",
    });
    await fetchMessagesAndConversations();
    if (cid === Number(id)) {
      navigate("/main_window/chat");
    }
  };

  // Toggle star state and send appropriate POST
  const toggleStar = async (msgId, content) => {
    const isStarred = starredIds[msgId];
    const url = `http://127.0.0.1:8000/conversations/${
      isStarred ? "unstar_message" : "star_message"
    }`;
    try {
      await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: content }),
      });
      setStarredIds((prev) => ({ ...prev, [msgId]: !isStarred }));
    } catch (err) {
      console.error("Star toggle failed:", err);
    }
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        disabled={loading}
        showCollapsible={true}
        onToggleSidebar={toggleSidebar}
        collapsed={collapsed}
      />

      <aside
        className={`relative bg-[#272727] text-white transition-all duration-300 ease-in-out ${
          collapsed ? "w-0 p-0" : "w-80 p-6 space-y-6"
        }`}
      >
        {!collapsed && (
          <>
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
          </>
        )}
      </aside>
      <main className="flex-1 flex flex-col bg-gradient-to-br from-[#041915] to-[#0f2d27] overflow-hidden">
        <div className="relative flex justify-center w-full px-8 pt-6">
          <HeaderBar
            initialTemperature={settings.temperature}
            initialTopP={settings.topP}
            initialMaxTokens={settings.maxTokens}
            initialQuantize={settings.quantize}
            onApply={(newSettings) => {
              setSettings(newSettings);
              saveConversationParameters(newSettings, customPrompt);
            }}
            onCustomizePrompt={() => setShowPromptModal(true)}
            disabled={loading}
            models={models}
            currentModel={currentModel}
            onModelChange={handleModelChange}
          />
        </div>

        <CustomizePromptModal
          isOpen={showPromptModal}
          onClose={() => setShowPromptModal(false)}
          customPrompt={customPrompt}
          onSave={(newPrompt) => {
            setCustomPrompt(newPrompt);
            saveConversationParameters(settings, newPrompt);
          }}
          title="Personnaliser le prompt"
        />
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto px-10 pt-10 pb-4"
          style={{
            scrollbarWidth: "none",
            msOverflowStyle: "none",
          }}
        >
          <style>{`::-webkit-scrollbar { display: none; }`}</style>{" "}
          <div className="flex flex-col gap-6">
            {messages.map((msg) => {
              const isUser = msg.sender === "user";
              const alignmentClass = isUser ? "items-end" : "items-start";
              const bubbleClass = isUser
                ? "bg-[#191919] ml-auto rounded-tr-none text-white"
                : msg.content.includes("[ERROR_MESSAGE_SYSTEM]")
                ? "text-red-400 mr-auto rounded-tl-none"
                : " text-white mr-auto rounded-tl-none";
              return (
                <div
                  key={msg.id}
                  className={`group flex flex-col mb-2 ${alignmentClass}`}
                >
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
                        className={starredIds[msg.id] ? "text-yellow-400" : ""}
                        fill={starredIds[msg.id] ? "currentColor" : "none"}
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
