import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, ChevronUp } from "lucide-react";
import GradientBox from "./GradientBox";

/**
 * Props:
 *   initialTemperature: number
 *   initialTopP: number
 *   initialMaxTokens: number
 *   onApply: (settings: { temperature: number; topP: number; maxTokens: number }) => void
 *   onCustomizePrompt: () => void
 */
export default function HeaderBar({
  initialTemperature,
  initialTopP,
  initialMaxTokens,
  onApply,
  onCustomizePrompt,
}) {
  const [isOpen, setIsOpen] = useState(false);

  // Local copies of your settings
  const [temperature, setTemperature] = useState(initialTemperature);
  const [topP, setTopP]           = useState(initialTopP);
  const [maxTokens, setMaxTokens] = useState(initialMaxTokens);

  const handleApply = () => {
    onApply({ temperature, topP, maxTokens });
    setIsOpen(false); // optionally collapse after applying
  };

  return (
    <div className="bg-[#143529] text-white rounded-2xl px-6 py-3 w-full max-w-4xl mx-6 mt-6 shadow-lg ">
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
            className="overflow-hidden mt-4 rounded-xl"
          >
            {/* ───── Zones de paramètres LLM + bouton Appliquer ───── */}
            <GradientBox className="flex flex-row justify-center items-center p-4 mb-4">
              <div className="flex flex-row justify-center items-center items-end space-x-4">
                <div className="flex flex-col gap-1">
                  <label className="block text-white text-sm">
                    Créativité (Température)
                  </label>
                  <input
                    type="range"
                    step="0.01"
                    min="0"
                    max="1"
                    value={temperature}
                    onChange={(e) =>
                      setTemperature(parseFloat(e.target.value))
                    }
                    className="my-1 w-40 h-1
                              bg-gray-700/50 rounded-full
                              appearance-none
                              accent-emerald-400
                              hover:accent-emerald-500
                              focus:outline-none"
                  />
                  <label className="block text-white text-sm">
                    Diversité (Top-P)
                  </label>
                  <input
                    type="range"
                    step="0.1"
                    min="0"
                    max="1"
                    value={topP}
                    onChange={(e) => setTopP(parseFloat(e.target.value))}
                    className="my-1 w-40 h-1
                              bg-gray-700/50 rounded-full
                              appearance-none
                              accent-emerald-400
                              hover:accent-emerald-500
                              focus:outline-none"
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-white text-sm font-medium">
                    Max Tokens
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="2000"
                    value={maxTokens}
                    onChange={(e) => setMaxTokens(parseInt(e.target.value, 10))}
                    className="
                      w-24
                      bg-transparent
                      border border-emerald-400/40
                      rounded-full
                      px-4 py-2
                      text-sm text-white
                      focus:outline-none focus:border-emerald-400 focus:ring-0
                      transition
                    "
                  />
                </div>

                <button
                  onClick={onCustomizePrompt}
                  className="bg-emerald-600/60 hover:bg-emerald-700/50 transition-colors text-white py-2 px-4 rounded-xl"
                >
                  Personnalise prompt
                </button>
              </div>


            </GradientBox>
            <div className="flex justify-center mt-4">
                <button
                  onClick={handleApply}
                  className="
                    bg-emerald-500
                    text-white
                    font-semibold
                    px-6 py-2
                    rounded-full
                    hover:bg-emerald-600
                    focus:outline-none focus:ring-2 focus:ring-emerald-400
                  transition-colors">
                  Apply
                </button>
              </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}



