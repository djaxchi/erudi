import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, ChevronUp } from "lucide-react";

export default function HeaderBar() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="bg-[#143529] text-white rounded-2xl px-6 py-3 w-full max-w-3xl mx-auto mt-6 shadow-lg">
      {/* ─── TOP ROW ─────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div className="font-semibold text-lg">Chat with</div>
        <div className="flex items-center space-x-2">
          <select className="bg-transparent text-white border-none focus:outline-none">
            <option className="text-black">Mistral-7b-AO</option>
          </select>
          <button onClick={() => setIsOpen((v) => !v)}>
            {isOpen ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
          </button>
        </div>
      </div>

      {/* ─── COLLAPSIBLE PANEL ──────────────────────────────────────────────── */}
      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            key="controls"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ type: "tween", duration: 0.2 }}
            className="overflow-hidden mt-4"
          >
            <div className="space-y-4">
              {/** Creativity Slider **/}
              <div className="flex items-center justify-between">
                <span className="text-sm">Creativity:</span>
                <input
                  type="range"
                  min="0"
                  max="100"
                  defaultValue="50"
                  className="w-2/3 h-1 rounded-lg bg-[#2a5e46]"
                  // accentColor sets thumb + filled portion
                  style={{ accentColor: "#5A67D8" }}
                />
              </div>

              {/** Diversity Slider **/}
              <div className="flex items-center justify-between">
                <span className="text-sm">Diversity:</span>
                <input
                  type="range"
                  min="0"
                  max="100"
                  defaultValue="50"
                  className="w-2/3 h-1 rounded-lg bg-[#2a5e46]"
                  style={{ accentColor: "#5A67D8" }}
                />
              </div>

              {/** Max Response Length **/}
              <div className="flex items-center justify-between">
                <span className="text-sm">Max Response Length:</span>
                <span className="bg-black text-white px-2 py-1 rounded-md text-xs">
                  3074
                </span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}


