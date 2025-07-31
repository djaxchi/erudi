import React, { useEffect, useState } from "react";
import Sidebar from "../components/Sidebar";
import DatasetCard from "../components/DatasetCard";
import HardwareInfo from "../components/HardwareInfo";
import ModelLibrary from "../components/ModelLibrary";

const API_BASE = "http://localhost:8000";

export default function TrainingPage() {
  const [hw, setHw] = useState({
    storage_path: "soon...",
    disk_available: "fetching…",
    cpu_model: "fetching…",
    gpu_model: "fetching…",
    gpu_vram_total: "fetching…",
    gpu_vram_free: "fetching…",
    ram_available: "fetching…",
    total_ram_gb: "fetching…",
    cuda_installed: false,
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
    /*fetch(`${API_BASE}/hardware/training`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        setHw({
          storage_path: data.storage_path ?? "coming soon...",
          ram_available: `${data.available_ram_gb} GB`,
          total_ram_gb: `${data.total_ram_gb} GB`,
          disk_available: `${data.disk_available_gb} GB`,
          cpu_model: data.cpu_model,
          gpu_model: data.gpu_model ?? "No GPU detected",
          gpu_vram_total: data.gpu_vram_total_gb ? `${data.gpu_vram_total_gb/1000} GB` : "No GPU detected",
          gpu_vram_free: data.gpu_vram_free_gb ? `${data.gpu_vram_free_gb/1000} GB` : "No GPU detected",
          cuda_installed: data.cuda_installed ? "✅" : "❌",
          global_finetuning_score: data.global_finetuning_score ? `${data.global_finetuning_score}/100` : "N/A",
          global_finetuning_label: data.global_finetuning_label ? data.global_finetuning_label : "N/A",
        });
      })
      .catch(err => {
        console.error("Erreur hardware:", err);
        setHw({
          storage_path: "Error fetching",
          ram_available: "Error fetching",
          disk_available: "Error fetching",
          cpu_model: "Error fetching",
          gpu_model: "Error fetching",
          gpu_vram_total: "Error fetching",
          gpu_vram_free: "Error fetching",
          cuda_installed: "Error fetching",
          global_finetuning_score: "Error fetching",
          global_finetuning_label: "Error fetching",
        });
      });*/
    fetchModels();
  }, []);

  // Handle model selection from ModelLibrary
  const handleModelSelect = (modelId) => {
    setSelectedModel(modelId);
  };

  // Handle model name change from ModelLibrary
  const handleModelNameChange = (name) => {
    setModelName(name);
  };

  return (
    <div className="flex h-screen bg-[#071b18]">
      <Sidebar />
      
      <main className="flex-1 p-4 md:p-8 space-y-8 overflow-auto custom-scroll">
        {/* Top Section: Hardware + Model Library */}
        <div className="flex flex-col lg:flex-row 2xl:h-[40%] gap-8">
          <HardwareInfo hw={hw} />
          
          <ModelLibrary 
            models={models}
            selectedModel={selectedModel}
            modelName={modelName}
            onModelSelect={handleModelSelect}
            onModelNameChange={handleModelNameChange}
            onRefresh={fetchModels}
          />
        </div>

        {/* Bottom Section: Dataset */}
        <div className="flex flex-col lg:h-[50%] 2xl:h-[56%] gap-8">
          <DatasetCard selectedModel={selectedModel} modelName={modelName} />
        </div>
      </main>
    </div>
  );
}
