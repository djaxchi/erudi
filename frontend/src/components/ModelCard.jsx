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
        <div className="flex flex-col items-center justify-center h-full text-center min-h-[200px]">
          <Plus className="w-12 h-12 text-white/60 mb-4" />
          <p className="text-white/60">Add New Model</p>
          <p className="text-white/40 text-sm mt-2">Browse available models</p>
        </div>
      </GradientBox>
    );
  }

  return (
    <GradientBox className="bg-[#1a1a1a]/60 backdrop-blur-sm border border-white/10">
      <div className="flex flex-col h-full">
        <div className="flex items-start justify-between mb-4">
          <h3 className="text-xl font-semibold text-white">{model.name}</h3>
          {type === "local" && (
            <div className={`w-3 h-3 rounded-full ${model.isOnline ? 'bg-green-500' : 'bg-red-500'}`}></div>
          )}
        </div>
        
        <div className="space-y-2 text-sm text-gray-300 mb-6">
          {/* Show description if available */}
          {model.description && (
            <p className="text-blue-300 font-medium mb-3">{model.description}</p>
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
        
        <div className="flex items-center gap-3 mt-auto">
          {type === "local" ? (
            <>
              <button 
                className="p-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
                onClick={() => onKnowledgeBase && onKnowledgeBase(model)}
                title="Knowledge Base"
              >
                <BookOpen className="w-5 h-5 text-white" />
              </button>
              <button 
                className="p-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
                onClick={() => onChat && onChat(model)}
                title="Chat"
              >
                <MessageSquare className="w-5 h-5 text-white" />
              </button>
            </>
          ) : (
            <>
              <button 
                className="p-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
                onClick={() => onDownload && onDownload(model)}
                title="Download"
              >
                <Download className="w-5 h-5 text-white" />
              </button>
              <button 
                className="p-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
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
