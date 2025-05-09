import React, { useState } from "react";

export default function InfoRow({ label, children }) {
    return (
      <div className="flex justify-between items-center py-1">
        <span className="text-gray-200 font-medium w-1/2">{label}</span>
        <div className="w-1/2 flex justify-end text-white">{children}</div>
      </div>
    );
  }
  