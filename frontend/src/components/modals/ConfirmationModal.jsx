import React from "react";
import { motion, AnimatePresence } from "framer-motion";

/**
 * Props:
 * - text: string to display in question
 * - onConfirm: () => void
 * - onCancel: () => void
 * - isOpen: boolean
 * - isFineTuning: boolean (optional)
 */
export default function ConfirmationModal({
  text,
  isOpen,
  onConfirm,
  onCancel,
  isFineTuning = false,
}) {
  return (
    <AnimatePresence>
      {isOpen && (
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
                <h2 className="text-xl font-semibold tracking-tight text-[#F2F7F4] mb-2">
                  {isFineTuning ? (
                    <>
                      Are you sure you want to start training{" "}
                      <span className="font-bold text-emerald-400">{text}</span>
                      ?
                    </>
                  ) : (
                    <>
                      Are you sure you want to download{" "}
                      <span className="font-bold text-emerald-400">{text}</span>
                      ?
                    </>
                  )}
                </h2>
                <p className="text-sm text-gray-300/80 mb-6">
                  {isFineTuning
                    ? "This will start the fine-tuning process."
                    : "It will be installed locally on your system."}
                </p>

                <div className="flex items-center justify-end gap-3">
                  <button
                    onClick={onCancel}
                    className={[
                      "rounded-full px-5 py-2 text-sm font-semibold",
                      "bg-white/10 hover:bg-white/15 text-gray-100",
                      "border border-white/20 backdrop-blur-sm shadow-sm",
                      "transition active:scale-95",
                    ].join(" ")}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={onConfirm}
                    className={[
                      "rounded-full px-5 py-2 text-sm font-semibold",
                      "bg-emerald-500 hover:bg-emerald-600 text-[#0f2f25]",
                      "border border-white/20 shadow",
                      "transition active:scale-95",
                    ].join(" ")}
                  >
                    {isFineTuning ? "Start Training" : "Download"}
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
