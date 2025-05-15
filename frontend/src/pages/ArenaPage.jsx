import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import GradientBox from "../components/GradientBox";
import QuestionInput from "../components/QuestionInput";
import { askArena } from "../services/arenaService";
import { Trash } from "lucide-react";
import HeaderBar from "../components/HeaderBar";


const MAX_PANELS = 4;
const DEFAULT_SETTINGS = {
    temperature: 0.5,
    topP: 0.9,
    maxTokens: 1000,
    customPrompt:"",
}

function makePanel(id, modelName=""){
    return{
        id,
        selectedModel: modelName,
        messages:[],
        ...DEFAULT_SETTINGS,
    }
}

export default function ArenaPage() {
  const [models, setModels] = useState([]);
  const [panels, setPanels] = useState(() => 
    [0,1].map(i=>makePanel(i,""))
  );
  const [inputValue, setInputValue] = useState("");
  const [loading, setLoading] = useState(false);
  const [createdConversationIds, setCreatedConversationIds] = useState([]);
  const createdConversationIdsRef = React.useRef(createdConversationIds);
  const [settings, setSettings] = useState({
    temperature: 0.5,
    topP: 0.9,
    maxTokens: 3074
  })
  const [showPromptModal, setShowPromptModal] = useState(false);
  const [customPrompt, setCustomPrompt] = useState("");

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

  const handleLeave = async () => {
    try {
      if (
        Array.isArray(createdConversationIdsRef.current) &&
        createdConversationIdsRef.current.length > 0
      ) {
        const response = await deleteConversations(createdConversationIdsRef.current);
      }
    } catch (error) {
      console.error("Failed to delete conversations", error);
    }
  };

  useEffect(() => {
    return () => {
      handleLeave(); // This runs when the component unmounts (when you leave the page)
    };
  }, []);

  useEffect(() => {
    const handleBeforeUnload = () => {
      handleLeave(); // 🔒 Ferme l'app ou l'onglet = appel de l'API
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, []);

  const handleAsk = async (inputValue) => {
    setLoading(true);

    // Build the updated panels with the user message
    let updatedPanels;
    setPanels(prev => {
      updatedPanels = prev.map(panel => ({
        ...panel,
        messages: [...panel.messages, { role: "user", content: inputValue }],
      }));
      return updatedPanels;
    });

    // Wait for the state update to finish (next tick)
    await new Promise(resolve => setTimeout(resolve, 0));

    try {
      // Use updatedPanels for API calls
      const responses = await Promise.all(
        updatedPanels.map(panel => {
          const llm = models.find(m => m.name === panel.selectedModel);
          if (!llm) return Promise.resolve("[Model not found]");
          const payload = {question: inputValue, 
            llmId: llm.id, 
            temperature: panel.temperature, 
            topP: panel.topP, 
            maxNewTokens: panel.maxTokens, 
            customPrompt: panel.customPrompt

          }

          console.log("Payload : ", payload)
          return askArena(payload);
        })
      );

      setPanels(prev => 
        prev.map((panel,idx) => ({
        ...prev,
        messages: [
            ...panel.messages,
            {role: "llm", content: responses[idx]},
        ],
        }))
        
      );

      const newIds = responses
        .map(res => res.conversation?.id)
        .filter(id => id !== undefined && id !== null);

      setCreatedConversationIds(prev => {
        const updated = [...new Set([...prev, ...newIds])];
        createdConversationIdsRef.current = updated;
        return updated;
      });
    } catch (err) {
      setPanels(prev =>
        prev.map(panel => ({
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
    const defaultModel = models[panels.length % models.length]?.name || "";
    
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
      <HeaderBar
            initialTemperature={settings.temperature}
            initialTopP={settings.topP}
            initialMaxTokens={settings.maxTokens}
            onApply={(newSettings) => setSettings(newSettings)}
            onCustomizePrompt={() => setShowPromptModal(true)}
          />
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
              onSend={handleAsk}
              backgroundClass="bg-emerald-900"
              disabled={loading}
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