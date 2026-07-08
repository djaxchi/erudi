import React, { useState, useRef, useEffect } from "react";
import PropTypes from "prop-types";
import { Upload, File, X, Plus, Folder, FolderPlus, AlertTriangle } from "lucide-react";
import GradientBox from "./GradientBox";
import { createLogger } from "../utils/logger";
import { isSupportedKbFile, KB_ACCEPT_ATTR } from "../utils/kbFormats";
const log = createLogger("DragDropArea");

// Upper bound on how many supported files a single add (drop or pick) may
// contribute. A dropped/selected folder can expand into thousands of files;
// past this cap we keep the first N and surface a visible warning rather than
// silently flood the ingestion queue.
const MAX_FILES_PER_ADD = 500;

/**
 * Drag‑and‑drop zone with optional file/folder picker.
 *
 * Accepts plain files, multi-file selections, AND folders — dropped folders are
 * traversed recursively in the renderer via the DataTransferItem entry API
 * (`webkitGetAsEntry` + `createReader().readEntries`), and the folder picker
 * uses a `webkitdirectory` input whose FileList is already recursive. Every
 * candidate is run through the same pipeline: unsupported-format filter → cap →
 * path resolution (path-less entries are dropped, never forwarded). Rejections
 * are counted and shown inline instead of failing silently at ingestion (#227).
 *
 * @param {function(string[])} onFilesAdded – receives absolute paths of dropped/selected files.
 */
export default function DragDropArea({ onFilesAdded }) {
  const [isOver, setIsOver] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [, setDragCounter] = useState(0);
  // Inline warning for the most recent add: { unsupported, capped, missingPath }
  // (all counts), or null when the add had nothing to flag.
  const [notice, setNotice] = useState(null);
  const inputRef = useRef(null);
  const folderInputRef = useRef(null);

  // `webkitdirectory`/`directory` aren't React-known props (they'd trip
  // react/no-unknown-property and inconsistent casing across DOM impls), so set
  // them imperatively once the folder input is mounted.
  useEffect(() => {
    const el = folderInputRef.current;
    if (el) {
      el.setAttribute("webkitdirectory", "");
      el.setAttribute("directory", "");
    }
  }, []);

  /* -------------------------------- helpers -------------------------------- */
  const isAllowedFileType = (fileName) => isSupportedKbFile(fileName);

  // Resolve the absolute path of a File. In Electron the preload bridge wraps
  // webUtils.getPathForFile; outside it (tests, plain browser) we can only try
  // file.path. NOTE: never fall back to file.name — a bare name is not a path
  // and is exactly the empty/bogus value gap 2 exists to reject.
  const resolvePath = (file) => {
    if (window.electron?.getFilePath) {
      return window.electron.getFilePath(file);
    }
    return file.path || "";
  };

  // Promise-wrap FileSystemFileEntry.file (callback API). Resolves null on error
  // so one unreadable entry can't reject the whole traversal.
  const entryToFile = (entry) =>
    new Promise((resolve) => {
      entry.file(
        (file) => resolve(file),
        () => resolve(null)
      );
    });

  // Promise-wrap FileSystemDirectoryReader.readEntries. readEntries yields the
  // directory in BATCHES (Chromium caps at ~100 per call), so we must loop until
  // a call returns an empty array — a classic gotcha that otherwise silently
  // truncates large folders.
  const readAllEntries = (reader) =>
    new Promise((resolve) => {
      const collected = [];
      const readBatch = () => {
        reader.readEntries(
          (batch) => {
            if (!batch || batch.length === 0) {
              resolve(collected);
              return;
            }
            collected.push(...batch);
            readBatch();
          },
          () => resolve(collected)
        );
      };
      readBatch();
    });

  // Recursively flatten a FileSystemEntry into the File objects it contains.
  const collectFilesFromEntry = async (entry) => {
    if (!entry) return [];
    if (entry.isFile) {
      const file = await entryToFile(entry);
      return file ? [file] : [];
    }
    if (entry.isDirectory) {
      const entries = await readAllEntries(entry.createReader());
      const nested = await Promise.all(entries.map(collectFilesFromEntry));
      return nested.flat();
    }
    return [];
  };

  // Shared ingestion pipeline for every entry point (drop, file pick, folder
  // pick): filter unsupported formats, cap the batch, resolve paths (dropping
  // path-less entries), record what was skipped, then commit the survivors.
  const addFiles = (fileList) => {
    const files = Array.from(fileList || []);

    // 1. Format filter.
    const supported = [];
    let unsupportedCount = 0;
    for (const file of files) {
      const fileName = file.name || file.path?.split(/[/\\]/).pop() || "";
      if (isAllowedFileType(fileName)) {
        supported.push(file);
      } else {
        unsupportedCount += 1;
        log.warn(`File "${fileName}" rejected: unsupported format (allowed: ${KB_ACCEPT_ATTR})`);
      }
    }

    // 2. Safety cap.
    let cappedCount = 0;
    let capped = supported;
    if (supported.length > MAX_FILES_PER_ADD) {
      cappedCount = supported.length - MAX_FILES_PER_ADD;
      capped = supported.slice(0, MAX_FILES_PER_ADD);
      log.warn(`Selection capped at ${MAX_FILES_PER_ADD}; ${cappedCount} file(s) ignored`);
    }

    // 3. Path resolution — a falsy/whitespace path must never reach selectedFiles.
    const paths = [];
    let missingPathCount = 0;
    for (const file of capped) {
      const path = resolvePath(file);
      if (path && path.trim()) {
        paths.push(path);
      } else {
        missingPathCount += 1;
        log.warn(`Could not resolve a path for "${file.name || "(unnamed)"}"; entry dropped`);
      }
    }

    // 4. Surface rejections inline (or clear a stale notice).
    if (unsupportedCount || cappedCount || missingPathCount) {
      setNotice({
        unsupported: unsupportedCount,
        capped: cappedCount,
        missingPath: missingPathCount,
      });
    } else {
      setNotice(null);
    }

    // 5. Commit survivors.
    if (paths.length) {
      const newFiles = [...selectedFiles, ...paths];
      setSelectedFiles(newFiles);
      onFilesAdded?.(newFiles);
    }
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
  const openFolderPicker = () => folderInputRef.current?.click();

  const removeFile = (indexToRemove) => {
    const updatedFiles = selectedFiles.filter((_, index) => index !== indexToRemove);
    setSelectedFiles(updatedFiles);

    // Call the parent callback with the updated list
    if (onFilesAdded) {
      onFilesAdded(updatedFiles);
    }
  };

  /* ------------------------------ event handlers --------------------------- */
  const handleSelect = (e) => {
    addFiles(e.target.files);
    e.target.value = ""; // reset picker so re-selecting the same path re-fires
  };

  const handleDrop = async (e) => {
    log.log("📦 REACT DROP EVENT triggered!", e.dataTransfer.files);
    e.preventDefault();
    setDragCounter(0);
    setIsOver(false);

    // Prefer the entry API so dropped folders can be walked. webkitGetAsEntry()
    // must be called SYNCHRONOUSLY while the event is live — collect every entry
    // first, then traverse (the FileSystemEntry handles stay valid across await).
    const items = e.dataTransfer.items;
    let files = null;
    if (items && items.length) {
      const entries = Array.from(items)
        .map((item) =>
          typeof item.webkitGetAsEntry === "function" ? item.webkitGetAsEntry() : null
        )
        .filter(Boolean);
      if (entries.length) {
        const collected = await Promise.all(entries.map(collectFilesFromEntry));
        files = collected.flat();
      }
    }

    // Fallback: no usable entry API (older surface / plain file list).
    if (files === null) {
      files = Array.from(e.dataTransfer.files);
    }

    log.log("Collected dropped files:", files.length);
    addFiles(files);
  };

  /* ---------------------------------- UI ---------------------------------- */
  const noticeParts = [];
  if (notice?.unsupported) {
    noticeParts.push(
      `${notice.unsupported} unsupported file${notice.unsupported > 1 ? "s" : ""} skipped`
    );
  }
  if (notice?.capped) {
    noticeParts.push(`capped at ${MAX_FILES_PER_ADD} files (${notice.capped} more ignored)`);
  }
  if (notice?.missingPath) {
    noticeParts.push(
      `couldn't resolve a path for ${notice.missingPath} item${notice.missingPath > 1 ? "s" : ""}`
    );
  }

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
      onDrop={handleDrop}
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
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              openFolderPicker();
            }}
            className="inline-flex items-center gap-1.5 text-white/60 text-sm hover:text-white transition"
          >
            <FolderPlus className="w-4 h-4" />
            or select a folder
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
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  openFolderPicker();
                }}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#3A3A3A] border border-gray-600/50 text-white text-xs font-medium hover:bg-[#404040] hover:border-gray-500/70 transition-all duration-200"
              >
                <FolderPlus className="w-3.5 h-3.5" />
                Add Folder
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  openPicker();
                }}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#3A3A3A] border border-gray-600/50 text-white text-xs font-medium hover:bg-[#404040] hover:border-gray-500/70 transition-all duration-200"
              >
                <Plus className="w-3.5 h-3.5" />
                Add More
              </button>
            </div>
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

      {/* Inline rejection notice (unsupported / capped / path-less) */}
      {noticeParts.length > 0 && (
        <div
          role="alert"
          className="absolute bottom-3 left-1/2 -translate-x-1/2 max-w-[92%] flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-500/15 border border-amber-500/30 text-amber-200 text-xs"
        >
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span className="truncate">{noticeParts.join(" · ")}</span>
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

      {/* hidden folder input (webkitdirectory set imperatively above); its
          FileList is already the folder's files, recursively. */}
      <input
        ref={folderInputRef}
        type="file"
        multiple
        onChange={handleSelect}
        style={{ display: "none" }}
      />
    </GradientBox>
  );
}

DragDropArea.propTypes = {
  onFilesAdded: PropTypes.func.isRequired,
};
