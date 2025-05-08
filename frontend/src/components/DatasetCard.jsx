import React, { useState } from "react";
import { ChevronDown } from "lucide-react";



export default function DatasetCard() {
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