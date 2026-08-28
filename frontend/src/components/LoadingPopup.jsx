import React from "react";
import PropTypes from "prop-types";
import { useTranslation } from "react-i18next";

export default function HardwareLoadingPopup({ show, loading, onClose }) {
  const { t } = useTranslation();
  if (!show) {
    return null;
  }
  return (
    <div className="fixed inset-0 bg-black bg-opacity-80 backdrop-blur-sm flex items-center justify-center z-[60] p-4">
      <div className="bg-[#1B1B1B] rounded-2xl border border-white/20 shadow-2xl max-w-md w-full">
        {/* Header */}
        <div className="p-6 border-b border-white/10">
          <div className="flex items-center justify-between">
            <h3 className="text-xl font-bold text-white flex items-center gap-3">
              {t("downloads:hardwareWait.title")}
            </h3>
            <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M6 18L18 6M6 6l12 12"
                ></path>
              </svg>
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6">
          <div className="text-center">
            <div className="w-12 h-12 border-3 border-emerald-400 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-white font-medium mb-2">{t("downloads:hardwareWait.evaluating")}</p>
            <p className="text-gray-400 text-sm mb-4">{t("downloads:hardwareWait.body")}</p>
            <div className="space-y-2 text-xs text-gray-500">
              <div className="flex items-center justify-between">
                <span>{t("downloads:hardwareWait.stepLabel")}</span>
                {loading ? (
                  <span className="text-yellow-400">{t("downloads:hardwareWait.stepLoading")}</span>
                ) : (
                  <span className="text-green-400">{t("downloads:hardwareWait.stepComplete")}</span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-white/10">
          <div className="flex justify-between">
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-white transition-colors text-sm"
            >
              {t("common:actions.close")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

HardwareLoadingPopup.propTypes = {
  show: PropTypes.bool.isRequired,
  loading: PropTypes.bool,
  onClose: PropTypes.func,
};
