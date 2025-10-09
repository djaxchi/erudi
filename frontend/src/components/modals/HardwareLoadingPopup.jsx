import React from "react";

export default function HardwareLoadingPopup({ show, loading, onClose }) {
  if (!show) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-60 backdrop-blur-sm flex items-center justify-center z-[60] p-4">
      <div className="bg-[#2B2B2B] rounded-2xl border border-white/10 shadow-2xl max-w-md w-full">
        {/* Header */}
        <div className="p-6 border-b border-white/10">
          <h2 className="text-xl font-bold text-white text-center">
            Hardware Evaluation
          </h2>
        </div>

        {/* Content */}
        <div className="p-6">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="w-8 h-8 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin"></div>
              <span className="ml-3 text-gray-300">Evaluating your hardware...</span>
            </div>
          ) : (
            <div className="text-center py-4">
              <p className="text-gray-300 mb-4">Hardware evaluation complete!</p>
              <button
                onClick={onClose}
                className="bg-emerald-600 hover:bg-emerald-700 text-white px-6 py-2 rounded-lg transition-colors font-medium"
              >
                Continue
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}