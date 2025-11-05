import React from "react";
import { X } from "lucide-react";

export default function BetaConsentModal({ onAccept, onDecline }) {
  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl max-w-2xl w-full mx-4 overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-500 to-purple-600 px-6 py-4">
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            🧪 Welcome to Erudi Beta
          </h2>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          <div className="space-y-3">
            <p className="text-gray-700 dark:text-gray-300 text-base leading-relaxed">
              Thank you for trying <span className="font-semibold">Erudi Beta</span>! 
              This is a free beta version that helps us understand how users interact 
              with the application.
            </p>

            <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
              <h3 className="font-semibold text-blue-900 dark:text-blue-100 mb-2 flex items-center gap-2">
                📊 What data we collect:
              </h3>
              <ul className="space-y-2 text-sm text-blue-800 dark:text-blue-200">
                <li className="flex items-start gap-2">
                  <span className="mt-1">•</span>
                  <span>Model downloads and usage (which models you use, when you download them)</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-1">•</span>
                  <span>Feature usage (chat, training, knowledge base, arena)</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-1">•</span>
                  <span>Conversation metadata (message length, response time, language, first 50 chars preview)</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-1">•</span>
                  <span>General app interactions (navigation, settings changes)</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-1">•</span>
                  <span>Basic system information (hardware capabilities, performance)</span>
                </li>
              </ul>
            </div>

            <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4">
              <h3 className="font-semibold text-green-900 dark:text-green-100 mb-2 flex items-center gap-2">
                🔒 Your privacy:
              </h3>
              <ul className="space-y-2 text-sm text-green-800 dark:text-green-200">
                <li className="flex items-start gap-2">
                  <span className="mt-1">•</span>
                  <span><strong>No personal data</strong> - We don't collect names, emails, or identifying information</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-1">•</span>
                  <span><strong>No full chat content</strong> - Only metadata (length, language, preview of first 50 chars)</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-1">•</span>
                  <span><strong>Anonymous ID only</strong> - We use a random identifier to group your usage patterns</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-1">•</span>
                  <span><strong>Works offline</strong> - Data is queued and sent only when you're online</span>
                </li>
              </ul>
            </div>

            <p className="text-sm text-gray-600 dark:text-gray-400 italic">
              This data helps us understand which features are most valuable and where 
              to focus our development efforts. By using this beta version, you're helping 
              us build a better product!
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="bg-gray-50 dark:bg-gray-900 px-6 py-4 flex flex-col sm:flex-row gap-3 justify-end">
          <button
            onClick={onDecline}
            className="px-6 py-2.5 rounded-lg font-medium text-gray-700 dark:text-gray-300 
                     bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600
                     hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          >
            Decline & Exit
          </button>
          <button
            onClick={onAccept}
            className="px-6 py-2.5 rounded-lg font-medium text-white 
                     bg-gradient-to-r from-blue-500 to-purple-600 
                     hover:from-blue-600 hover:to-purple-700 
                     transition-all shadow-lg hover:shadow-xl"
          >
            I Accept - Let's Go! 🚀
          </button>
        </div>
      </div>
    </div>
  );
}
