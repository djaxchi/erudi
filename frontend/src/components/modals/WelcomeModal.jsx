import React from "react";
import { HelpCircle } from "lucide-react";
import logoErudi from "../../img/logo-erudi.png";

export default function WelcomeModal({ isOpen, onClose, hardwareInfo, loading }) {
    if (!isOpen) return null;

    return (
        <div 
            className="fixed inset-0 bg-black bg-opacity-50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
            onClick={onClose}
        >
            <div 
                className={[
                    "rounded-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto",
                    "border border-white/10",
                    "bg-[rgba(22,40,36,0.45)] backdrop-blur-[18px] saturate-[1.4]",
                    "shadow-[0_8px_30px_-4px_rgba(0,0,0,0.45),0_2px_6px_-1px_rgba(0,0,0,0.4),inset_0_1px_0_rgba(255,255,255,0.06)]",
                ].join(" ")}
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="text-center py-6 px-6 sm:py-8 sm:px-8">
                    <h1 className="text-4xl sm:text-5xl font-bold mb-4">
                        <span className="text-[#00B574]">Welcome!</span>
                    </h1>
                    <p className="text-lg sm:text-xl text-gray-300 mb-2 flex items-center justify-center gap-2">
                        <img src={logoErudi} alt="erudi" className="h-12 sm:h-12" /> is a <span className="text-[#00B574]">personal</span> AI training platform.
                    </p>
                    <p className="text-lg sm:text-xl text-gray-300">
                        Get ready to chat and <span className="text-[#00B574]">specialize</span> your <span className="text-[#00B574]">own</span> AI models!
                    </p>
                </div>

                {/* Content */}
                <div className="px-4 pb-6 sm:px-8 sm:pb-8">
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
                        {/* Left Column - Important Notice */}
                        <div className="bg-amber-900/30 border border-amber-600/40 rounded-xl p-4 sm:p-6">
                            <div className="flex items-start gap-3 sm:gap-4">
                                <div className="text-xl sm:text-2xl mt-1">⚠️</div>
                                <div className="flex-1">
                                    <h3 className="text-[#E5D07D] font-semibold text-lg mb-3 flex items-center gap-2">
                                        Important Notice
                                    </h3>
                                    <div className="space-y-3 text-sm sm:text-base">
                                        <p className="text-gray-300 leading-relaxed">
                                            The app is in early alpha and highly dependent on your PC's hardware.
                                        </p>
                                        <p className="text-gray-300 leading-relaxed">
                                            Features may change, and you may encounter bugs. If you do, we'd be grateful if you report to our team.
                                        </p>
                                        <p className="text-gray-300 leading-relaxed">
                                            Every report helps us improve and your feedback means a lot, and we truly appreciate the time you take to test and support the project.
                                        </p>
                                        <p className="text-[#E5D07D] font-medium">
                                            Thank you for being part of this journey
                                        </p>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Right Column - Hardware Evaluation */}
                        <div className="space-y-4">
                            {/* Hardware Evaluation */}
                            <div className="bg-[#1A1A1A] rounded-xl p-4 sm:p-6">
                                <div className="flex items-center gap-3 mb-4">
                                    <div className="w-8 h-8 bg-[#00B574]/20 rounded-lg flex items-center justify-center">
                                        <span className="text-[#00B574] text-lg">🖥️</span>
                                    </div>
                                    <h3 className="text-[#00B574] font-semibold text-lg">Hardware Evaluation</h3>
                                </div>

                                {loading ? (
                                    <div className="flex items-center justify-center py-6 sm:py-8">
                                        <div className="w-6 h-6 sm:w-8 sm:h-8 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin"></div>
                                        <span className="ml-3 text-gray-300 text-sm sm:text-base">We are evaluating your hardware...</span>
                                    </div>
                                ) : hardwareInfo?.error ? (
                                    <div className="text-red-400 bg-red-900/20 border border-red-600/30 rounded-lg p-3">
                                        <p className="font-medium">⚠️ Evaluation Failed</p>
                                        <p className="text-sm mt-1">{hardwareInfo.error}</p>
                                    </div>
                                ) : hardwareInfo ? (
                                    <div className="space-y-3">
                                        {/* Performance Cards */}
                                        <div className="space-y-3">
                                            <div className="bg-[#242424] rounded-lg p-3 sm:p-4">
                                                <div className="flex items-center justify-between">
                                                    <span className="text-gray-400 text-sm">Chat Performance</span>
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-lg sm:text-xl font-bold text-white">
                                                            {Math.round(hardwareInfo.global_inference_score)}%
                                                        </span>
                                                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                                                            hardwareInfo.global_inference_score >= 70 ? 'bg-[#00B574]/80 text-white' :
                                                            hardwareInfo.global_inference_score >= 50 ? 'bg-yellow-900/80 text-yellow-300' :
                                                            'bg-red-900/80 text-red-300'
                                                        }`}>
                                                            {hardwareInfo.global_inference_label || 'Unknown'}
                                                        </span>
                                                    </div>
                                                </div>
                                            </div>

                                            <div className="bg-[#242424] rounded-lg p-3 sm:p-4">
                                                <div className="flex items-center justify-between">
                                                    <span className="text-gray-400 text-sm">Training Performance</span>
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-lg sm:text-xl font-bold text-white">
                                                            {Math.round(hardwareInfo.global_finetuning_score)}%
                                                        </span>
                                                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                                                            hardwareInfo.global_finetuning_score >= 70 ? 'bg-[#00B574] text-white' :
                                                            hardwareInfo.global_finetuning_score >= 50 ? 'bg-yellow-600 text-white' :
                                                            'bg-red-900/80 text-red-300'
                                                        }`}>
                                                            {hardwareInfo.global_finetuning_label || 'Unknown'}
                                                        </span>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>

                                        {/* Summary */}
                                        <div className="bg-[#242424] rounded-lg p-3 sm:p-4">
                                            <div className="flex items-start gap-3">
                                                <HelpCircle className="w-4 h-4 sm:w-5 sm:h-5 text-[#E3712B] transition-colors cursor-help mt-0.5" />
                                                <div className="flex-1 min-w-0">
                                                    <h4 className="text-[#E3712B] font-semibold mb-2 flex items-center gap-0">Summary</h4>
                                                    <p className="text-gray-300 text-sm leading-relaxed">
                                                        {(hardwareInfo.global_inference_score >= 70 && hardwareInfo.global_finetuning_score >= 70) 
                                                            ? 'Good overall performance, you should get fluid experience on most models'
                                                            : (hardwareInfo.global_inference_score >= 50 || hardwareInfo.global_finetuning_score >= 50)
                                                            ? 'Good overall performance, some finetuning operations may be slower'
                                                            : 'Limited performance. It will do the trick on smaller models but you may experience some lag with larger ones.'
                                                        }
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                ) : null}
                            </div>

                            {/* Get Started Button */}
                            <div className="flex justify-center">
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        onClose();
                                    }}
                                    className={[
                                        "rounded-full px-5 py-2 text-sm font-semibold",
                                        "bg-[#00B574] hover:bg-[#009960] text-white",
                                        "border border-white/20 shadow",
                                        "transition active:scale-95",
                                        "flex items-center gap-2",
                                    ].join(" ")}
                                >
                                    Get Started
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}