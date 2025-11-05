import React from "react";
import { ShieldCheck, Lock, Database } from "lucide-react";

export default function BetaConsentModal({ isOpen, onAccept, onDecline }) {
  if (!isOpen) return null;

  return (
    <div 
      className="fixed inset-0 bg-black bg-opacity-50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={(e) => e.stopPropagation()}
    >
      <div 
        className={[
          "rounded-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto custom-scroll",
          "border border-white/10",
          "bg-[rgba(22,40,36,0.45)] backdrop-blur-[18px] saturate-[1.4]",
          "shadow-[0_8px_30px_-4px_rgba(0,0,0,0.45),0_2px_6px_-1px_rgba(0,0,0,0.4),inset_0_1px_0_rgba(255,255,255,0.06)]",
        ].join(" ")}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="text-center py-6 px-6 sm:py-8 sm:px-8">
          <h1 className="text-4xl sm:text-5xl font-bold mb-4">
            <span className="text-[#00B574]">🧪 Beta Program</span>
          </h1>
          <p className="text-lg sm:text-xl text-gray-300 mb-2">
            Help us improve by sharing <span className="text-[#00B574]">anonymous</span> usage data
          </p>
          <p className="text-lg sm:text-xl text-gray-300">
            Your privacy is our <span className="text-[#00B574]">top priority</span>
          </p>
        </div>

        {/* Content */}
        <div className="px-4 pb-6 sm:px-8 sm:pb-8">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
            {/* Left Column - What We Collect */}
            <div className="bg-[#1A1A1A]/70 border border-white/10 rounded-xl p-4 sm:p-6 backdrop-blur-[10px] saturate-[1.2]">
              <div className="flex items-start gap-3 sm:gap-4">
                <Database className="w-8 h-8 text-[#00B574] mt-1" />
                <div className="flex-1">
                  <h3 className="text-[#00B574] font-semibold text-lg mb-3 flex items-center gap-2">
                    What We Collect
                  </h3>
                  <div className="space-y-3 text-sm sm:text-base">
                    <p className="text-gray-300 leading-relaxed">
                      Thank you for trying <span className="font-semibold text-white">Erudi Beta</span>! 
                      This free beta helps us understand how users interact with the app.
                    </p>
                    <ul className="space-y-2.5 text-gray-300">
                      <li className="flex items-start gap-2">
                        <span className="text-[#00B574] mt-0.5">•</span>
                        <span>Model downloads and usage patterns</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="text-[#00B574] mt-0.5">•</span>
                        <span>Feature usage (chat, training, knowledge base, arena)</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="text-[#00B574] mt-0.5">•</span>
                        <span>Conversation metadata (length, response time, language)</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="text-[#00B574] mt-0.5">•</span>
                        <span>App interactions and settings changes</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="text-[#00B574] mt-0.5">•</span>
                        <span>Basic system information and performance</span>
                      </li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>

            {/* Right Column - Your Privacy */}
            <div className="space-y-4">
              {/* Privacy Card */}
              <div className="bg-emerald-900/30 border border-emerald-600/40 rounded-xl p-4 sm:p-6">
                <div className="flex items-start gap-3 sm:gap-4">
                  <Lock className="w-8 h-8 text-emerald-400 mt-1" />
                  <div className="flex-1">
                    <h3 className="text-emerald-400 font-semibold text-lg mb-3 flex items-center gap-2">
                      Your Privacy
                    </h3>
                    <div className="space-y-3 text-sm sm:text-base">
                      <p className="text-gray-300 leading-relaxed">
                        We take your privacy seriously and follow strict data protection practices.
                      </p>
                      <ul className="space-y-2.5 text-gray-300">
                        <li className="flex items-start gap-2">
                          <span className="text-emerald-400 mt-0.5 font-bold">✓</span>
                          <span><strong className="text-white">No personal data</strong> - No names, emails, or identifiers</span>
                        </li>
                        <li className="flex items-start gap-2">
                          <span className="text-emerald-400 mt-0.5 font-bold">✓</span>
                          <span><strong className="text-white">No full chat content</strong> - Only metadata</span>
                        </li>
                        <li className="flex items-start gap-2">
                          <span className="text-emerald-400 mt-0.5 font-bold">✓</span>
                          <span><strong className="text-white">Anonymous ID only</strong> - Random identifier for usage patterns</span>
                        </li>
                        <li className="flex items-start gap-2">
                          <span className="text-emerald-400 mt-0.5 font-bold">✓</span>
                          <span><strong className="text-white">Works offline</strong> - Data queued and sent when online</span>
                        </li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>

              {/* Info Box */}
              <div className="bg-[#1A1A1A]/70 border border-white/10 rounded-xl p-4 sm:p-6 backdrop-blur-[10px] saturate-[1.2]">
                <p className="text-gray-300 text-sm sm:text-base leading-relaxed italic">
                  This data helps us understand which features are most valuable and where 
                  to focus our development efforts. By using this beta, you're helping us build a better product!
                </p>
              </div>
            </div>
          </div>

          {/* Get Started Button - Centered */}
          <div className="flex justify-center mt-6 gap-3">
            <button
              onClick={onDecline}
              className={[
                "rounded-full px-5 py-2 text-sm font-semibold",
                "bg-gray-700/50 hover:bg-gray-700/70 text-gray-300 hover:text-white",
                "border border-white/20 shadow backdrop-blur-[6px] saturate-[1.1]",
                "transition active:scale-95",
              ].join(" ")}
            >
              Decline & Exit
            </button>
            <button
              onClick={onAccept}
              className={[
                "rounded-full px-5 py-2 text-sm font-semibold",
                "bg-[#00B574]/80 hover:bg-[#009960]/80 text-white",
                "border border-white/20 shadow backdrop-blur-[6px] saturate-[1.1]",
                "transition active:scale-95",
                "flex items-center gap-2",
              ].join(" ")}
            >
              I Accept - Let's Go! 🚀
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
