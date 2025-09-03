import React from "react";
import { createPortal } from "react-dom";

/**
 * Props:
 * - modelInfo: object with model information
 * - isOpen: boolean
 * - onClose: () => void
 * - onDownload: (modelInfo) => void
 */
export default function ModelInfoModal({ modelInfo, isOpen, onClose, onDownload }) {
  if (!isOpen || !modelInfo) return null;

  // Ensure there's a div#modal-root in your index.html
  return createPortal(
    <div className="fixed inset-0 flex items-center justify-center z-50">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black bg-opacity-70"
        onClick={onClose}
      />
      
      {/* Modal container */}
      <div className="relative bg-[#313131] rounded-2xl px-20 py-12 w-[60%] max-h-[80vh] overflow-auto shadow-lg shadow-emerald-500/10">
        <div className="flex items-start justify-between mb-6">
          <div>
            <h2 className="text-xl font-semibold text-white pr-4">{modelInfo.name}</h2>
            <p className="text-gray-300 mt-1">{modelInfo.description || "No description available"}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-300 hover:text-white transition-colors p-1"
          >
            ×
          </button>
        </div>
        
        {/* Metadata Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <div className="space-y-3">
            <h3 className="text-lg font-semibold text-white border-b border-white/20 pb-2">Basic Info</h3>
            <div className="space-y-2 text-sm">
              <p className="text-gray-300"><span className="text-white font-medium">Size:</span> {modelInfo.size}</p>
              <p className="text-gray-300"><span className="text-white font-medium">Parameters:</span> {modelInfo.parameters}</p>
              {modelInfo.author && modelInfo.author !== "Unknown" && (
                <p className="text-gray-300"><span className="text-white font-medium">Author:</span> {modelInfo.author}</p>
              )}
              {modelInfo.library && modelInfo.library !== "Unknown" && (
                <p className="text-gray-300"><span className="text-white font-medium">Library:</span> {modelInfo.library}</p>
              )}
            </div>
          </div>
          
          <div className="space-y-3">
            <h3 className="text-lg font-semibold text-white border-b border-white/20 pb-2">Stats</h3>
            <div className="space-y-2 text-sm">
              {modelInfo.downloads && modelInfo.downloads !== "Unknown" && (
                <p className="text-gray-300"><span className="text-white font-medium">Downloads:</span> {modelInfo.downloads}</p>
              )}
              {modelInfo.likes && modelInfo.likes !== "Unknown" && (
                <p className="text-gray-300"><span className="text-white font-medium">Likes:</span> {modelInfo.likes}</p>
              )}
              {modelInfo.lastUpdate && modelInfo.lastUpdate !== "Unknown" && (
                <p className="text-gray-300"><span className="text-white font-medium">Last Update:</span> {modelInfo.lastUpdate}</p>
              )}
              {modelInfo.pipeline && modelInfo.pipeline !== "Unknown" && (
                <p className="text-gray-300"><span className="text-white font-medium">Pipeline:</span> {modelInfo.pipeline}</p>
              )}
            </div>
          </div>
        </div>
        
        {/* Raw Metadata (collapsible) */}
        {modelInfo.rawMetadata && (
          <div className="border-t border-white/20 pt-4">
            <details className="group">
              <summary className="cursor-pointer text-white font-medium mb-3 hover:text-gray-300">
                Show Raw Metadata
              </summary>
              <div className="bg-black/40 p-4 rounded-lg text-xs text-gray-400 font-mono whitespace-pre-wrap max-h-60 overflow-auto">
                {modelInfo.rawMetadata}
              </div>
            </details>
          </div>
        )}
        
        {/* Action Buttons */}
        <div className="flex justify-start gap-4 mt-6 pt-4 border-t border-white/20">
          <button
            onClick={onClose}
            className="px-4 py-1 border border-red-500 text-red-500 rounded-full hover:bg-red-500/10 transition-shadow shadow-none hover:shadow-lg"
          >
            Cancel
          </button>
          <button
            onClick={() => {
              onDownload(modelInfo);
              onClose();
            }}
            className="px-4 py-2 border border-emerald-500 text-emerald-500 rounded-full hover:bg-emerald-500/10 transition-shadow shadow-none hover:shadow-lg"
          >
            Download
          </button>
        </div>
      </div>
    </div>,
    document.getElementById("modal-root")
  );
}
