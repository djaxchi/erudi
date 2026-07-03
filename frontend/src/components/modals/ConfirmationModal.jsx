import React from "react";
import PropTypes from "prop-types";
import { motion, AnimatePresence } from "framer-motion";
import grainOverlay from "../../assets/images/textures/grain-overlay.png";

/**
 * Props:
 * - text: string to display in question
 * - onConfirm: () => void
 * - onCancel: () => void
 * - isOpen: boolean
 */
export default function ConfirmationModal({ text, isOpen, onConfirm, onCancel }) {
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
                  backgroundImage: `url("${grainOverlay}")`,
                  backgroundSize: "200px 200px",
                }}
              />

              {/* Content */}
              <div className="relative z-10 p-6">
                <h2 className="text-xl font-semibold tracking-tight text-[#F2F7F4] mb-2">
                  Are you sure you want to download{" "}
                  <span className="font-bold text-emerald-400">{text}</span>?
                </h2>
                <p className="text-sm text-gray-300/80 mb-6">
                  It will be installed locally on your system.
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
                    Download
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

ConfirmationModal.propTypes = {
  text: PropTypes.string.isRequired,
  isOpen: PropTypes.bool.isRequired,
  onConfirm: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
};
