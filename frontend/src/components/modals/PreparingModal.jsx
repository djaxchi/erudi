import React from "react";
import { createPortal } from "react-dom";

/**
 * PreparingModal
 * Props:
 * - isOpen: boolean
 * - onClose: () => void
 */
export default function PreparingModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  return createPortal(
    <div className="fixed inset-0 flex items-center justify-center z-50">
      {/* Semi-opaque backdrop */}
      <div
        className="absolute inset-0 bg-black bg-opacity-60"
        onClick={onClose}
      />
        
        {/* Modal container */}
      <div className="relative bg-[#313131] rounded-2xl px-20 py-8 w-[50%] flex items-center justify-between gap-4 shadow-lg shadow-emerald-500/10">
        <div className="flex flex-col">
          <h2 className="text-xl font-semibold text-white">
            Preparing your model...
          </h2>
          <p className="mt-2 text-gray-300">
            Should be good in a couple of minutes
          </p>
        </div>

        <div className="relative w-10 h-10 flex items-center justify-center">
          <div className="absolute inset-0 rounded-full bg-emerald-500 opacity-40 blur-xl"></div>
          <div className="relative w-full h-full border-4 border-white/30 border-t-white rounded-full animate-spin"></div>
        </div>
      </div>
    </div>,
    document.getElementById("modal-root")
  );
}



