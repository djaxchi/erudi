import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, AlertTriangle } from "lucide-react";

export default function ErrorModal({ errorMessage, onClose }) {
  return (
    <AnimatePresence>
      {errorMessage && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[9999] p-4"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            className="relative w-full max-w-md"
          >
            <div
              className={[
                "relative w-full rounded-[26px] overflow-hidden",
                "border border-white/10",
                "bg-[rgba(22,40,36,0.45)] backdrop-blur-[18px] saturate-[1.4]",
                "shadow-[0_8px_30px_-4px_rgba(0,0,0,0.45),0_2px_6px_-1px_rgba(0,0,0,0.4),inset_0_1px_0_rgba(255,255,255,0.06)]",
              ].join(" ")}
            >
              <div
                aria-hidden
                className="absolute inset-0 pointer-events-none rounded-[26px] mix-blend-overlay"
                style={{
                  background:
                    "linear-gradient(to bottom, rgba(255,255,255,0.18), rgba(255,255,255,0) 40%)",
                }}
              />
              <div
                aria-hidden
                className="absolute inset-0 pointer-events-none rounded-[26px] opacity-35 mix-blend-overlay"
                style={{
                  backgroundImage:
                    'url("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAABVUlEQVRYR+2WvQ3CMAyFPxF0AB1AB1ABN0AHcAF0gA3QATpN0lInyY5kUVqSk4TsSIv8P2RNFpBf6h8Bi5TBSW0AVbAAmwBpjqgA3wD1fYwHzwFR3QAdwDvl7T2JQG4C7gA/H8LwAVtFznGKnyD20PnKQqa5wzwwM3Vl8r9mQwZP4RFL9XPs35SHJxKcVd5jTwK9K1u4ErfJUF2XblI8g4BtMSSYlLQF41f+WAbc42t7CM6ikgs6Y2oT64y8G8BuEorQFrirN4i0cK4erQblIDmI+F6kAD0fYp2RchEot1Hc6S/T/lNa8T1nDjMDPxgg7wM8S+P8Gn8UH2Piu0mV9K/VLBbq+508Quy_ngGBrhV98yYzeBdOL4SqyGoccEqbE6+ZjKlj19qCxgY6N8lH3dy5zvY1/drdEw2d+uHMDuHwrK0Yas7PwAxRxmKJl0VokAAAAASUVORK5CYII=")',
                  backgroundSize: "200px 200px",
                }}
              />

              {/* Content */}
              <div className="relative z-10 p-6">
                {/* Header */}
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-red-500/20 flex items-center justify-center">
                      <AlertTriangle className="w-4 h-4 text-red-400" />
                    </div>
                    <h2 className="text-xl font-semibold tracking-tight text-[#F2F7F4]">
                      Error
                    </h2>
                  </div>
                  <button
                    onClick={onClose}
                    className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 text-gray-300 hover:text-gray-100 transition"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                {/* Error message */}
                <div className="mb-6">
                  <div className="bg-red-500/10 border border-red-400/20 rounded-2xl p-4">
                    <p className="text-sm text-red-200">{errorMessage}</p>
                  </div>
                </div>

                {/* Button */}
                <div className="flex items-center justify-end">
                  <button
                    onClick={onClose}
                    className={[
                      "rounded-full px-5 py-2 text-sm font-semibold",
                      "bg-emerald-500 hover:bg-emerald-600 text-[#0f2f25]",
                      "border border-white/20 shadow",
                      "transition active:scale-95",
                    ].join(" ")}
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
