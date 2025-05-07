import React, { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  MessageSquare,
  Brain,
  SendHorizontal,
    Plus,
    RefreshCcw,
    Cog,
} from "lucide-react";

function SidebarIcon({ children, active }) {
    return (
      <div
        className={`w-full flex justify-center items-center py-4 ${
          active ? "border-l-4 border-green-500" : ""
        }`}
      >
        {children}
      </div>
    );
  }

function CollapsibleSection({ title }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="text-gray-200">
      <div
        className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-gray-700/30"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center gap-2">
          {open ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
          <span className="font-semibold">{title}</span>
        </div>

        <div className="flex gap-3">
          <Cog className="w-4 h-4 hover:opacity-70" />
          <RefreshCcw className="w-4 h-4 hover:opacity-70" />
          <Plus className="w-4 h-4 hover:opacity-70" />
        </div>
      </div>

      {open && (
        <p className="px-10 py-2 text-sm italic text-gray-500">Nothing here…</p>
      )}
    </div>
  );
}

export function GradientBox({ children, className = "" }) {
    return (
      <div className={`relative rounded-2xl overflow-hidden shadow-xl ${className}`}>
        {/* gradient layer (11 % d'opacité) */}
        <div
          className="absolute inset-0 opacity-[11%]"
          style={{
            background:
              "linear-gradient(135deg, rgba(217, 217, 217, 1) 0%, rgba(217, 217, 217, 0.26) 26%, rgba(0, 204, 133, 1) 100%)",
          }}
        />
  
        {/* grain overlay */}
        <div
          className="absolute inset-0 mix-blend-overlay pointer-events-none"
        />
  
        {/* content retains full opacity */}
        <div className="relative z-10 p-8">{children}</div>
      </div>
    );
  }
  
  /**
   * Specific card that matches the second mock‑up (Chat with → input).
   */
  export function ChatWithCard() {
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


export default function ChatPage() {
  return (
    <div className="flex h-screen">
      {/* mini sidebar */}
      <div className="w-16 bg-[#121212] flex flex-col items-center">
        <SidebarIcon>
          <Brain className="w-6 h-6 text-gray-400" />
        </SidebarIcon>
        <SidebarIcon active>
          <MessageSquare className="w-6 h-6 text-green-400" />
        </SidebarIcon>
      </div>

      {/* main sidebar */}
      <aside className="w-80 bg-[#272727] text-white flex flex-col p-6 space-y-6">
        <h1 className="text-3xl font-bold">History</h1>
        <CollapsibleSection title="Hot Chats" />
        <CollapsibleSection title="Previous Chats" />
      </aside>

      {/* content */}
      <main className="flex-1 bg-[#071b18] flex items-center justify-center relative overflow-auto">
        <ChatWithCard />
      </main>
    </div>
  );
}
