import React from "react";
import { Plus } from "lucide-react";
import { useNavigate } from "react-router-dom";

export default function TrainNewModelCard() {
  const navigate = useNavigate();
  const handleTrainNewModel = () => navigate("/main_window/new-training");

  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center">
    <div
      className="cursor-pointer w-56 h-56 rounded-xl bg-white/5 backdrop-blur-md shadow-xl flex items-center justify-center hover:backdrop-blur-lg transition"
      onClick={handleTrainNewModel}
    >
      <Plus className="w-20 h-20 text-white" />
    </div>
    <p className="mt-4 text-white text-lg">Train new model</p>
  </div>
  );
}