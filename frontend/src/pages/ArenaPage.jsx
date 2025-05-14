import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import GradientBox from "../components/GradientBox";
import QuestionInput from "../components/QuestionInput";
import { ask } from "../services/conversationService";
import { Trash } from "lucide-react";

const MAX_PANELS = 4;

export default function ArenaPage() {
  const [models, setModels] = useState([]);
  const [panels, setPanels] = useState([
    { id: 0, selectedModel: "", messages: [] },
    { id: 1, selectedModel: "", messages: [] },
  ]);
  const [inputValue, setInputValue] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch("http://127.0.0.1:8000/main_window/llms/local")
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setModels(data);
          setPanels((prev) =>
            prev.map((panel, idx) => ({
              ...panel,
              selectedModel: data[idx % data.length].name,
            }))
          );
        }
      })
      .catch((err) => console.error("Erreur lors du fetch des modèles:", err));
  }, []);

  const handleAsk = async () => {
    if (!inputValue.trim() || loading) return;
    setLoading(true);
    setPanels((prev) =>
      prev.map((panel) => ({
        ...panel,
        messages: [...panel.messages, { role: "user", content: inputValue }],
      }))
    );
    try {
      const responses = await Promise.all(
        panels.map((panel) => {
          const llm = models.find((m) => m.name === panel.selectedModel);
          if (!llm) return Promise.resolve({ answer: "[Model not found]" });
          return ask({ question: inputValue, llmId: llm.id });
        })
      );
      setPanels((prev) =>
        prev.map((panel, idx) => ({
          ...panel,
          messages: [
            ...panel.messages,
            {
              role: "llm",
              content:
                responses[idx].answer ||
                responses[idx].conversation?.messages?.slice(-1)[0]?.content ||
                "",
            },
          ],
        }))
      );
    } catch (err) {
      setPanels((prev) =>
        prev.map((panel) => ({
          ...panel,
          messages: [...panel.messages, { role: "llm", content: "[Erreur de réponse]" }],
        }))
      );
    }
    setInputValue("");
    setLoading(false);
  };

  const handleModelChange = (panelId, newModel) => {
    setPanels((prev) =>
      prev.map((panel) =>
        panel.id === panelId ? { ...panel, selectedModel: newModel } : panel
      )
    );
  };

  const handleAddPanel = () => {
    if (panels.length >= MAX_PANELS) return;
    const nextId = panels.length > 0 ? Math.max(...panels.map((p) => p.id)) + 1 : 0;
    setPanels((prev) => [
      ...prev,
      {
        id: nextId,
        selectedModel: models[prev.length % models.length]?.name || "",
        messages: [],
      },
    ]);
  };

  const handleDeletePanel = (panelId) => {
    setPanels((prev) => prev.filter((panel) => panel.id !== panelId));
  };

  // Grid layout logic
  let gridCols = 1;
  let gridRows = 1;
  if (panels.length === 2) {
    gridCols = 2;
    gridRows = 1;
  } else if (panels.length === 3) {
    gridCols = 2;
    gridRows = 2;
  } else if (panels.length === 4) {
    gridCols = 2;
    gridRows = 2;
  }

  // For 3 panels, show them side by side (3 columns)
  let gridPanels = panels;
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
  const renderChatPanel = (panel, idx) => (
    <GradientBox
      key={panel.id}
      className="flex flex-col mx-2 min-w-[320px] h-full"
    >
      <div className="flex items-center justify-between pb-2">
        {/* Chat with and model selector */}
        <div className="flex items-center gap-2">
          <h2 className="text-white text-3xl font-bold whitespace-nowrap">Chat with</h2>
          <div className="relative">
            <select
              className="appearance-none pr-8 pl-4 py-1 rounded-full border border-emerald-400 bg-transparent text-white focus:outline-none text-sm"
              onChange={(e) => handleModelChange(panel.id, e.target.value)}
              value={panel.selectedModel}
            >
              {models.map((model) => (
                <option key={model.id} value={model.name} className="text-black">
                  {model.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Trash Button */}
        <button
          className="p-1 text-gray-400 hover:text-gray-200"
          onClick={() => handleDeletePanel(panel.id)}
          title="Delete this panel"
        >
          <Trash className="w-5 h-5" />
        </button>
      </div>

      <div className="flex-1 flex flex-col gap-2 pb-6 overflow-y-auto">
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
      <Sidebar />
      <main className="flex-1 flex flex-col bg-[#071b18] relative">
        <div className={`flex-1 p-8 ${gridClass}`}>
          {gridPanels.map((panel, idx) =>
            renderChatPanel(panel, idx)
          )}
        </div>
        <div className="w-full flex justify-center items-center pb-8">
          <div className="w-[700px] max-w-full">
            <QuestionInput
              value={inputValue}
              onChange={setInputValue}
              onSend={handleAsk}
              loading={loading}
              placeholder="Ask a question..."
            />
          </div>
        </div>
        {/* Floating + button */}
        <button
          className={`fixed bottom-8 right-8 z-50 bg-emerald-500 hover:bg-emerald-600 text-white rounded-full w-14 h-14 flex items-center justify-center text-4xl shadow-lg transition-all duration-200 ${
            panels.length >= MAX_PANELS ? "opacity-50 cursor-not-allowed" : ""
          }`}
          onClick={handleAddPanel}
          disabled={panels.length >= MAX_PANELS}
          title={panels.length >= MAX_PANELS ? "Maximum 4 panels" : "Add chat panel"}
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
    </div>
  );
}