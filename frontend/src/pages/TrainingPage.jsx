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
    storage_path:   "/Path/To/Storage",
    disk_available: "fetching…",
    cpu_model:      "fetching…",
    gpu_model:      "fetching…",
    cuda_installed: { path: "", ok: false },
  });

  useEffect(() => {
    fetch(`${API_BASE}/hardware`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        setHw({
          storage_path:   data.storage_path ?? "/Path/To/Storage",
          ram_available:  `${data.available_ram_gb} GB`,
          disk_available: `${data.disk_available_gb} GB`,
          cpu_model:      data.cpu_model,
          gpu_model:      data.gpu_model ?? "No GPU detected",
          cuda_installed: {
            path: data.cuda_path  ?? "Path/To/Cuda",
            ok:   data.cuda_installed
          },
        });
      })
      .catch(err => {
        console.error("Erreur hardware:", err);
        // on laisse les valeurs par défaut en UI
      });
  }, []);

  const [cudaPath, setCudaPath] = useState(hw.cuda_installed.path);

  return (
    <div className="flex h-screen bg-[#071b18]">
      <Sidebar />

      <main className="flex-1 p-8 space-y-8 overflow-auto">
        {/* Top Row */}
        <div className="flex gap-8">
          {/* System Info Card */}
          <HardwareInfo hw={hw} />
          {/* Model List Card */}
          <div className="flex-1 min-w-[300px] bg-[#2B2B2B] rounded-2xl p-8 text-white shadow-lg flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h3 className="text-2xl font-bold">Model Name</h3>
              <input
                className="bg-transparent border border-gray-400 rounded-full px-4 py-1 text-sm w-56 truncate placeholder-white/40 focus:border-emerald-400/50 focus:ring-0 focus:outline-none"
                placeholder="/AppData/DataStorage…"
              />
            </div>

            <div className="flex items-center justify-between mt-4">
              <div className="flex items-center gap-2">
                <h4 className="text-lg font-semibold">Available Models</h4>
              </div>
              <RefreshCcw className="w-4 h-4 cursor-pointer hover:rotate-90 transition" />
            </div>

            <div className="bg-gray-800/50 rounded-lg p-4 overflow-y-auto h-40 mt-2 shadow-lg">
              <ul className="space-y-2 text-white/80 text-sm">
                <li>Mistral‑7b</li>
                <li>Llama‑3</li>
                <li>LoRa</li>
                <li>TinyLlama</li>
                {/* … */}
              </ul>
            </div>
          </div>
        </div>

        {/* Bottom Row */}
        <div className="flex gap-8">
          <DatasetCard />
        </div>
      </main>
    </div>
  );
}
