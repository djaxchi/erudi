import React from "react";
import { Plus } from "lucide-react";
import { useNavigate } from "react-router-dom";
import GradientBox from "./GradientBox";

export default function TrainNewModelCard() {
  const navigate = useNavigate();
  const handleAttachKnowledgeBase = () => navigate("/erudi/attach_knowledge_base");

  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center">
      {/* wrapper div receives the click */}
      <div
        onClick={handleAttachKnowledgeBase}
        className="cursor-pointer w-56 h-56 flex items-center justify-center"
      >
        <GradientBox 
          className="w-full h-full" 
          contentClassName="flex items-center justify-center h-full"
        >
          <Plus className="w-20 h-20 text-white" />
        </GradientBox>
      </div>

      <p className="mt-4 text-white text-lg">Attach Knowledge Base</p>
    </div>
  );
}
