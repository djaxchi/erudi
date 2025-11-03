import React, { useState } from "react";
import PropTypes from "prop-types";
import { motion, AnimatePresence } from "framer-motion";
import { X, Download, Users, Heart, Calendar, Tag, ChevronDown } from "lucide-react";

/**
 * Props:
 * - modelInfo: object with model information
 * - isOpen: boolean
 * - onClose: () => void
 * - onDownload: (modelInfo) => void
 */

ModelInfoModal.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  model: PropTypes.shape({
    name: PropTypes.string,
    description: PropTypes.string,
    size: PropTypes.string,
    parameters: PropTypes.string,
  }),
  onClose: PropTypes.func.isRequired,
};

ModelInfoModal.defaultProps = {
  model: null,
};

export default function ModelInfoModal({ modelInfo, isOpen, onClose, onDownload }) {
  const [showRawMetadata, setShowRawMetadata] = useState(false);

  return (
    <AnimatePresence>
      {isOpen && modelInfo && (
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
            className="relative w-full max-w-3xl max-h-[80vh] overflow-hidden"
          >
            {/* Modal container with HeaderBar-like styling */}
            <div
              className={[
                "relative w-full rounded-[26px] overflow-hidden",
                "border border-white/10",
                "bg-[rgba(22,40,36,0.45)] backdrop-blur-[18px] saturate-[1.4]",
                "shadow-[0_8px_30px_-4px_rgba(0,0,0,0.45),0_2px_6px_-1px_rgba(0,0,0,0.4),inset_0_1px_0_rgba(255,255,255,0.06)]",
              ].join(" ")}
            >
              {/* Glossy overlays matching HeaderBar */}
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
              <div className="relative z-10 flex flex-col h-full max-h-[80vh]">
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-white/10">
                  <div className="flex-1">
                    <h2 className="text-xl font-semibold tracking-tight text-[#F2F7F4] mb-1">
                      {modelInfo.name}
                    </h2>
                    <p className="text-sm text-gray-300/80">
                      {modelInfo.description || "No description available"}
                    </p>
                  </div>
                  <button
                    onClick={onClose}
                    className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 text-gray-300 hover:text-gray-100 transition ml-4"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                {/* Scrollable content */}
                <div className="flex-1 overflow-y-auto p-6">
                  {/* Metadata Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                    <div className="space-y-4">
                      <h3 className="text-lg font-semibold text-[#F2F7F4] flex items-center gap-2">
                        <Tag className="w-4 h-4 text-emerald-400" />
                        Basic Info
                      </h3>
                      <div className="space-y-3 text-sm">
                        <div className="bg-white/5 rounded-xl p-3 border border-white/10">
                          <span className="text-emerald-400 font-medium">Size:</span>
                          <span className="text-gray-200 ml-2">{modelInfo.size}</span>
                        </div>
                        <div className="bg-white/5 rounded-xl p-3 border border-white/10">
                          <span className="text-emerald-400 font-medium">Parameters:</span>
                          <span className="text-gray-200 ml-2">{modelInfo.parameters}</span>
                        </div>
                        {modelInfo.author && modelInfo.author !== "Unknown" && (
                          <div className="bg-white/5 rounded-xl p-3 border border-white/10">
                            <span className="text-emerald-400 font-medium">Author:</span>
                            <span className="text-gray-200 ml-2">{modelInfo.author}</span>
                          </div>
                        )}
                        {modelInfo.library && modelInfo.library !== "Unknown" && (
                          <div className="bg-white/5 rounded-xl p-3 border border-white/10">
                            <span className="text-emerald-400 font-medium">Library:</span>
                            <span className="text-gray-200 ml-2">{modelInfo.library}</span>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="space-y-4">
                      <h3 className="text-lg font-semibold text-[#F2F7F4] flex items-center gap-2">
                        <Users className="w-4 h-4 text-emerald-400" />
                        Stats
                      </h3>
                      <div className="space-y-3 text-sm">
                        {modelInfo.downloads && modelInfo.downloads !== "Unknown" && (
                          <div className="bg-white/5 rounded-xl p-3 border border-white/10 flex items-center gap-2">
                            <Download className="w-4 h-4 text-emerald-400" />
                            <span className="text-emerald-400 font-medium">Downloads:</span>
                            <span className="text-gray-200">{modelInfo.downloads}</span>
                          </div>
                        )}
                        {modelInfo.likes && modelInfo.likes !== "Unknown" && (
                          <div className="bg-white/5 rounded-xl p-3 border border-white/10 flex items-center gap-2">
                            <Heart className="w-4 h-4 text-emerald-400" />
                            <span className="text-emerald-400 font-medium">Likes:</span>
                            <span className="text-gray-200">{modelInfo.likes}</span>
                          </div>
                        )}
                        {modelInfo.lastUpdate && modelInfo.lastUpdate !== "Unknown" && (
                          <div className="bg-white/5 rounded-xl p-3 border border-white/10 flex items-center gap-2">
                            <Calendar className="w-4 h-4 text-emerald-400" />
                            <span className="text-emerald-400 font-medium">Last Update:</span>
                            <span className="text-gray-200">{modelInfo.lastUpdate}</span>
                          </div>
                        )}
                        {modelInfo.pipeline && modelInfo.pipeline !== "Unknown" && (
                          <div className="bg-white/5 rounded-xl p-3 border border-white/10">
                            <span className="text-emerald-400 font-medium">Pipeline:</span>
                            <span className="text-gray-200 ml-2">{modelInfo.pipeline}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Raw Metadata (collapsible) */}
                  {modelInfo.rawMetadata && (
                    <div className="border-t border-white/10 pt-6">
                      <button
                        onClick={() => setShowRawMetadata(!showRawMetadata)}
                        className="flex items-center gap-2 cursor-pointer text-[#F2F7F4] font-medium mb-3 hover:text-emerald-400 transition-colors select-none group"
                      >
                        <motion.div
                          animate={{ rotate: showRawMetadata ? 180 : 0 }}
                          transition={{ duration: 0.2 }}
                        >
                          <ChevronDown className="w-4 h-4" />
                        </motion.div>
                        Show Raw Metadata
                      </button>

                      <AnimatePresence>
                        {showRawMetadata && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{
                              duration: 0.3,
                              ease: [0.16, 1, 0.3, 1],
                            }}
                            style={{ overflow: "hidden" }}
                          >
                            <motion.div
                              initial={{ y: -10 }}
                              animate={{ y: 0 }}
                              exit={{ y: -10 }}
                              transition={{
                                duration: 0.3,
                                ease: [0.16, 1, 0.3, 1],
                              }}
                              className="bg-black/40 border border-white/10 p-4 rounded-2xl text-xs text-gray-300 font-mono whitespace-pre-wrap max-h-60 overflow-auto"
                            >
                              {modelInfo.rawMetadata}
                            </motion.div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  )}
                </div>

                {/* Footer */}
                <div className="flex items-center justify-end gap-3 p-6 border-t border-white/10">
                  <button
                    onClick={onClose}
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
                    onClick={() => {
                      onDownload(modelInfo);
                      onClose();
                    }}
                    className={[
                      "rounded-full px-5 py-2 text-sm font-semibold",
                      "bg-emerald-500 hover:bg-emerald-600 text-[#0f2f25]",
                      "border border-white/20 shadow",
                      "transition active:scale-95",
                      "flex items-center gap-2",
                    ].join(" ")}
                  >
                    <Download className="w-4 h-4" />
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
