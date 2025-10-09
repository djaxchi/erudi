import React, { useState } from "react";
import { X, Download, ChevronDown, ChevronUp } from "lucide-react";

/**
 * Props:
 * - modelInfo: object with model information
 * - isOpen: boolean
 * - onClose: () => void
 * - onDownload: (modelInfo) => void
 */
export default function ModelInfoModal({
  modelInfo,
  isOpen,
  onClose,
  onDownload,
}) {
  const [showRawMetadata, setShowRawMetadata] = useState(false);

  if (!isOpen || !modelInfo) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-[#2B2B2B] rounded-2xl border border-white/10 shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="p-6 border-b border-white/10">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold text-white">{modelInfo.name}</h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-white transition-colors"
            >
              <X className="w-6 h-6" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-200px)]">
          {/* Description */}
          {modelInfo.description && (
            <div className="mb-6">
              <h3 className="text-lg font-semibold text-white mb-2">Description</h3>
              <p className="text-gray-300 text-sm">{modelInfo.description}</p>
            </div>
          )}

          {/* Model Details */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div className="bg-[#1a1a1a] rounded-lg p-4">
              <h4 className="text-white font-medium mb-2">Model Details</h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-400">Size:</span>
                  <span className="text-white">{modelInfo.size || 'Unknown'}</span>
                </div>
                {modelInfo.parameters && (
                  <div className="flex justify-between">
                    <span className="text-gray-400">Parameters:</span>
                    <span className="text-white">{modelInfo.parameters}</span>
                  </div>
                )}
                {modelInfo.author && (
                  <div className="flex justify-between">
                    <span className="text-gray-400">Author:</span>
                    <span className="text-white">{modelInfo.author}</span>
                  </div>
                )}
                {modelInfo.library && (
                  <div className="flex justify-between">
                    <span className="text-gray-400">Library:</span>
                    <span className="text-white">{modelInfo.library}</span>
                  </div>
                )}
              </div>
            </div>

            <div className="bg-[#1a1a1a] rounded-lg p-4">
              <h4 className="text-white font-medium mb-2">Statistics</h4>
              <div className="space-y-2 text-sm">
                {modelInfo.downloads && (
                  <div className="flex justify-between">
                    <span className="text-gray-400">Downloads:</span>
                    <span className="text-white">{modelInfo.downloads}</span>
                  </div>
                )}
                {modelInfo.likes && (
                  <div className="flex justify-between">
                    <span className="text-gray-400">Likes:</span>
                    <span className="text-white">{modelInfo.likes}</span>
                  </div>
                )}
                {modelInfo.lastUpdate && (
                  <div className="flex justify-between">
                    <span className="text-gray-400">Last Update:</span>
                    <span className="text-white">{modelInfo.lastUpdate}</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Raw Metadata (collapsible) */}
          {modelInfo.rawMetadata && (
            <div className="mb-6">
              <button
                onClick={() => setShowRawMetadata(!showRawMetadata)}
                className="flex items-center gap-2 text-white hover:text-gray-300 transition-colors mb-2"
              >
                <span className="font-medium">Raw Metadata</span>
                {showRawMetadata ? (
                  <ChevronUp className="w-4 h-4" />
                ) : (
                  <ChevronDown className="w-4 h-4" />
                )}
              </button>
              {showRawMetadata && (
                <div className="bg-[#1a1a1a] rounded-lg p-4">
                  <pre className="text-xs text-gray-300 whitespace-pre-wrap overflow-x-auto">
                    {modelInfo.rawMetadata}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-white/10">
          <div className="flex justify-end gap-3">
            <button
              onClick={onClose}
              className="bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded-lg transition-colors font-medium"
            >
              Close
            </button>
            {onDownload && (
              <button
                onClick={() => onDownload(modelInfo)}
                className="bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded-lg transition-colors font-medium flex items-center gap-2"
              >
                <Download className="w-4 h-4" />
                Download
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}