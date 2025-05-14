import React from "react";
import { Brain, MessageSquare, Swords} from "lucide-react";
import { Link, useLocation } from "react-router-dom";

/**
 * Sidebar with icons that highlight based on the current route.
 */
export default function Sidebar() {
  const location = useLocation();
  const isModelsActive =
    location.pathname === "/main_window/models" ||
    location.pathname === "/main_window/new-training";
  const isChatActive = location.pathname.startsWith("/main_window/chat") ||
    location.pathname.startsWith("/main_window/conversations");
  const isArenaActive = location.pathname === "/main_window/arena";

  return (
    <div className="w-[8%] bg-[#121212] flex flex-col items-center">
      <Link
        to="/main_window/models"
        className={`w-full flex justify-center items-center py-4 ${
          isModelsActive ? "border-l-4 border-green-500" : ""
        }`}
      >
      <Brain
  className={`w-[50%] sm:w-[40%] xl:w-[25%] h-auto aspect-square ${
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
          className={`w-[50%] sm:w-[40%] xl:w-[25%] h-auto aspect-square  ${
            isChatActive ? "text-green-400" : "text-gray-400"
          }`}
        />
      </Link>
      <Link
        to="/main_window/arena"
        className={`w-full flex justify-center items-center py-4 ${
          isArenaActive ? "border-l-4 border-green-500" : ""
        }`}
      >
        <Swords
          className={`w-6 h-6 ${
            isArenaActive ? "text-green-400" : "text-gray-400"
          }`}
        />
      </Link>
    </div>
  );
}
