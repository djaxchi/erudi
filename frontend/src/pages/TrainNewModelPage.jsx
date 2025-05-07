import React from "react";
import { Plus } from "lucide-react";

export default function TrainNewModelCard() {
  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center">
      <div className="w-56 h-56 rounded-xl bg-white/5 backdrop-blur-md shadow-xl flex items-center justify-center hover:backdrop-blur-lg transition">
        <Plus className="w-20 h-20 text-white" />
      </div>
      <p className="mt-4 text-white text-lg">Train new model</p>
    </div>
  );
}