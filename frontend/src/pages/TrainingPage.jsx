import React, { useState } from "react";
import Sidebar from "../components/Sidebar";   
import GradientBox  from "../components/GradientBox";
import {
  ChevronDown,
  RefreshCcw,
  Check,
} from "lucide-react";
import InfoRow from "../components/InfoRow";
import DatasetCard from "../components/DatasetCard";
import DragDropArea from "../components/DragDropArea";

export default function TrainingPage() {
  return (
    <div className="flex h-screen bg-[#071b18]">
      <Sidebar />

      <main className="flex-1 p-8 space-y-8 overflow-auto">
        {/* Top Row */}
        <div className="flex gap-8">
          {/* System Info Card */}
          <GradientBox className="flex-1 min-w-[300px]">
            <InfoRow label="Storage Path :">
              <div className="bg-gray-800/60 rounded-full px-4 py-1 text-sm truncate max-w-[180px]">
                /AppData/ModelStorage…
              </div>
            </InfoRow>
            <InfoRow label="Available Storage :">32 GB</InfoRow>
            <InfoRow label="Available CPU :">AMD Ryzen 5</InfoRow>
            <InfoRow label="Available GPU :">NVIDIA GEFORCE 940M</InfoRow>
            <InfoRow label="Cuda Installed :">
              <div className="flex items-center gap-2">
                <div className="bg-gray-800/60 rounded-full px-4 py-1 text-sm truncate max-w-[160px]">
                  /AppData/CudaPack…
                </div>
                <Check className="w-5 h-5 text-emerald-400" />
              </div>
            </InfoRow>
          </GradientBox>

          {/* Model List Card */}
          <div className="flex-1 min-w-[300px] bg-[#2B2B2B] rounded-2xl p-8 text-white shadow-lg flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h3 className="text-2xl font-bold">Model Name</h3>
              <input
                className="bg-transparent border border-gray-400 rounded-full px-4 py-1 text-sm w-56 truncate focus:outline-none"
                placeholder="/AppData/DataStorage…"
              />
            </div>

            <div className="flex items-center justify-between mt-4">
              <div className="flex items-center gap-2">
                <ChevronDown className="w-4 h-4" />
                <h4 className="text-lg font-semibold">Available Models</h4>
              </div>
              <RefreshCcw className="w-4 h-4 cursor-pointer hover:rotate-90 transition" />
            </div>

            <div className="bg-gray-800/50 rounded-lg p-4 overflow-y-auto h-40 mt-2">
              <ul className="space-y-2 text-emerald-300 text-sm">
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
