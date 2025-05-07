import React from "react";

export default function SidebarIcon({ children, active }) {
  return (
    <div
      className={`w-full flex justify-center items-center py-4 ${
        active ? "border-l-4 border-green-500" : ""
      }`}
    >
      {children}
    </div>
  );
}