import React from "react";
import Sidebar from "../components/Sidebar";
import ModelCollapsibleSection from "../components/ModelCollapsibleSection";
import TrainNewModelCard from "../components/TrainNewModelCard";

export default function LandingPage() {
  return (
    <div className="flex h-screen">
      {/* Left mini sidebar */}
      <Sidebar />

      {/* Main sidebar */}
      <aside className="w-[30%] sm:w-[35%] xl:w-[25%]  bg-[#272727] text-white flex flex-col p-6 space-y-6">
        <h1 className="text-3xl font-bold">Models</h1>
        <ModelCollapsibleSection title="Local Models" />
        <ModelCollapsibleSection title="Available Models" />
      </aside>

      {/* Main content */}
      <main className="flex-1 bg-[#071b18] relative overflow-auto">
        <TrainNewModelCard />
      </main>
    </div>
  );
}