import React from "react";
import PropTypes from "prop-types";
import GradientBox from "./GradientBox";
import { Download, Info, BookOpen, MessageSquare, Plus, Trash2 } from "lucide-react";
import { useDownloadModal } from "../contexts/DownloadModalContext";

/**
 * ModelCard component - displays model information with actions
 * @param {Object} model - Model object with name, size, description, etc.
 * @param {string} type - Card type: "base" (available), "local" (installed), "add" (add new)
 * @param {Function} onDownload - Callback when download button clicked
 * @param {Function} onInfo - Callback when info button clicked
 * @param {Function} onChat - Callback when chat button clicked
 * @param {Function} onKnowledgeBase - Callback when knowledge base button clicked
 * @param {Function} onDelete - Callback when delete button clicked
 * @param {Function} onClick - Callback when card clicked
 */
function ModelCard({
  model,
  type = "base",
  onDownload,
  onInfo,
  onChat,
  onKnowledgeBase,
  onDelete,
  onClick: _onClick,
}) {
  const { open } = useDownloadModal();
  const unavailable = model?.runnable === false;
  const handleDownload = () => {
    if (model) {
      open(model, {
        onComplete: () => onDownload && onDownload(model),
        onError: (error) => console.error("Download error:", error),
      });
    } else if (type === "add" && onDownload) {
      onDownload();
    }
  };

  if (type === "add") {
    return (
      <GradientBox
        className="bg-[#1a1a1a]/60 backdrop-blur-sm border border-white/10 border-dashed cursor-pointer hover:border-white/30 transition-colors"
        onClick={handleDownload}
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
          {unavailable && type !== "local" && (
            <span className="ml-2 flex-shrink-0 text-[10px] uppercase tracking-wide text-amber-500/80 border border-amber-500/30 rounded px-1.5 py-0.5">
              Unavailable on your hardware
            </span>
          )}
          {type === "local" && (
            <button
              className="p-1 bg-red-500/20 hover:bg-red-500/40 rounded-lg transition-colors ml-8"
              onClick={(e) => {
                e.stopPropagation();
                onDelete && onDelete(model);
              }}
              title="Delete model"
            >
              <Trash2 className="w-4 h-4 text-red-400" />
            </button>
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
              {model.likes && model.likes !== "Unknown" && <p>Likes: {model.likes}</p>}
              {model.author && model.author !== "Unknown" && <p>Author: {model.author}</p>}
              {model.library && model.library !== "Unknown" && <p>Library: {model.library}</p>}
            </>
          )}

          {/* Local model specific info */}
          {type === "local" && model.lastUpdate && model.lastUpdate !== "Unknown" && (
            <>
              <p>Parameters: {model.parameters}</p>
              <p>Last update: {model.lastUpdate}</p>
            </>
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
              <button
                className="p-1 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
                onClick={() => onInfo && onInfo(model)}
                title="Info"
              >
                <Info className="w-4 h-4 text-white" />
              </button>
            </>
          ) : (
            <>
              <button
                className={`p-1 rounded-lg transition-colors ${unavailable ? "bg-white/5 opacity-40 cursor-not-allowed" : "bg-white/10 hover:bg-white/20"}`}
                onClick={() => !unavailable && onDownload && onDownload(model)}
                disabled={unavailable}
                title={unavailable ? "Unavailable on your hardware" : "Download"}
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

ModelCard.propTypes = {
  model: PropTypes.shape({
    name: PropTypes.string.isRequired,
    size: PropTypes.string,
    description: PropTypes.string,
    downloads: PropTypes.string,
    likes: PropTypes.string,
    author: PropTypes.string,
    library: PropTypes.string,
    parameters: PropTypes.string,
    lastUpdate: PropTypes.string,
    runnable: PropTypes.bool,
  }).isRequired,
  type: PropTypes.oneOf(["base", "local", "add"]),
  onDownload: PropTypes.func,
  onInfo: PropTypes.func,
  onChat: PropTypes.func,
  onKnowledgeBase: PropTypes.func,
  onDelete: PropTypes.func,
  onClick: PropTypes.func,
};

export default ModelCard;
