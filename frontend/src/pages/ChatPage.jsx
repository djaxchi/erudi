import React, { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import ChatCollapsibleSection from "../components/ChatCollapsibleSection";
import GradientBox from "../components/GradientBox";
import QuestionInput from "../components/QuestionInput";
import CustomizePromptModal from "../components/modals/CustomizePromptModal";
import Tooltip from "../components/Tooltip";
import ErrorModal from "../components/modals/ErrorModal";
import { motion, AnimatePresence } from "framer-motion";
import { SlidersHorizontal, ChevronDown, HelpCircle } from "lucide-react";
import logoErudi from "../img/logoerudifinal.png";

export default function ChatPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [conversations, setConversations] = useState([]);
  const [errorMessage, setErrorMessage] = useState("");
  const [showErrorPopup, setShowErrorPopup] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [isLanguageWarningExpanded, setIsLanguageWarningExpanded] = useState(false);

  // Parameters state
  const [settings, setSettings] = useState({
    temperature: 1.0,
    topP: 0.95,
    maxTokens: 1024,
    quantize: false,
  });
  const [customPrompt, setCustomPrompt] = useState("");
  const [showPromptModal, setShowPromptModal] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  // Refs for dropdown
  const dropdownRef = useRef(null);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  const toggleSidebar = () => {
    setCollapsed((prev) => !prev);
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsDropdownOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

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
        setErrorMessage(
          `Failed to load models: ${err.message || "Network error"}`
        );
      });
  }, []);

  useEffect(() => {
    const fetchConversations = async () => {
      try {
        const res = await fetch("http://127.0.0.1:8000/conversations");
        const data = await res.json();
        const sorted = data.sort(
          (a, b) =>
            new Date(b.last_message_time) - new Date(a.last_message_time)
        );
        setConversations(sorted);
      } catch (err) {
        console.error("Failed to fetch conversations:", err);
        setErrorMessage(
          `Failed to load conversations: ${err.message || "Network error"}`
        );
      }
    };

    fetchConversations();
  }, []);

  // Handle URL parameter for model selection
  useEffect(() => {
    const modelParam = searchParams.get("model");
    if (modelParam && models.length > 0) {
      // Find the model by name or id
      const foundModel = models.find(
        (model) =>
          model.name === modelParam ||
          model.id === modelParam ||
          model.name.toLowerCase() === modelParam.toLowerCase()
      );

      if (foundModel) {
        console.log("Setting model from URL parameter:", foundModel);
        setSelectedModel(foundModel.name);
      } else {
        console.warn("Model not found for parameter:", modelParam);
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
        // 1. Create a new conversation with the specified parameters
        const res = await fetch("http://127.0.0.1:8000/conversations", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            llm_id: llm.id,
            temperature: settings.temperature,
            top_p: settings.topP,
            max_tokens: settings.maxTokens,
            quantize: settings.quantize,
            custom_prompt: customPrompt,
          }),
        });
        if (!res.ok) throw new Error("Failed to create conversation");
        const conversation = await res.json();

        // 2. Redirect to ConversationPage and pass the question AND parameters
        navigate(`/main_window/conversations/${conversation.id}`, {
          state: {
            initialQuestion: question,
            initialSettings: settings,
            initialCustomPrompt: customPrompt,
          },
        });
      } catch (err) {
        console.error("Failed to start conversation:", err);
        setErrorMessage(
          `Failed to start conversation: ${err.message || "Network error"}`
        );
      }
    },
    [models, selectedModel, navigate, settings, customPrompt]
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
      setErrorMessage(
        `Failed to refresh conversations: ${err.message || "Network error"}`
      );
    }
  };

  // Utility functions for HeaderBar-like styling
  const TooltipIcon = ({ id, side = "right" }) => {
    const text =
      id === "temperature"
        ? "Controls creativity. Lower = focused, higher = creative."
        : id === "top-p"
        ? "Controls word variety. Lower = predictable, higher = diverse."
        : id === "prompt"
        ? "Customize system instructions that guide AI behavior."
        : id === "quantize"
        ? "Lower memory usage: faster inference but may reduce response quality."
        : "";
    return (
      <Tooltip content={text} side={side} width="w-64">
        <HelpCircle className="w-4 h-4 text-gray-400 hover:text-emerald-400 transition-colors cursor-help" />
      </Tooltip>
    );
  };

  const sliderBg = (value) => {
    const pct = Math.round(value * 100);
    return {
      background: `linear-gradient(to right, #25C08A 0%, #1EAB78 ${pct}%, rgba(255,255,255,0.06) ${pct}%, rgba(255,255,255,0.06) 100%)`,
    };
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        showCollapsible={true}
        onToggleSidebar={toggleSidebar}
        collapsed={collapsed}
      />

      {/* barre latérale */}
      <aside
        className={`${
          collapsed ? "w-0 opacity-0" : "w-80 opacity-100 p-6 space-y-6"
        } relative bg-[#272727] text-white transition-all duration-300`}
      >
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
              No current local models found, please add local models to proceed.
            </div>
            {/* Language Warning */}
              <div className="flex justify-center px-2 pb-1">
                <div className="w-[700px] max-w-full">
                  <div
                    className={[
                      "relative w-full rounded-[26px] overflow-hidden",
                      "bg-[rgba(64,35,22,0.45)] backdrop-blur-[18px] saturate-[1.4]",
                      "shadow-[0_8px_30px_-4px_rgba(0,0,0,0.45),0_2px_6px_-1px_rgba(0,0,0,0.4),inset_0_1px_0_rgba(255,200,150,0.06)]",
                    ].join(" ")}
                  >
                    <div
                      aria-hidden
                      className="absolute inset-0 pointer-events-none rounded-[26px] mix-blend-overlay"
                      style={{
                        background:
                          "linear-gradient(to bottom, rgba(255,180,100,0.18), rgba(255,180,100,0) 40%)",
                      }}
                    />
                    <div
                      aria-hidden
                      className="absolute inset-0 pointer-events-none rounded-[26px] opacity-35 mix-blend-overlay"
                      style={{
                        backgroundImage:
                          'url("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAABVUlEQVRYR+2WvQ3CMAyFPxF0AB1AB1ABN0AHcAF0gA3QATpN0lInyY5kUVqSk4TsSIv8P2RNFpBf6h8Bi5TBSW0AVbAAmwBpjqgA3wD1fYwHzwFR3QAdwDvl7T2JQG4C7gA/H8LwAVtFznGKnyD20PnKQqa5wzwwM3Vl8r9mQwZP4RFL9XPs35SHJxKcVd5jTwK9K1u4ErfJUF2XblI8g4BtMSSYlLQF41f+WAbc42t7CM6ikgs6Y2oT64y8G8BuEorQFrirN4i0cK4erQblIDmI+F6kAD0fYp2RchEot1Hc6S/T/lNa8T1nDjMDPxgg7wM8S+P8Gn8UH2Piu0mV9K/VLBbq+508Quy_ngGBrhV98yYzeBdOL4SqyGoccEqbE6+ZjKlj19qCxgY6N8lH3dy5zvY1/drdEw2d+uHMDuHwrK0Yas7PwAxRxmKJl0VokAAAAASUVORK5CYII=")',
                        backgroundSize: "200px 200px",
                      }}
                    />

            {/* Content */}
              <div className="relative z-10 p-6">
                <h2 className="text-lg font-semibold tracking-tight text-orange-100 mb-3">
                  Note on Language
                </h2>
                <p className="text-sm text-orange-200/80 mb-3">
                  Base models have been massively trained on English data. You will get significantly better results by chatting in English.
                </p>
                <p className="text-sm text-orange-200/70 italic">
                  Pour les français, ça vous fera de l'entraînement :)
                </p>
              </div>
          </div>
        </div>
      </div>
          </GradientBox>
        ) : (
          /* Interface de création de chat avec design HeaderBar */
          <div className="w-[700px] max-w-full">
            {/* Logo Erudi */}
            <div className="flex justify-center mb-8">
              <img 
                src={logoErudi} 
                alt="Erudi" 
                className="h-20 w-auto" 
              />
            </div>

            {/* HeaderBar-like container */}
            <div
              className={[
                "hb-scope relative w-full rounded-[26px] mb-6",
                "border border-white/10",
                "bg-[rgba(22,40,36,0.45)] backdrop-blur-[18px] saturate-[1.4]",
                "shadow-[0_8px_30px_-4px_rgba(0,0,0,0.45),0_2px_6px_-1px_rgba(0,0,0,0.4),inset_0_1px_0_rgba(255,255,255,0.06)]",
              ].join(" ")}
            >
              {/* Glossy overlays */}
              <div
                aria-hidden
                className="absolute inset-0 pointer-events-none rounded-[26px] mix-blend-overlay"
                style={{
                  background:
                    "linear-gradient(to bottom, rgba(255,255,255,0.18), rgba(255,255,255,0) 40%)",
                }}
              />
              <div
                aria-hidden
                className="absolute inset-0 pointer-events-none rounded-[26px] opacity-35 mix-blend-overlay"
                style={{
                  backgroundImage:
                    'url("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAABVUlEQVRYR+2WvQ3CMAyFPxF0AB1AB1ABN0AHcAF0gA3QATpN0lInyY5kUVqSk4TsSIv8P2RNFpBf6h8Bi5TBSW0AVbAAmwBpjqgA3wD1fYwHzwFR3QAdwDvl7T2JQG4C7gA/H8LwAVtFznGKnyD20PnKQqa5wzwwM3Vl8r9mQwZP4RFL9XPs35SHJxKcVd5jTwK9K1u4ErfJUF2XblI8g4BtMSSYlLQF41f+WAbc42t7CM6ikgs6Y2oT64y8G8BuEorQFrirN4i0cK4erQblIDmI+F6kAD0fYp2RchEot1Hc6S/T/lNa8T1nDjMDPxgg7wM8S+P8Gn8UH2Piu0mV9K/VLBbq+508Quy_ngGBrhV98yYzeBdOL4SqyGoccEqbE6+ZjKlj19qCxgY6N8lH3dy5zvY1/drdEw2d+uHMDuHwrK0Yas7PwAxRxmKJl0VokAAAAASUVORK5CYII=")',
                  backgroundSize: "200px 200px",
                }}
              />

              <div className="relative z-10 p-5">
                <style>{`
        .hb-scope input.hb-range { -webkit-appearance: none; appearance: none; height: 6px; border-radius: 999px; outline: none; }
        .hb-scope input.hb-range::-webkit-slider-thumb {
          -webkit-appearance: none; width: 18px; height: 18px; border-radius: 50%; border: 0; cursor: pointer;
          background: radial-gradient(circle at 30% 30%, #ffffff, #d9e4dd 60%, #b7c6c0 100%);
          box-shadow: 0 2px 6px rgba(0,0,0,0.45), 0 0 0 1px rgba(255,255,255,0.4), inset 0 1px 2px rgba(255,255,255,0.7);
          transition: transform .25s ease, box-shadow .25s ease;
        }
        .hb-scope input.hb-range:hover::-webkit-slider-thumb { transform: scale(1.07); }
        .hb-scope input.hb-range:active::-webkit-slider-thumb { transform: scale(.9); }
        .hb-scope input.hb-range:focus-visible::-webkit-slider-thumb {
          box-shadow: 0 0 0 4px rgba(37,192,138,0.35), 0 2px 6px rgba(0,0,0,0.55), inset 0 1px 2px rgba(255,255,255,0.8);
        }
        .hb-scope input.hb-range::-moz-range-track { height: 6px; background: rgba(255,255,255,0.06); border-radius: 999px; }
        .hb-scope input.hb-range::-moz-range-thumb {
          width: 18px; height: 18px; border-radius: 50%; border: 0; cursor: pointer;
          background: radial-gradient(circle at 30% 30%, #ffffff, #d9e4dd 60%, #b7c6c0 100%);
          box-shadow: 0 2px 6px rgba(0,0,0,0.45), 0 0 0 1px rgba(255,255,255,0.4), inset 0 1px 2px rgba(255,255,255,0.7);
        }
        .hb-scope input.hb-range:focus-visible::-moz-range-thumb {
          box-shadow: 0 0 0 4px rgba(37,192,138,0.35), 0 2px 6px rgba(0,0,0,0.55), inset 0 1px 2px rgba(255,255,255,0.8);
        }
      `}</style>

                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3 flex-wrap min-w-0">
                    <h3 className="text-[1.15rem] font-semibold tracking-tight text-[#F2F7F4] truncate">
                      Chat with
                    </h3>

                    <div
                      ref={dropdownRef}
                      className={[
                        "inline-flex items-center rounded-lg relative z-50",
                        "px-3.5 py-1.5 text-sm",
                        "border transition",
                        "bg-white/5 hover:bg-white/10 border-white/10 hover:border-white/20",
                        "backdrop-blur-sm text-gray-100",
                        "max-w-[100%] cursor-pointer",
                      ].join(" ")}
                      onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                    >
                      <div
                        className="font-medium truncate pr-5 max-w-[150px]"
                        title={selectedModel}
                      >
                        {selectedModel || "Select model..."}
                      </div>
                      <ChevronDown
                        size={16}
                        className={`opacity-70 shrink-0 transition-transform absolute right-3 ${
                          isDropdownOpen ? "rotate-180" : ""
                        }`}
                      />

                      {/* Custom Dropdown */}
                      {isDropdownOpen && (
                        <div className="absolute top-full left-0 right-0 mt-1 bg-[#2a2a2a] border border-white/20 rounded-lg shadow-lg z-[9999] max-h-60 overflow-y-auto">
                          {models.map((m) => (
                            <div
                              key={m.id ?? m.name}
                              className="px-3 py-2 hover:bg-white/10 cursor-pointer text-gray-100 border-b border-white/10 last:border-b-0"
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedModel(m.name);
                                setIsDropdownOpen(false);
                              }}
                            >
                              {m.name}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  <button
                    type="button"
                    aria-label="Toggle settings"
                    onClick={() => setIsSettingsOpen((v) => !v)}
                    className={[
                      "inline-flex items-center justify-center",
                      "w-9 h-9 rounded-xl",
                      "bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20",
                      "text-gray-300 hover:text-emerald-400 transition",
                      "shrink-0",
                    ].join(" ")}
                  >
                    <SlidersHorizontal size={18} />
                  </button>
                </div>

                <AnimatePresence initial={false}>
                  {isSettingsOpen && (
                    <motion.div
                      key="controls"
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ type: "tween", duration: 0.3 }}
                      className="overflow-hidden"
                    >
                      <div className="mt-6 grid gap-6 md:grid-cols-2">
                        <div className="flex flex-col gap-6">
                          <div className="relative">
                            <div className="flex items-center gap-1.5 mb-1">
                              <span className="text-[0.72rem] uppercase tracking-wide font-semibold text-gray-300/80">
                                Creativity
                              </span>
                              <TooltipIcon id="temperature" side="right" />
                              <span className="ml-auto text-[11px] font-semibold text-emerald-200/90 bg-emerald-500/10 px-2 py-0.5 rounded-md border border-emerald-400/25">
                                {settings.temperature.toFixed(2)}
                              </span>
                            </div>

                            <div className="relative pt-1">
                              <input
                                type="range"
                                min="0"
                                max="1"
                                step="0.01"
                                value={settings.temperature}
                                onChange={(e) =>
                                  setSettings((prev) => ({
                                    ...prev,
                                    temperature: parseFloat(e.target.value),
                                  }))
                                }
                                className="hb-range w-full rounded-full bg-white/5 cursor-pointer"
                                style={sliderBg(settings.temperature)}
                              />
                            </div>
                          </div>

                          <div className="relative">
                            <div className="flex items-center gap-1.5 mb-1">
                              <span className="text-[0.72rem] uppercase tracking-wide font-semibold text-gray-300/80">
                                Diversity
                              </span>
                              <TooltipIcon id="top-p" side="right" />
                              <span className="ml-auto text-[11px] font-semibold text-emerald-200/90 bg-emerald-500/10 px-2 py-0.5 rounded-md border border-emerald-400/25">
                                {settings.topP.toFixed(2)}
                              </span>
                            </div>

                            <div className="relative pt-1">
                              <input
                                type="range"
                                min="0"
                                max="1"
                                step="0.01"
                                value={settings.topP}
                                onChange={(e) =>
                                  setSettings((prev) => ({
                                    ...prev,
                                    topP: parseFloat(e.target.value),
                                  }))
                                }
                                className="hb-range w-full rounded-full bg-white/5 cursor-pointer"
                                style={sliderBg(settings.topP)}
                              />
                            </div>
                          </div>
                        </div>

                        <div className="flex flex-col justify-center gap-6">
                          <div>
                            <div className="grid grid-cols-2 items-start justify-items-start gap-x-6 gap-y-2 mb-2">
                              <div>
                                <span className="text-[0.72rem] uppercase tracking-wide font-semibold text-gray-300/80">
                                  Max Tokens
                                </span>
                              </div>
                              {/* Controls row */}
                              <div className="inline-flex items-center rounded-md bg-white/10 border border-white/20 shadow p-0 m-0 w-fit justify-self-start">
                                <input
                                  type="number"
                                  min="1"
                                  max="2000"
                                  value={settings.maxTokens}
                                  onChange={(e) =>
                                    setSettings((prev) => ({
                                      ...prev,
                                      maxTokens: parseInt(
                                        e.target.value || "0",
                                        10
                                      ),
                                    }))
                                  }
                                  className="bg-transparent border-0 outline-none w-28 text-sm font-semibold text-gray-100 text-center appearance-none [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                                />
                              </div>

                            </div>
                          </div>

                          <div className="flex flex-row items-center gap-3 w-full">
                            <div className="flex items-center gap-2 w-full">
                              <button
                                type="button"
                                onClick={() => setShowPromptModal(true)}
                                className={[
                                  "rounded-md font-semibold",
                                  "px-5 py-2 text-[0.9rem]",
                                  "bg-emerald-800 hover:bg-emerald-900 text-white",
                                  "border border-white/20 shadow",
                                  "transition active:scale-95",
                                ].join(" ")}
                              >
                                Customize Prompt
                              </button>
                              <div>
                                <TooltipIcon id="prompt" side="top-left" />
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Question Input - Always visible */}
                <div className="mt-6">
                  <QuestionInput 
                    onSend={handleAsk} 
                    placeholder="Ask me anything..."
                  />
                </div>
                {/* Language Warning */}
              <div className="flex justify-center mt-6 px-2 pb-1">
                <div className="w-[700px] max-w-full">
                  <div
                    className={[
                      "relative w-full rounded-[26px] overflow-hidden cursor-pointer transition-all duration-300",
                      "bg-[rgba(64,35,22,0.45)] backdrop-blur-[18px] saturate-[1.4]",
                      "shadow-[0_8px_30px_-4px_rgba(0,0,0,0.45),0_2px_6px_-1px_rgba(0,0,0,0.4),inset_0_1px_0_rgba(255,200,150,0.06)]",
                      "hover:border-orange-600/40",
                    ].join(" ")}
                    onClick={() => setIsLanguageWarningExpanded(!isLanguageWarningExpanded)}
                  >
                    <div
                      aria-hidden
                      className="absolute inset-0 pointer-events-none rounded-[26px] mix-blend-overlay"
                      style={{
                        background:
                          "linear-gradient(to bottom, rgba(255,180,100,0.18), rgba(255,180,100,0) 40%)",
                      }}
                    />
                    <div
                      aria-hidden
                      className="absolute inset-0 pointer-events-none rounded-[26px] opacity-35 mix-blend-overlay"
                      style={{
                        backgroundImage:
                          'url("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAABVUlEQVRYR+2WvQ3CMAyFPxF0AB1AB1ABN0AHcAF0gA3QATpN0lInyY5kUVqSk4TsSIv8P2RNFpBf6h8Bi5TBSW0AVbAAmwBpjqgA3wD1fYwHzwFR3QAdwDvl7T2JQG4C7gA/H8LwAVtFznGKnyD20PnKQqa5wzwwM3Vl8r9mQwZP4RFL9XPs35SHJxKcVd5jTwK9K1u4ErfJUF2XblI8g4BtMSSYlLQF41f+WAbc42t7CM6ikgs6Y2oT64y8G8BuEorQFrirN4i0cK4erQblIDmI+F6kAD0fYp2RchEot1Hc6S/T/lNa8T1nDjMDPxgg7wM8S+P8Gn8UH2Piu0mV9K/VLBbq+508Quy_ngGBrhV98yYzeBdOL4SqyGoccEqbE6+ZjKlj19qCxgY6N8lH3dy5zvY1/drdEw2d+uHMDuHwrK0Yas7PwAxRxmKJl0VokAAAAASUVORK5CYII=")',
                        backgroundSize: "200px 200px",
                      }}
                    />

            {/* Content */}
              <div className="relative z-10 p-4 px-6">
                <div className="flex items-center justify-between">
                  <h2 className="text-base font-semibold tracking-tight text-orange-100">
                    Note on Language
                  </h2>
                  <motion.div
                    animate={{ rotate: isLanguageWarningExpanded ? 180 : 0 }}
                    transition={{ duration: 0.3 }}
                  >
                    <ChevronDown className="w-5 h-5 text-orange-100" />
                  </motion.div>
                </div>
                
                <AnimatePresence>
                  {isLanguageWarningExpanded && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.3 }}
                      className="overflow-hidden"
                    >
                      <p className="text-sm text-orange-200/80 mb-3 mt-3">
                        Base models have been massively trained on English data. You will get significantly better results by chatting in English.
                      </p>
                      <p className="text-sm text-orange-200/70 italic">
                        Pour les français, ça vous fera de l'entraînement :)
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
          </div>
        </div>
      </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Error Popup */}
      <ErrorModal
        errorMessage={errorMessage}
        onClose={() => setErrorMessage("")}
      />

      {/* Customize Prompt Modal */}
      <CustomizePromptModal
        isOpen={showPromptModal}
        onClose={() => setShowPromptModal(false)}
        customPrompt={customPrompt}
        onSave={(newPrompt) => setCustomPrompt(newPrompt)}
        title="Customize System Prompt"
      />
    </div>
  );
}
