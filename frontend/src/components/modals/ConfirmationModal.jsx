import React from "react";
import { createPortal } from "react-dom";

/**
 * Props:
 * - text: string to display in question
 * - onConfirm: () => void
 * - onCancel: () => void
 * - isOpen: boolean
 */
export default function ConfirmationModal({ text, isOpen, onConfirm, onCancel }) {
  if (!isOpen) return null;

  // Ensure there's a div#modal-root in your index.html
  return createPortal(
    <div className="fixed inset-0 flex items-center justify-center z-50">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black bg-opacity-70"
        onClick={onCancel}
      />

      {/* Modal container */}
      <div className="relative bg-[#313131] rounded-2xl px-20 py-12 w-[50%] shadow-lg shadow-emerald-500/10">
        <h2 className="text-xl font-semibold text-white pr-4">
          Are you sure you want to download <span className="font-bold">{text}</span>
        </h2>
        <p className="mt-1 text-gray-300">It will install locally</p>

        <div className="mt-4 flex justify-start gap-4">
          <button
            onClick={onConfirm}
            className="px-4 py-2 border border-emerald-500 text-emerald-500 rounded-full hover:bg-emerald-500/10 transition-shadow shadow-none hover:shadow-lg"
          >
            Yes
          </button>
          <button
            onClick={onCancel}
            className="px-4 py-1 border border-red-500 text-red-500 rounded-full hover:bg-red-500/10 transition-shadow shadow-none hover:shadow-lg"
          >
            No
          </button>
        </div>
      </div>
    </div>,
    document.getElementById("modal-root")
  );
}



