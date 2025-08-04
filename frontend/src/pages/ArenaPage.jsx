import React, { useEffect, useState, useRef } from "react";
import Sidebar from "../components/Sidebar";
import GradientBox from "../components/GradientBox";
import QuestionInput from "../components/QuestionInput";
import { askArena } from "../services/arenaService.js";
import { Trash } from "lucide-react";
import HeaderBar from "../components/HeaderBar";
import { API_BASE_URL } from "../config/api";

const MAX_PANELS = 4;
const DEFAULT_SETTINGS = {
  temperature: 0.5,
  topP: 0.9,
  maxTokens: 200,
  customPrompt: "",
};

function makePanel(id, modelName = "", models = []) {
  return {
    id,
    selectedModel: modelName || (models[0]?.name ?? ""),
    temperature: DEFAULT_SETTINGS.temperature,
    topP: DEFAULT_SETTINGS.topP,
    maxTokens: DEFAULT_SETTINGS.maxTokens,
    customPrompt: DEFAULT_SETTINGS.customPrompt,
    messages: [],
    showPromptModal: false,
  };
}

export default function ArenaPage() {
  const [models, setModels] = useState([]);
  const [panels, setPanels] = useState([]);
  const [inputValue, setInputValue] = useState("");
  const [loading, setLoading] = useState(false);

  const streamingPanels = useRef(new Set());
  const buffersRef = useRef({});
  const flushIntervalRef = useRef(null);

  useEffect(() => {
    return () => {
      if (flushIntervalRef.current) clearInterval(flushIntervalRef.current);
    };
  }, []);

  useEffect(() => {
    fetch(`${API_BASE_URL}/main_window/llms/local`)
      .then((res) => res.json())
      .then((data) => {
        setModels(data);
        setPanels(
          [0, 1].map((i) => makePanel(i, data[i % data.length]?.name, data))
        );
      })
      .catch((err) =>
        console.error("Erreur lors du fetch des modèles:", err)
      );
  }, []);

  const handleModelChange = (panelId, newModel) =>
    setPanels((prev) =>
      prev.map((p) =>
        p.id === panelId ? { ...p, selectedModel: newModel } : p
      )
    );

  const handleSettingsChange = (panelId, newSettings) =>
    setPanels((prev) =>
      prev.map((p) => (p.id === panelId ? { ...p, ...newSettings } : p))
    );

  const handleCustomizePrompt = (panelId, show) =>
    setPanels((prev) =>
      prev.map((p) => (p.id === panelId ? { ...p, showPromptModal: show } : p))
    );

  const handleAsk = async (inputValue) => {
    if (flushIntervalRef.current) clearInterval(flushIntervalRef.current);
    setLoading(true);

    const withPlaceholders = panels.map((panel) => ({
      ...panel,
      messages: [
        ...panel.messages,
        { role: "user", content: inputValue },
        { role: "llm", content: "" },
      ],
    }));
    setPanels(withPlaceholders);

    buffersRef.current = {};
    streamingPanels.current = new Set(withPlaceholders.map((p) => p.id));
    withPlaceholders.forEach((p) => {
      buffersRef.current[p.id] = [];
    });

    const flushBuffers = () => {
      const stillStreaming = streamingPanels.current.size > 0;
      const activeIds = stillStreaming
        ? Array.from(streamingPanels.current)
        : Object.keys(buffersRef.current).map(Number);

      const ready = stillStreaming
        ? activeIds.every((id) => buffersRef.current[id].length > 0)
        : activeIds.some((id) => buffersRef.current[id].length > 0);

      if (!ready) return;

      setPanels((prev) =>
        prev.map((p) => {
          const buf = buffersRef.current[p.id];
          if (buf?.length) {
            const nextTok = buf.shift();
            const msgs = [...p.messages];
            msgs[msgs.length - 1] = {
              ...msgs[msgs.length - 1],
              content: msgs[msgs.length - 1].content + nextTok,
            };
            return { ...p, messages: msgs };
          }
          return p;
        })
      );

      if (
        !stillStreaming &&
        activeIds.every((id) => buffersRef.current[id].length === 0)
      ) {
        clearInterval(flushIntervalRef.current);
        flushIntervalRef.current = null;
        setLoading(false);
      }
    };
    flushIntervalRef.current = setInterval(flushBuffers, 50);

    withPlaceholders.forEach((panel) => {
      const llm = models.find((m) => m.name === panel.selectedModel);
      if (!llm) {
        buffersRef.current[panel.id].push("[Model not found]");
        streamingPanels.current.delete(panel.id);
        if (streamingPanels.current.size === 0) setLoading(false);
        return;
      }

      askArena({
        question:     inputValue,
        llmId:        llm.id,
        temperature:  panel.temperature,
        topP:         panel.topP,
        maxNewTokens: panel.maxTokens,
        customPrompt: panel.customPrompt,
        onStreamChunk: (chunk) => {
          buffersRef.current[panel.id].push(chunk);
        },
      })
        .then(() => {
          streamingPanels.current.delete(panel.id);
          if (streamingPanels.current.size === 0) setLoading(false);
        })
        .catch(() => {
          buffersRef.current[panel.id].push("[Erreur]");
          streamingPanels.current.delete(panel.id);
          if (streamingPanels.current.size === 0) setLoading(false);
        });
    });

    setInputValue("");
  };

  const handleAddPanel = () => {
    if (panels.length >= MAX_PANELS) return;
    const nextId = panels.length
      ? Math.max(...panels.map((p) => p.id)) + 1
      : 0;
    const defaultModel = models[panels.length % models.length]?.name || "";
    setPanels((prev) => [...prev, makePanel(nextId, defaultModel, models)]);
  };

  const handleDeletePanel = (panelId) =>
    setPanels((prev) => prev.filter((p) => p.id !== panelId));

  let gridClass = "";
  if (panels.length === 1) gridClass = "grid-cols-1";
  else if (panels.length === 2) gridClass = "grid-cols-2";
  else if (panels.length === 3) gridClass = "grid-cols-3";
  else if (panels.length === 4) gridClass = "grid-cols-2 grid-rows-2";

  const renderChatPanel = (panel) => (
    <GradientBox
      key={panel.id}
      className="flex flex-col mx-2 min-w-[320px] h-full"
    >
      <div className="flex items-center justify-between pb-2">
        <HeaderBar
          initialTemperature={panel.temperature}
          initialTopP={panel.topP}
          initialMaxTokens={panel.maxTokens}
          onApply={(s) => handleSettingsChange(panel.id, s)}
          onCustomizePrompt={() => handleCustomizePrompt(panel.id, true)}
          disabled={loading}
          models={models}
          currentModel={panel.selectedModel}
          onModelChange={(m) => handleModelChange(panel.id, m)}
        />
        {panel.showPromptModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg shadow-lg w-11/12 max-w-md p-6">
              <h2 className="text-xl font-semibold mb-4">
                Personnaliser le prompt
              </h2>
              <textarea
                className="w-full h-40 border rounded p-2 mb-4"
                value={panel.customPrompt}
                onChange={(e) =>
                  handleSettingsChange(panel.id, {
                    customPrompt: e.target.value,
                  })
                }
              />
              <div className="flex justify-end space-x-2">
                <button
                  onClick={() => handleCustomizePrompt(panel.id, false)}
                  className="px-4 py-2 bg-gray-300 rounded hover:bg-gray-400"
                >
                  Annuler
                </button>
                <button
                  onClick={() => handleCustomizePrompt(panel.id, false)}
                  className="px-4 py-2 bg-emerald-600 text-white rounded hover:bg-emerald-700"
                >
                  Enregistrer
                </button>
              </div>
            </div>
          </div>
        )}
        <button
          className="p-1 text-gray-400 hover:text-gray-200"
          onClick={() => handleDeletePanel(panel.id)}
          title="Delete this panel"
        >
          <Trash className="w-5 h-5" />
        </button>
      </div>

      {/* scrollable messages area */}
      <div className="flex-1 overflow-y-auto flex flex-col gap-2 pb-6">
        {panel.messages.map((msg, idx) => (
          <div
            key={idx}
            className={`rounded-xl px-4 py-2 my-1 max-w-[90%] whitespace-pre-line ${
              msg.role === "user"
                ? "bg-emerald-900/40 text-white self-end"
                : "text-white self-start"
            }`}
          >
            {msg.content}
          </div>
        ))}
      </div>
    </GradientBox>
  );

  return (
    <div className="flex h-screen">
      <Sidebar disabled={loading} />
      <main className="flex-1 flex flex-col bg-[#071b18] relative">
        {/* grid with panels, full height */}
        <div className={`flex-1 p-8 grid gap-4 ${gridClass} h-full`}>
          {panels.map(renderChatPanel)}
        </div>

        {/* input bar */}
        <div className="w-full flex justify-center items-center pb-8">
          <div className="w-[700px] max-w-full">
            <QuestionInput
              onSend={handleAsk}
              backgroundClass="bg-emerald-900"
              disabled={loading}
            />
          </div>
        </div>

        {/* add-panel button */}
        <button
          className={`fixed bottom-8 right-8 z-50 bg-emerald-500 hover:bg-emerald-600 text-white rounded-full w-14 h-14 flex items-center justify-center text-4xl shadow-lg transition-all duration-200 ${
            panels.length >= MAX_PANELS ? "opacity-50 cursor-not-allowed" : ""
          }`}
          onClick={handleAddPanel}
          disabled={panels.length >= MAX_PANELS}
          title={
            panels.length >= MAX_PANELS
              ? "Maximum 4 panels"
              : "Add chat panel"
          }
        >
          +
        </button>
      </main>
    </div>
  );
}
