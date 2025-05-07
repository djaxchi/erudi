import React from "react";
import Sidebar from "../components/Sidebar/Sidebar";
import CollapsibleSection from "../components/CollapsibleSection";
import TrainNewModelCard from "../components/TrainNewModelCard";

export default function LandingPage() {
  return (
    <div className="flex h-screen">
      {/* Left mini sidebar */}
      <Sidebar />

      {/* Main sidebar */}
      <aside className="w-80 bg-[#272727] flex flex-col">
        <CollapsibleSection title="Local Models"/>
        <CollapsibleSection title="Available Models"/>
      </aside>

      {/* Main content */}
      <main className="flex-1 bg-[#071b18] relative overflow-auto">
        <TrainNewModelCard />
      </main>
    </div>
  );
}