import React, { useEffect, useState } from "react";
import { createPortal } from "react-dom";

export default function PreparingModal({ isOpen, onClose }) {
  const [visible, setVisible] = useState(isOpen);

  useEffect(() => {
    let timeout;
    let closeTimeout;

    if (isOpen) {
      setVisible(true);

      timeout = setTimeout(() => {
        setVisible(false); // start fade-out
        closeTimeout = setTimeout(onClose, 300); // wait for fade-out animation
      }, 10000); // auto close after 10s
    }

    return () => {
      clearTimeout(timeout);
      clearTimeout(closeTimeout);
    };
  }, [isOpen, onClose]);

  if (!isOpen && !visible) return null;

  return createPortal(
    <div
      className={`fixed inset-0 flex items-center justify-center z-50 transition-opacity duration-300 ${
        visible ? "opacity-100" : "opacity-0"
      }`}
    >
      <div
        className="absolute inset-0 bg-black bg-opacity-60"
        onClick={() => {
          setVisible(false);
          setTimeout(onClose, 300);
        }}
      />
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
