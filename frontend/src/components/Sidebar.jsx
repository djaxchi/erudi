import React from "react";
import { Brain, MessageSquare, Swords} from "lucide-react";
import { Link, useLocation } from "react-router-dom";

/**
 * Sidebar with icons that highlight based on the current route.
 */
export default function Sidebar({ disabled = false }) {
  const location = useLocation();
  const isModelsActive =
    location.pathname === "/main_window/models" ||
    location.pathname === "/main_window/new-training";
  const isChatActive = location.pathname.startsWith("/main_window/chat") ||
    location.pathname.startsWith("/main_window/conversations");
  const isArenaActive = location.pathname === "/main_window/arena";

  return (
    <div
      className={`w-[4.8%] bg-[#121212] flex flex-col items-center transition-opacity duration-200 ${
        disabled ? "opacity-50 pointer-events-none select-none" : ""
      }`}
    >
      <Link
        to="/main_window/models"
        className={`w-full flex justify-center items-center py-4 border-l-4 ${
          isModelsActive ? "border-green-500" : "border-transparent"
        }`}
      >
      <Brain
  className={`w-[60%] sm:w-[50%] xl:w-[35%] h-auto aspect-square ${
    isModelsActive ? "text-green-400" : "text-gray-400"
  }`}
/>

      </Link>

      <Link
        to="/main_window/chat"
        className={`w-full flex justify-center items-center py-4 border-l-4 ${
          isChatActive ? "border-green-500" : "border-transparent"
        }`}
      >
        <MessageSquare
          className={`w-[60%] sm:w-[50%] xl:w-[35%] h-auto aspect-square  ${
            isChatActive ? "text-green-400" : "text-gray-400"
          }`}
        />
      </Link>
      <Link
        to="/main_window/arena"
        className={`w-full flex justify-center items-center py-4 border-l-4 ${
          isArenaActive ? "border-green-500" : "border-transparent"
        }`}
      >
        <Swords
          className={`w-[60%] sm:w-[50%] xl:w-[35%] h-auto aspect-square ${
            isArenaActive ? "text-green-400" : "text-gray-400"
          }`}
        />
      </Link>
    </div>
  );

}
