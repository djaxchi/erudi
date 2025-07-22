// frontend/src/pages/LoadingPage.jsx
import React from "react";

export default function LoadingPage() {
  return (
    <div className="flex flex-col items-center justify-center w-screen h-screen bg-[#01110C]">
      {/* Logo */}
      <h1 className="text-emerald-500 text-4xl mb-4">Erudi</h1>

      {/* Subtitle */}
      <p className="text-white text-lg mb-8">local fine tuning</p>

      {/* Spinner */}
      <div className="w-16 h-16 border-4 border-gray-600 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}
