import React, { useEffect, useState } from "react";
import Sidebar from "../components/Sidebar";
import {
  RefreshCcw,
} from "lucide-react";
import DatasetCard from "../components/DatasetCard";
import HardwareInfo from "../components/HardwareInfo";

const API_BASE = "http://localhost:8000";

export default function TrainingPage() {
  const [hw, setHw] = useState({
    storage_path: "/Path/To/Storage",
    disk_available: "fetching…",
    cpu_model: "fetching…",
    gpu_model: "fetching…",
    cuda_installed: { path: "", ok: false },
  });

  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState(null);
  const [modelName, setModelName] = useState("");


  const fetchModels = () => {
    fetch(`${API_BASE}/main_window/llms/local`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        console.log("Fetched models:", data, "Count:", data ? data.length : 0);
        setModels(data || []);
      })
      .catch(err => {
        console.error("Erreur models:", err);
        setModels([]);
      });
  };

  useEffect(() => {
    fetch(`${API_BASE}/hardware`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        setHw({
          storage_path: data.storage_path ?? "/Path/To/Storage",
          ram_available: `${data.available_ram_gb} GB`,
          disk_available: `${data.disk_available_gb} GB`,
          cpu_model: data.cpu_model,
          gpu_model: data.gpu_model ?? "No GPU detected",
          cuda_installed: {
            path: data.cuda_path ?? "Path/To/Cuda",
            ok: data.cuda_installed
          },
        });
      })
      .catch(err => {
        console.error("Erreur hardware:", err);
      });
    fetchModels();
  }, []);

  const [cudaPath, setCudaPath] = useState(hw.cuda_installed.path);

  return (
    <div className="flex h-screen bg-[#071b18]">
      <Sidebar />
      
      <main className="flex-1 p-4 md:p-8 space-y-8 overflow-auto custom-scroll">
        {/* Top Section: Hardware + Model Info */}
        <div className="flex flex-col lg:flex-row 2xl:h-[40%] gap-8">
          <HardwareInfo hw={hw} />

          <div className="flex-1 min-w-[300px] bg-[#2B2B2B] rounded-2xl p-6 text-white shadow-lg flex flex-col gap-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <h3 className="text-xl md:text-2xl font-bold">Model Name</h3>
              <input
                className="bg-transparent border border-gray-400 rounded-full px-4 py-1 text-sm w-full sm:w-56 truncate placeholder-white/40 focus:border-emerald-400/50 focus:ring-0 focus:outline-none"
                placeholder={selectedModel ? "Name your new model!" : "Select a model..."}
                value={modelName}
                onChange={e => setModelName(e.target.value)}
              />
            </div>

            <div className="flex items-center justify-between mt-4">
              <div className="flex items-center gap-2">
                <h4 className="text-lg font-semibold">Available Models</h4>
              </div>
              <RefreshCcw
                className="w-4 h-4 cursor-pointer hover:rotate-90 transition"
                onClick={fetchModels}
                title="Refresh models"
              />
            </div>

            <div className="bg-gray-800/50 rounded-lg p-4 overflow-y-auto max-h-40 mt-2 shadow-lg">
              {models.length === 0 ? (
                <div className="text-white/60 text-sm">No local LLMs found.</div>
              ) : (
                <ul className="space-y-2 text-white/80 text-sm">
                  {models.map(model => (
                    <li key={model.id} className="flex items-center gap-2">
                      <input
                        type="radio"
                        name="local-llm"
                        value={model.id}
                        checked={selectedModel === model.id}
                        onChange={() => setSelectedModel(model.id)}
                        className="accent-emerald-400"
                      />
                      <span>{model.name}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>

        {/* Bottom Section: Dataset */}
        <div className="flex flex-col lg:h-[50%] 2xl:h-[56%] gap-8">
          <DatasetCard selectedModel={selectedModel} modelName={modelName} />
        </div>
      </main>

    </div>
  );
}
