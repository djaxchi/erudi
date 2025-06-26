import React, { useEffect, useState } from "react";
import Sidebar from "../components/Sidebar";
import GradientBox from "../components/GradientBox";
import QuestionInput from "../components/QuestionInput";
import { askArena } from "../services/arenaService.js";
import { Trash } from "lucide-react";
import HeaderBar from "../components/HeaderBar";

const MAX_PANELS = 4;
const DEFAULT_SETTINGS = {
  temperature: 0.5,
  topP: 0.9,
  maxTokens: 1000,
  customPrompt: "",
};

function makePanel(id, modelName = "", models = []) {
  const initialMessages = [
    { role: "user", content: "Hello, how are you?" },
    {
      role: "llm",
      content:
        "I'm doing well, thank you for asking. How can I assist you today?",
    },
    {
      role: "user",
      content:
        "I'm looking for information on the latest advancements in AI research.",
    },
    {
      role: "llm",
      content:
        "There have been many exciting developments in AI research recently. Would you like me to summarize some of the key findings?",
    },
    { role: "user", content: "Yes, please do." },
    {
      role: "llm",
      content:
        "Sure! Here are some of the latest advancements in AI research...",
    },
    { role: "user", content: "Thank you, that's very helpful!" },
    {
      role: "llm",
      content:
        "You're welcome! If you have any more questions, feel free to ask.",
    },
    { role: "user", content: "What are the ethical implications of AI?" },
    {
      role: "llm",
      content:
        "The ethical implications of AI are vast and complex. They include concerns about privacy, bias, job displacement, and the potential for misuse.",
    },
    { role: "user", content: "Can you give me an example of AI bias?" },
    {
      role: "llm",
      content:
        "Certainly! An example of AI bias is when a facial recognition system performs better on certain demographics than others, leading to unequal accuracy rates.",
    },
    { role: "user", content: "How can we mitigate AI bias?" },
    {
      role: "llm",
      content:
        "Mitigating AI bias involves using diverse training data, implementing fairness algorithms, and continuously monitoring AI systems for biased outcomes.",
    },
    { role: "user", content: "Thank you for the information!" },
    {
      role: "llm",
      content:
        "You're welcome! If you have any more questions or need further assistance, feel free to ask.",
    },
    { role: "user", content: "What are the latest trends in AI?" },
    {
      role: "llm",
      content:
        "Some of the latest trends in AI include advancements in natural language processing, computer vision, and reinforcement learning.",
    },
    { role: "user", content: "Can you explain reinforcement learning?" },
    {
      role: "llm",
      content:
        "Reinforcement learning is a type of machine learning where an agent learns to make decisions by receiving rewards or penalties based on its actions.",
    },
    { role: "user", content: "Thank you for explaining!" },
    {
      role: "llm",
      content:
        "You're welcome! If you have any more questions or need further clarification, feel free to ask.",
    },
  ];
  return {
    id,
    selectedModel: modelName || (models[0]?.name ?? ""),
    temperature: DEFAULT_SETTINGS.temperature,
    topP: DEFAULT_SETTINGS.topP,
    maxTokens: DEFAULT_SETTINGS.maxTokens,
    customPrompt: DEFAULT_SETTINGS.customPrompt,
    messages: initialMessages,
    showPromptModal: false,
  };
}

export default function ArenaPage() {
  const [models, setModels] = useState([]);
  const [panels, setPanels] = useState([]);
  const [inputValue, setInputValue] = useState("");
  const [loading, setLoading] = useState(false);

  // Fetch models and initialize panels
  useEffect(() => {
    fetch("http://127.0.0.1:8000/main_window/llms/local")
      .then((res) => res.json())
      .then((data) => {
        setModels(data);
        setPanels(
          [0, 1].map((i) => makePanel(i, data[i % data.length]?.name, data))
        );
      })
      .catch((err) => console.error("Erreur lors du fetch des modèles:", err));
  }, []);

  // Handle model change for a panel
  const handleModelChange = (panelId, newModel) => {
    setPanels((prev) =>
      prev.map((panel) =>
        panel.id === panelId ? { ...panel, selectedModel: newModel } : panel
      )
    );
  };

  // Handle settings change for a panel
  const handleSettingsChange = (panelId, newSettings) => {
    setPanels((prev) =>
      prev.map((panel) =>
        panel.id === panelId ? { ...panel, ...newSettings } : panel
      )
    );
  };

  // Handle prompt customization for a panel
  const handleCustomizePrompt = (panelId, show) => {
    setPanels((prev) =>
      prev.map((panel) =>
        panel.id === panelId ? { ...panel, showPromptModal: show } : panel
      )
    );
  };

  // Handle prompt input and LLM response
  const handleAsk = async (inputValue) => {
    setLoading(true);

    // Add user message to each panel
    setPanels((prev) =>
      prev.map((panel) => ({
        ...panel,
        messages: [...panel.messages, { role: "user", content: inputValue }],
      }))
    );

    // Wait for state update
    await new Promise((resolve) => setTimeout(resolve, 0));

    // Pour chaque panel on va :
    // 1) ajouter un message assistant vide
    // 2) lancer askArena en streaming, et coller les chunks au fur et à mesure
    panels.forEach((panel) => {
      const llm = models.find((m) => m.name === panel.selectedModel);
      if (!llm) {
        return setPanels((prev) =>
          prev.map((p) =>
            p.id === panel.id
              ? {
                  ...p,
                  messages: [
                    ...p.messages,
                    { role: "llm", content: "[Model not found]" },
                  ],
                }
              : p
          )
        );
      }

      // 1) on ajoute le message assistant vide
      setPanels((prev) =>
        prev.map((p) =>
          p.id === panel.id
            ? { ...p, messages: [...p.messages, { role: "llm", content: "" }] }
            : p
        )
      );

      // 2) on stream la réponse
      askArena({
        question: inputValue,
        llmId: llm.id,
        temperature: panel.temperature,
        topP: panel.topP,
        maxNewTokens: panel.maxTokens,
        customPrompt: panel.customPrompt,
        onStreamChunk: (chunk) => {
          setPanels((prev) =>
            prev.map((p) => {
              if (p.id !== panel.id) return p;
              const msgs = [...p.messages];
              const last = msgs.pop();
              msgs.push({ ...last, content: last.content + chunk });
              return { ...p, messages: msgs };
            })
          );
        },
      }).catch(() => {
        // en cas d’erreur de stream, on remplace le message vide par "[Erreur]"
        setPanels((prev) =>
          prev.map((p) =>
            p.id === panel.id
              ? {
                  ...p,
                  messages: [
                    ...p.messages.slice(0, -1),
                    { role: "llm", content: "[Erreur]" },
                  ],
                }
              : p
          )
        );
      });
    });

    setInputValue("");
    setLoading(false);
  };

  const handleAddPanel = () => {
    if (panels.length >= MAX_PANELS) return;
    const nextId =
      panels.length > 0 ? Math.max(...panels.map((p) => p.id)) + 1 : 0;
    const defaultModel = models[panels.length % models.length]?.name || "";
    setPanels((prev) => [...prev, makePanel(nextId, defaultModel, models)]);
  };

  const handleDeletePanel = (panelId) => {
    setPanels((prev) => prev.filter((panel) => panel.id !== panelId));
  };

  // Grid layout logic (unchanged)
  let gridClass = "";
  if (panels.length === 1) {
    gridClass = "grid grid-cols-1 gap-4 w-full h-full";
  } else if (panels.length === 2) {
    gridClass = "grid grid-cols-2 gap-4 w-full";
  } else if (panels.length === 3) {
    gridClass = "grid grid-cols-3 gap-4 w-full";
  } else if (panels.length === 4) {
    gridClass = "grid grid-cols-2 grid-rows-2 gap-4 w-full";
  }

  const renderChatPanel = (panel) => (
    <GradientBox
      key={panel.id}
      className="flex flex-col mx-2 min-w-[320px] h-[80vh]"
    >
      <div className="flex items-center justify-between pb-2">
        <HeaderBar
          initialTemperature={panel.temperature}
          initialTopP={panel.topP}
          initialMaxTokens={panel.maxTokens}
          onApply={(newSettings) => handleSettingsChange(panel.id, newSettings)}
          onCustomizePrompt={() => handleCustomizePrompt(panel.id, true)}
          disabled={loading}
          models={models}
          currentModel={panel.selectedModel}
          onModelChange={(modelName) => handleModelChange(panel.id, modelName)}
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
      <div
        className="flex-1 min-h-0 overflow-y-auto flex flex-col gap-2 pb-6 custom-scroll"
        style={{
          scrollbarWidth: "none",
          msOverflowStyle: "none",
        }}
      >
        <style>
          {`
            .custom-scroll::-webkit-scrollbar {
              display: none;
            }
          `}
        </style>
        {panel.messages.map((msg, idx) => (
          <div
            key={idx}
            className={`rounded-xl px-4 py-2 my-1 max-w-[90%] whitespace-pre-line ${
              msg.role === "user"
                ? "bg-emerald-900/40 text-white self-end"
                : "bg-gray-800/80 text-white self-start"
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
      <main
        className="flex-1 flex flex-col bg-[#071b18] relative overflow-auto custom-scroll"
        style={{ paddingBottom: "4rem" }}
      >
        <div className={`flex-1 p-8 ${gridClass}`}>
          {panels.map(renderChatPanel)}
        </div>
        {/* <div className="w-full flex justify-center items-center pb-8">
          <div className="w-[700px] max-w-full">
            <QuestionInput
              onSend={handleAsk}
              backgroundClass="bg-emerald-900"
              disabled={loading}
            />
          </div>
        </div> */}
        <button
          className={`fixed bottom-8 right-8 z-50 bg-emerald-500 hover:bg-emerald-600 text-white rounded-full w-14 h-14 flex items-center justify-center text-4xl shadow-lg transition-all duration-200 ${
            panels.length >= MAX_PANELS ? "opacity-50 cursor-not-allowed" : ""
          }`}
          onClick={handleAddPanel}
          disabled={panels.length >= MAX_PANELS}
          title={
            panels.length >= MAX_PANELS ? "Maximum 4 panels" : "Add chat panel"
          }
        >
          +
        </button>
        {loading && (
          <div className="fixed inset-0 z-[100] bg-black bg-opacity-40 flex items-center justify-center cursor-progress select-none">
            <div className="text-white text-xl font-bold animate-pulse">
              Loading...
            </div>
          </div>
        )}
      </main>
      <div className="fixed bottom-0 left-0 right-0 flex justify-center z-30">
        <div className="max-w-lg w-full px-4 py-2">
          <QuestionInput
            onSend={handleAsk}
            backgroundClass="bg-emerald-900"
            disabled={loading}
          />
        </div>
      </div>
    </div>
  );
}
