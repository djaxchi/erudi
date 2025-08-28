import React from "react";

export default function LoadingModal({
  show,
  onClose,
  loading,
  cudaLoading,
}) {
  if (!show) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-80 backdrop-blur-sm flex items-center justify-center z-[60] p-4">
      <div className="bg-[#2B2B2B] rounded-2xl border border-white/10 shadow-2xl max-w-2xl w-[60%] max-h-[70vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="p-4 sm:p-6 border-b border-white/10 flex-shrink-0">
          <div className="flex items-center justify-between">
            <h2 className="text-xl sm:text-2xl font-bold text-white flex items-center gap-3">
              ⏳ Please Wait
            </h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-white transition-colors"
            >
              <svg className="w-5 h-5 sm:w-6 sm:h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
              </svg>
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden flex flex-col">
          {/* Center Spinner Section */}
          <div className="flex-1 flex items-center justify-center px-4 sm:px-6 py-6 sm:py-8">
            <div className="text-center">
              <div className="w-16 h-16 sm:w-20 sm:h-20 border-4 border-emerald-400 border-t-transparent rounded-full animate-spin mx-auto mb-4 sm:mb-6"></div>
              <h3 className="text-lg sm:text-xl font-semibold text-white mb-2">
                Evaluating Hardware
              </h3>
              <p className="text-gray-400 text-sm sm:text-base max-w-sm mx-auto leading-relaxed">
                We're checking your system capabilities. This will only take a moment.
              </p>
            </div>
          </div>
          
          {/* Progress Section */}
          <div className="p-4 sm:p-6 text-white">
            <div className="max-w-md mx-auto space-y-3 sm:space-y-4">
              {/* Hardware Evaluation */}
              <div className="bg-[#1a1a1a] rounded-lg p-3 sm:p-4 border border-white/10">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3 min-w-0 flex-1">
                    <div className="flex-shrink-0">
                      {loading ? (
                        <div className="w-5 h-5 sm:w-6 sm:h-6 border-2 border-yellow-400 border-t-transparent rounded-full animate-spin"></div>
                      ) : (
                        <div className="w-5 h-5 sm:w-6 sm:h-6 bg-green-500 rounded-full flex items-center justify-center">
                          <svg className="w-3 h-3 sm:w-4 sm:h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                          </svg>
                        </div>
                      )}
                    </div>
                    <div className="min-w-0">
                      <p className="font-medium text-white text-sm sm:text-base">Hardware Evaluation</p>
                      <p className="text-gray-400 text-xs sm:text-sm">CPU, RAM, and storage analysis</p>
                    </div>
                  </div>
                  <div className="flex-shrink-0">
                    {loading ? (
                      <span className="text-yellow-400 text-xs sm:text-sm font-medium">⏳ Loading...</span>
                    ) : (
                      <span className="text-green-400 text-xs sm:text-sm font-medium">✅ Complete</span>
                    )}
                  </div>
                </div>
              </div>

              {/* CUDA Detection */}
              <div className="bg-[#1a1a1a] rounded-lg p-3 sm:p-4 border border-white/10">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3 min-w-0 flex-1">
                    <div className="flex-shrink-0">
                      {cudaLoading ? (
                        <div className="w-5 h-5 sm:w-6 sm:h-6 border-2 border-yellow-400 border-t-transparent rounded-full animate-spin"></div>
                      ) : (
                        <div className="w-5 h-5 sm:w-6 sm:h-6 bg-green-500 rounded-full flex items-center justify-center">
                          <svg className="w-3 h-3 sm:w-4 sm:h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                          </svg>
                        </div>
                      )}
                    </div>
                    <div className="min-w-0">
                      <p className="font-medium text-white text-sm sm:text-base">CUDA Detection</p>
                      <p className="text-gray-400 text-xs sm:text-sm">GPU acceleration compatibility</p>
                    </div>
                  </div>
                  <div className="flex-shrink-0">
                    {cudaLoading ? (
                      <span className="text-yellow-400 text-xs sm:text-sm font-medium">⏳ Detecting...</span>
                    ) : (
                      <span className="text-green-400 text-xs sm:text-sm font-medium">✅ Complete</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 sm:p-6 border-t border-white/10 flex-shrink-0">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-gray-400 text-xs sm:text-sm order-2 sm:order-1">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
              </svg>
              <span>Auto-closing when ready...</span>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-white transition-colors text-sm font-medium order-1 sm:order-2"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
