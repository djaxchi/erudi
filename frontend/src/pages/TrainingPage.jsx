import React, { useState } from "react";
import Sidebar from "../components/Sidebar";   
import GradientBox  from "../components/GradientBox";
import {
  ChevronDown,
  RefreshCcw,
  Check,
  Folder,
} from "lucide-react";

function InfoRow({ label, children }) {
  return (
    <div className="flex justify-between items-center py-1">
      <span className="text-gray-200 font-medium w-1/2">{label}</span>
      <div className="w-1/2 flex justify-end text-white">{children}</div>
    </div>
  );
}

function DatasetCard() {
  const [type, setType] = useState("Textuel");
  const [dataPath, setDataPath] = useState("/AppData/DataStorage…");

  return (
    <div className="flex-1 bg-[#2B2B2B] rounded-2xl p-8 text-white flex flex-col gap-6 shadow-lg">
      <div>
        <h3 className="text-xl font-bold mb-4">Choose Your Dataset Type</h3>
        <div className="relative inline-block w-48">
          <select
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="appearance-none w-full bg-transparent border border-gray-400 rounded-full px-4 py-2 pr-8 text-sm focus:outline-none"
          >
            <option value="Textuel">Textuel</option>
            <option value="Images">Images</option>
            <option value="Audio">Audio</option>
          </select>
          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-300 pointer-events-none" />
        </div>
      </div>

      <div>
        <h3 className="text-xl font-bold mb-2">Data Path</h3>
        <input
          value={dataPath}
          onChange={(e) => setDataPath(e.target.value)}
          className="w-full bg-transparent border border-gray-400 rounded-full px-4 py-2 text-sm focus:outline-none placeholder-gray-400"
          placeholder="/AppData/DataStorage…"
        />
      </div>

      <div className="flex-1 flex items-end">
        <button className="w-40 mx-auto py-3 rounded-full border border-emerald-400 text-emerald-400 font-semibold hover:bg-emerald-400/10 transition">
          Train
        </button>
      </div>
    </div>
  );
}

function DragDropArea() {
  return (
    <GradientBox className="flex-1 flex items-center justify-center h-full min-h-[230px]">
      <div className="flex flex-col items-center text-white/80 gap-4">
        <Folder className="w-14 h-14" />
        <p className="text-lg">Drag and Drop</p>
      </div>
    </GradientBox>
  );
}

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
          <DragDropArea />
        </div>
      </main>
    </div>
  );
}
