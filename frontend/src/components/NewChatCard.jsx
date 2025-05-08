import React, { useEffect, useState } from "react";
import GradientBox from "./GradientBox";
import { SendHorizontal } from "lucide-react";

export default function NewChatCard() {
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState("");

  useEffect(() => {
    fetch("http://127.0.0.1:8000/main_window/llms/local")
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setModels(data);
          setSelectedModel(data[0].name); // Premier modèle par défaut
        }
      })
      .catch((err) => {
        console.error("Erreur lors du fetch des modèles:", err);
      });
  }, []);

  if (models.length === 0) {
    return (
      <GradientBox className="w-[700px] max-w-full">
        <div className="text-white text-center py-10">
          Aucun modèle local disponible. Veuillez en ajouter un.
        </div>
      </GradientBox>
    );
  }

  return (
    <GradientBox className="w-[700px] max-w-full">
      <div className="space-y-6">
        {/* header row */}
        <div className="flex items-center gap-2 flex-wrap">
          <h2 className="text-white text-3xl font-bold whitespace-nowrap">Chat with</h2>
          <div className="relative">
            <select
              className="appearance-none pr-8 pl-4 py-1 rounded-full border border-emerald-400 bg-transparent text-white focus:outline-none text-sm"
              onChange={(e) => setSelectedModel(e.target.value)}
              value={selectedModel}
            >
              {models.map((model) => (
                <option key={model.id} value={model.name} className="text-black">
                  {model.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* question input */}
        <div className="flex items-center bg-gray-900/80 rounded-full overflow-hidden">
          <input
            type="text"
            placeholder="Ask a question…"
            className="flex-1 bg-transparent font-thin px-8 py-4 border-0 text-white placeholder-white focus:outline-none"
          />
          <button className="pr-6">
            <SendHorizontal className="w-6 h-6 text-white" />
          </button>
        </div>
      </div>
    </GradientBox>
  );
}
