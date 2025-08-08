import React, { useState } from "react";

export default function InfoRow({ label, children, bullet, icon, isHeader = false }) {
    return (
      <div className={`flex justify-between items-center gap-2 overflow-visible ${isHeader ? 'py-2 sm:py-3' : 'py-1 sm:py-1.5'}`}>
        <span className={`text-gray-200 flex-shrink-0 min-w-0 overflow-visible ${
          isHeader 
            ? 'font-bold text-sm sm:text-base lg:text-lg' 
            : 'font-medium text-xs sm:text-sm lg:text-base'
        }`}>{label}</span>
        <div className="flex justify-end items-center text-right text-white text-xs sm:text-sm lg:text-base min-w-0 gap-2 overflow-visible">
          {icon && <div className="flex-shrink-0">{icon}</div>}
          {!icon && bullet && <div className={`w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full ${bullet} flex-shrink-0`}></div>}
          <span className="truncate">{children}</span>
        </div>
      </div>
    );
  }
  