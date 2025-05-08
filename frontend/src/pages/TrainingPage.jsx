import React, { useState } from "react";
import Sidebar from "../components/Sidebar";   
import GradientBox  from "../components/GradientBox";
import {
  RefreshCcw,
  Check,
    X,
} from "lucide-react";
import InfoRow from "../components/InfoRow";
import DatasetCard from "../components/DatasetCard";

export default function TrainingPage() {
    const [cudaPath, setCudaPath] = useState("");
  return (
    <div className="flex h-screen bg-[#071b18]">
      <Sidebar />

      <main className="flex-1 p-8 space-y-8 overflow-auto">
        {/* Top Row */}
        <div className="flex gap-8">
          {/* System Info Card */}
          <GradientBox className="flex-1 min-w-[300px]">
            <InfoRow label="Storage Path :">
            <input
                className="bg-gray-800/60 border border-transparent rounded-full px-4 py-1 placeholder-white text-sm truncate max-w-[180px] focus:border-emerald-400/50 focus:ring-0 focus:outline-none "
                placeholder="/AppData/ModelStorage…"
              />
            </InfoRow>
            <InfoRow label="Available Storage :">32 GB</InfoRow>
            <InfoRow label="Available RAM :">8 GB</InfoRow>
            <InfoRow label="Available CPU :">AMD Ryzen 5</InfoRow>
            <InfoRow label="Available GPU :">NVIDIA GEFORCE 940M</InfoRow>
            <InfoRow label="Cuda Installed :">
              <div className="flex items-center gap-2">
                <input
                  value={cudaPath}
                  onChange={(e) => setCudaPath(e.target.value)}
                  className="bg-gray-800/60 border border-transparent rounded-full px-4 py-1 placeholder-white text-sm truncate max-w-[180px] focus:border-emerald-400/50 focus:ring-0 focus:outline-none"
                  placeholder="Click to specify path"
                />
                {cudaPath ? (
                  <Check className="w-5 h-5 text-emerald-400" />
                ) : (
                  <X className="w-5 h-5 text-red-500" />
                )}
              </div>
            </InfoRow>
          </GradientBox>

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
