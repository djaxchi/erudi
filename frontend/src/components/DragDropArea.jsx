import React, { useState, useRef } from "react";
import PropTypes from "prop-types";
import { Upload, File, X, Plus, Folder } from "lucide-react";
import GradientBox from "./GradientBox";
import { createLogger } from "../utils/logger";
import { isSupportedKbFile, KB_ACCEPT_ATTR } from "../utils/kbFormats";
const log = createLogger("DragDropArea");

/**
 * Drag‑and‑drop zone with optional file picker.
 *
 * @param {function(string[])} onFilesAdded – receives absolute paths of dropped/selected files.
 */
export default function DragDropArea({ onFilesAdded }) {
  const [isOver, setIsOver] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [, setDragCounter] = useState(0);
  const inputRef = useRef(null);

  /* -------------------------------- helpers -------------------------------- */
  const isAllowedFileType = (fileName) => isSupportedKbFile(fileName);

  const extractPaths = (fileList) => {
    return Array.from(fileList)
      .filter((file) => {
        const fileName = file.name || file.path?.split(/[/\\]/).pop() || "";
        const isAllowed = isAllowedFileType(fileName);
        if (!isAllowed) {
          log.warn(`File "${fileName}" rejected: unsupported format (allowed: ${KB_ACCEPT_ATTR})`);
        }
        return isAllowed;
      })
      .map((file) => {
        log.log("Processing file:", file);

        // Use the preload API if available
        if (window.electron?.getFilePath) {
          log.log("Using window.electron.getFilePath");
          const path = window.electron.getFilePath(file);
          log.log("Got path from electron API:", path);
          return path;
        }

        // Fallback to direct access
        log.log("Using direct file.path access");
        return file.path || file.name;
      });
  };

  const getFileName = (path) => {
    if (!path) {
      return "";
    }
    // Handle both Windows and Unix path separators
    const parts = path.split(/[/\\]/);
    return parts[parts.length - 1] || path;
  };

  const getFileType = (path) => {
    if (!path) {
      return "other";
    }
    const fileName = getFileName(path);

    // Check if it's a folder (no file extension)
    if (!fileName.includes(".")) {
      return "Folder";
    }

    const extension = fileName.split(".").pop()?.toLowerCase();
    return extension ? extension.toUpperCase() : "Other";
  };

  const openPicker = () => inputRef.current?.click();

  const removeFile = (indexToRemove) => {
    const updatedFiles = selectedFiles.filter((_, index) => index !== indexToRemove);
    setSelectedFiles(updatedFiles);

    // Call the parent callback with the updated list
    if (onFilesAdded) {
      onFilesAdded(updatedFiles);
    }
  };

  const addMoreFiles = () => {
    inputRef.current?.click();
  };

  /* ------------------------------ event handlers --------------------------- */
  const handleSelect = (e) => {
    const paths = extractPaths(e.target.files);
    if (paths.length) {
      const newFiles = [...selectedFiles, ...paths];
      setSelectedFiles(newFiles);
      onFilesAdded?.(newFiles);
    }
    e.target.value = ""; // reset picker
  };

  /* ---------------------------------- UI ---------------------------------- */
  return (
    <GradientBox
      data-drag-drop-area="true"
      className={`h-full min-h-[230px] flex items-start justify-center cursor-pointer select-none transition border-2 border-dashed rounded-4xl ${
        isOver ? "border-emerald-400 bg-emerald-400/10" : "border-white/20"
      }`}
      onDragOver={(e) => {
        log.log("🔄 REACT DRAG OVER triggered");
        e.preventDefault(); // required for windows
        e.dataTransfer.dropEffect = "copy"; // ← Chrome/Edge need this line
      }}
      onDragEnter={(e) => {
        log.log("➡️ REACT DRAG ENTER triggered");
        e.preventDefault(); // required for Windows
        setDragCounter((prev) => prev + 1);
        setIsOver(true);
      }}
      onDragLeave={(e) => {
        log.log("⬅️ REACT DRAG LEAVE triggered");
        e.preventDefault();
        setDragCounter((prev) => {
          const newCounter = prev - 1;
          if (newCounter === 0) {
            setIsOver(false);
          }
          return newCounter;
        });
      }}
      onDrop={(e) => {
        log.log("📦 REACT DROP EVENT triggered!", e.dataTransfer.files);
        e.preventDefault();
        setDragCounter(0);
        setIsOver(false);

        const files = Array.from(e.dataTransfer.files);
        log.log("Files array:", files);

        const paths = extractPaths(e.dataTransfer.files);
        log.log("Extracted paths:", paths);

        if (paths.length) {
          const newFiles = [...selectedFiles, ...paths];
          log.log("New files array:", newFiles);
          setSelectedFiles(newFiles);
          onFilesAdded?.(newFiles);
        }
      }}
      onClick={selectedFiles.length === 0 ? openPicker : undefined}
    >
      {selectedFiles.length === 0 ? (
        /* Initial state - no files selected */
        <div className="flex flex-col items-center text-center gap-2 pt-8">
          <Upload className="w-14 h-14 text-white" />
          <p className="text-white text-xl font-medium">Drag and Drop</p>
          <span className="text-white/60 text-base">or</span>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              openPicker();
            }}
            className="text-emerald-400 text-base font-semibold underline-offset-4 hover:underline"
          >
            Browse files
          </button>
        </div>
      ) : (
        /* Files selected state - show file list */
        <div className="w-full h-full p-4 flex flex-col max-h-[400px]">
          {" "}
          {/* Add max-h constraint */}
          {/* Header with file count and add more button */}
          <div className="flex items-center justify-between mb-4 flex-shrink-0">
            {" "}
            {/* Add flex-shrink-0 */}
            <h3 className="text-white text-lg font-medium">
              Selected Files ({selectedFiles.length})
            </h3>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                addMoreFiles();
              }}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#3A3A3A] border border-gray-600/50 text-white text-xs font-medium hover:bg-[#404040] hover:border-gray-500/70 transition-all duration-200"
            >
              <Plus className="w-3.5 h-3.5" />
              Add More
            </button>
          </div>
          {/* File list - scrollable with fixed height */}
          <div className="flex-1 overflow-y-auto space-y-2 max-h-[300px] custom-scroll">
            {selectedFiles.map((filePath, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/10 group hover:bg-white/10 transition flex-shrink-0" // Add flex-shrink-0
              >
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  {getFileType(filePath) === "Folder" ? (
                    <Folder className="w-5 h-5 text-blue-400 flex-shrink-0" />
                  ) : (
                    <File className="w-5 h-5 text-emerald-400 flex-shrink-0" />
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <p className="text-white text-sm font-medium truncate">
                        {getFileName(filePath)}
                      </p>
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-medium ${
                          getFileType(filePath) === "PDF"
                            ? "bg-red-500/20 text-red-300 border border-red-500/30"
                            : getFileType(filePath) === "TXT"
                              ? "bg-blue-500/20 text-blue-300 border border-blue-500/30"
                              : getFileType(filePath) === "Folder"
                                ? "bg-blue-500/20 text-blue-300 border border-blue-500/30"
                                : "bg-gray-500/20 text-gray-300 border border-gray-500/30"
                        }`}
                      >
                        {getFileType(filePath)}
                      </span>
                    </div>
                    <p
                      className="text-white/60 text-xs truncate"
                      style={{ direction: "rtl", textAlign: "left" }}
                    >
                      {filePath}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    removeFile(index);
                  }}
                  className="p-1 rounded-full text-white/60 hover:text-red-400 hover:bg-red-400/20 transition opacity-0 group-hover:opacity-100"
                  aria-label="Remove file"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* hidden native file input */}
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={KB_ACCEPT_ATTR}
        onChange={handleSelect}
        style={{ display: "none" }}
      />
    </GradientBox>
  );
}

DragDropArea.propTypes = {
  onFilesAdded: PropTypes.func.isRequired,
};
