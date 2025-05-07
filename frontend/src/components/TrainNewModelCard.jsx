import React from "react";
import { Plus } from "lucide-react";

export default function TrainNewModelCard() {
  const handleTrainNewModel = async () => {
    try {
      const response = await fetch("http://127.0.0.1:8000/main_window/train-new-model", {
        method: "GET",
      });
      const data = await response.json();
      console.log("Response from Train New Model:", data.message);
      alert(`Response: ${data.message}`); // Optional: Show a message to the user
    } catch (error) {
      console.error("Error calling Train New Model endpoint:", error);
      alert("Failed to call Train New Model endpoint.");
    }
  };

  return (
    <div
      className="absolute inset-0 flex flex-col items-center justify-center "
    >
      <div className="cursor-pointer w-56 h-56 rounded-xl bg-white/5 backdrop-blur-md shadow-xl flex items-center justify-center hover:backdrop-blur-lg transition" onClick={handleTrainNewModel}>
        <Plus className="w-20 h-20 text-white" />
      </div>
      <p className="mt-4 text-white text-lg">Train new model</p>
    </div>
  );
}