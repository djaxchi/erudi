import React, { useState } from "react";
import { Brain, MessageSquare, Swords, BookOpen, PanelLeftClose, PanelLeftOpen, Bug } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { useDownloadModal } from "../contexts/DownloadModalContext";

/**
 * Sidebar with icons that highlight based on the current route.
 */
export default function Sidebar({ 
  disabled = false, 
  onToggleSidebar, 
  showCollapsible = false, 
  collapsed = false,
  showBrainCollapsible = false,
  onToggleBrainSidebar,
  brainCollapsed = false
}) {
  const [isHovering, setIsHovering] = useState(false);
  const [isBrainHovering, setIsBrainHovering] = useState(false);
  const { isDownloading } = useDownloadModal();
  const location = useLocation();
  const isModelsActive =
    location.pathname === "/erudi/models" ||
    location.pathname === "/erudi/new-training";
  const isChatActive = location.pathname.startsWith("/erudi/chat") ||
    location.pathname.startsWith("/erudi/conversations");
  const isArenaActive = location.pathname === "/erudi/arena";
  const isKnowledgeBaseActive = location.pathname === "/erudi/attach_knowledge_base";

  return (
    <div
      className={`w-[4.8%] bg-[#121212] mt-0 flex flex-col items-center transition-opacity duration-200 ${
        disabled ? "opacity-50 pointer-events-none select-none" : ""
      }`}
    >
      {showBrainCollapsible ? (
        <button
          onClick={onToggleBrainSidebar}
          onMouseEnter={() => setIsBrainHovering(true)}
          onMouseLeave={() => setIsBrainHovering(false)}
          className={`w-full flex justify-center items-center py-6 border-l-4 ${
            isModelsActive ? "border-green-500" : "border-transparent"
          }`}
        >
          {isBrainHovering ? (
            brainCollapsed ? (
              <PanelLeftOpen
                className={`w-[60%] sm:w-[50%] xl:w-[35%] h-auto aspect-square ${
                  isModelsActive ? "text-green-400" : "text-gray-400"
                }`}
              />
            ) : (
              <PanelLeftClose
                className={`w-[60%] sm:w-[50%] xl:w-[35%] h-auto aspect-square ${
                  isModelsActive ? "text-green-400" : "text-gray-400"
                }`}
              />
            )
          ) : (
            <Brain
              className={`w-[60%] sm:w-[50%] xl:w-[35%] h-auto aspect-square ${
                isModelsActive ? "text-green-400" : "text-gray-400"
              }`}
            />
          )}
        </button>
      ) : (
        <Link
          to="/main_window/models"
          className={`w-full flex justify-center items-center py-6 border-l-4 ${
            isModelsActive ? "border-green-500" : "border-transparent"
          }`}
        >
          <Brain
            className={`w-[60%] sm:w-[50%] xl:w-[35%] h-auto aspect-square transition-colors duration-200 ${
              isModelsActive ? "text-green-400" : "text-gray-400 hover:text-green-400"
            }`}
          />
        </Link>
      )}

      {showCollapsible ? (
        <button
          onClick={onToggleSidebar}
          onMouseEnter={() => setIsHovering(true)}
          onMouseLeave={() => setIsHovering(false)}
          className={`w-full flex justify-center items-center py-6 border-l-4 ${
            isChatActive ? "border-green-500" : "border-transparent"
          }`}
        >
          {isHovering ? (
            collapsed ? (
              <PanelLeftOpen
                className={`w-[60%] sm:w-[50%] xl:w-[35%] h-auto aspect-square ${
                  isChatActive ? "text-green-400" : "text-gray-400"
                }`}
              />
            ) : (
              <PanelLeftClose
                className={`w-[60%] sm:w-[50%] xl:w-[35%] h-auto aspect-square ${
                  isChatActive ? "text-green-400" : "text-gray-400"
                }`}
              />
            )
          ) : (
            <MessageSquare
              className={`w-[60%] sm:w-[50%] xl:w-[35%] h-auto aspect-square ${
                isChatActive ? "text-green-400" : "text-gray-400"
              }`}
            />
          )}
        </button>
      ) : (
        <Link
          to="/main_window/chat"
          className={`w-full flex justify-center items-center py-6 border-l-4 ${
            isChatActive ? "border-green-500" : "border-transparent"
          }`}
        >
          <MessageSquare
            className={`w-[60%] sm:w-[50%] xl:w-[35%] h-auto aspect-square transition-colors duration-200 ${
              isChatActive ? "text-green-400" : "text-gray-400 hover:text-green-400"
            }`}
          />
        </Link>
      )}
      <Link
        to="/main_window/arena"
        className={`w-full flex justify-center items-center py-6 border-l-4 ${
          isArenaActive ? "border-green-500" : "border-transparent"
        }`}
      >
        <Swords
          className={`w-[60%] sm:w-[50%] xl:w-[35%] h-auto aspect-square transition-colors duration-200 ${
            isArenaActive ? "text-green-400" : "text-gray-400 hover:text-green-400"
          }`}
        />
      </Link>
      <Link
        to="/main_window/attach_knowledge_base"
        className={`w-full flex justify-center items-center py-6 border-l-4 ${
          isKnowledgeBaseActive ? "border-green-500" : "border-transparent"
        }`}
      >
        <BookOpen
          className={`w-[60%] sm:w-[50%] xl:w-[35%] h-auto aspect-square transition-colors duration-200 ${
            isKnowledgeBaseActive ? "text-green-400" : "text-gray-400 hover:text-green-400"
          }`}
        />
      </Link>

      {/* Bug Report Button - Bottom of sidebar */}
      <div className="flex-1" />
      {!isDownloading && (
        <button
          onClick={() => window.open('https://erudi.app/contact', '_blank')}
          className="w-full flex justify-center items-center py-4 border-l-4 border-transparent mb-4"
        >
          <Bug
            className="w-[60%] sm:w-[50%] xl:w-[35%] h-auto aspect-square transition-colors duration-200 text-gray-400 hover:text-red-400"
          />
        </button>
      )}

      
    </div>
  );}
