import React from "react";
import GradientBox from "./GradientBox";
import { Download, Info, BookOpen, MessageSquare, Plus } from "lucide-react";

export default function ModelCard({ 
  model,
  type = "base", // "base", "local", "add"
  onDownload,
  onInfo,
  onChat,
  onKnowledgeBase,
  onClick
}) {
  if (type === "add") {
    return (
      <GradientBox 
        className="bg-[#1a1a1a]/60 backdrop-blur-sm border border-white/10 border-dashed cursor-pointer hover:border-white/30 transition-colors"
        onClick={onDownload}
      >
        <div className="flex flex-col items-center justify-center h-full text-center min-h-[160px]">
          <Plus className="w-8 h-8 text-white/60 mb-3" />
          <p className="text-white/60 text-sm">Add New Model</p>
          <p className="text-white/40 text-xs mt-1">Browse available models</p>
        </div>
      </GradientBox>
    );
  }

  return (
    <GradientBox className="bg-[#1a1a1a]/60 backdrop-blur-sm border border-white/10">
      <div className="flex flex-col h-full">
        <div className="flex items-start justify-between mb-3">
          <h3 className="text-lg font-semibold text-white">{model.name}</h3>
          {type === "local" && (
            <div className={`w-2 h-2 rounded-full ${model.isOnline ? 'bg-green-500' : 'bg-red-500'}`}></div>
          )}
        </div>
        
        <div className="space-y-1 text-xs text-gray-300 mb-4">
          {/* Show description if available */}
          {model.description && (
            <p className="text-blue-300 font-medium mb-2 text-xs">{model.description}</p>
          )}
          
          {/* Core metadata */}
          <p>Size: {model.size}</p>
          
          {/* Additional metadata for remote models */}
          {type !== "local" && (
            <>
              {model.downloads && model.downloads !== "Unknown" && (
                <p>Downloads: {model.downloads}</p>
              )}
              {model.likes && model.likes !== "Unknown" && (
                <p>Likes: {model.likes}</p>
              )}
              {model.author && model.author !== "Unknown" && (
                <p>Author: {model.author}</p>
              )}
              {model.library && model.library !== "Unknown" && (
                <p>Library: {model.library}</p>
              )}
            </>
          )}
          
          {/* Local model specific info */}
          {type === "local" && model.lastUpdate && model.lastUpdate !== "Unknown" && (
            <p>Last update: {model.lastUpdate}</p>
          )}
        </div>
        
        <div className="flex items-center gap-2 mt-auto">
          {type === "local" ? (
            <>
              <button 
                className="p-1 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
                onClick={() => onKnowledgeBase && onKnowledgeBase(model)}
                title="Knowledge Base"
              >
                <BookOpen className="w-4 h-4 text-white" />
              </button>
              <button 
                className="p-1 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
                onClick={() => onChat && onChat(model)}
                title="Chat"
              >
                <MessageSquare className="w-4 h-4 text-white" />
              </button>
            </>
          ) : (
            <>
              <button 
                className="p-1 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
                onClick={() => onDownload && onDownload(model)}
                title="Download"
              >
                <Download className="w-5 h-5 text-white" />
              </button>
              <button 
                className="p-1 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
                onClick={() => onInfo && onInfo(model)}
                title="Info"
              >
                <Info className="w-5 h-5 text-white" />
              </button>
            </>
          )}
        </div>
      </div>
    </GradientBox>
  );
}
