import React from "react";
import { Plus } from "lucide-react";
import { useNavigate } from "react-router-dom";
import GradientBox from "./GradientBox";          // ⬅️  ajoute l'import

export default function TrainNewModelCard() {
  const navigate = useNavigate();
  const handleTrainNewModel = () => navigate("/main_window/new-training");

  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center">
      {/* gradient fond + clic */}
      <GradientBox
        className="cursor-pointer w-56 h-56 flex items-center justify-center"
        onClick={handleTrainNewModel}
      >
        <Plus className="w-20 h-20 text-white" />
      </GradientBox>

      <p className="mt-4 text-white text-lg">Train new model</p>
    </div>
  );
}
