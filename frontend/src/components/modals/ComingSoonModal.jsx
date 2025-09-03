import React from "react";
import { X } from "lucide-react";

export default function ComingSoonModal({ showComingSoonModal, onClose, featureName, featureDescription }) {
  if (!showComingSoonModal) return null;
  return (
    <div className="fixed inset-0 bg-black bg-opacity-60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-[#2B2B2B] rounded-2xl border border-white/10 shadow-2xl max-w-md w-full">
        {/* Header */}
        <div className="p-4 border-b border-white/10">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold text-white flex items-center gap-3">
              🚧 Coming Soon
            </h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-white transition-colors"
            >
              <X className="w-6 h-6" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6">
          <div className="text-gray-300 text-center">
            <p className="text-sm mb-4">
              {featureName} feature is currently under development and will be available in a future update.
            </p>
            <p className="text-xs text-gray-400">
              {featureDescription}
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-white/10">
          <div className="flex justify-end">
            <button
              onClick={onClose}
              className="bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded-lg transition-colors font-medium"
            >
              Got it
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
