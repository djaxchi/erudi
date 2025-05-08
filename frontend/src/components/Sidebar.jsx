import React from "react";
import { Brain, MessageSquare } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

/**
 * Sidebar with icons that highlight based on the current route.
 */
export default function Sidebar() {
  const location = useLocation();
  const isModelsActive =
    location.pathname === "/main_window/models" ||
    location.pathname === "/main_window/new-training";
  const isChatActive = location.pathname.startsWith("/main_window/chat");

  return (
    <div className="w-16 bg-[#121212] flex flex-col items-center">
      <Link
        to="/main_window/models"
        className={`w-full flex justify-center items-center py-4 ${
          isModelsActive ? "border-l-4 border-green-500" : ""
        }`}
      >
        <Brain
          className={`w-6 h-6 ${
            isModelsActive ? "text-green-400" : "text-gray-400"
          }`}
        />
      </Link>

      <Link
        to="/main_window/chat"
        className={`w-full flex justify-center items-center py-4 ${
          isChatActive ? "border-l-4 border-green-500" : ""
        }`}
      >
        <MessageSquare
          className={`w-6 h-6 ${
            isChatActive ? "text-green-400" : "text-gray-400"
          }`}
        />
      </Link>
    </div>
  );
}
