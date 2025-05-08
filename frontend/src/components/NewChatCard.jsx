import React from "react";
import GradientBox from "./GradientBox";
import { SendHorizontal } from "lucide-react";

export default function NewChatCard() {
    return (
      <GradientBox className="w-[700px] max-w-full">
        <div className="space-y-6">
          {/* header row */}
          <div className="flex items-center gap-4 flex-wrap">
            <h2 className="text-white text-3xl font-bold">Chat with</h2>
            <select className="px-4 py-1 rounded-full border border-emerald-400 bg-transparent text-white focus:outline-none text-sm">
              <option className="text-black">Models</option>
              {/* options dynamiques ici */}
            </select>
          </div>
  
          {/* question input */}
          <div className="flex items-center bg-gray-900/80 rounded-full overflow-hidden">
            <input
              type="text"
              placeholder="Ask a question…"
              className="flex-1 bg-transparent font-thin px-8 py-4 border-0 text-white placeholder-white focus:outline-none"
            />
            <button className="pr-6">
              <SendHorizontal className="w-6 h-6 text-white" />
            </button>
          </div>
        </div>
      </GradientBox>
    );
  }