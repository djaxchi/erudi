import React, { useState, useRef } from "react";
import { Upload, File, X, Plus, Folder } from "lucide-react";
import GradientBox from "./GradientBox";

/**
 * Drag‑and‑drop zone with optional file picker.
 *
 * @param {function(string[])} onFilesAdded – receives absolute paths of dropped/selected files.
 */
export default function DragDropArea({ onFilesAdded }) {
  const [isOver, setIsOver] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [dragCounter, setDragCounter] = useState(0); 
  const inputRef = useRef(null);

  /* -------------------------------- helpers -------------------------------- */
  const isAllowedFileType = (fileName) => {
    const allowedExtensions = ['.pdf', '.txt'];
    const extension = '.' + fileName.split('.').pop()?.toLowerCase();
    return allowedExtensions.includes(extension);
  };

  const extractPaths = (fileList) => {
    const filesArray = Array.from(fileList);
    const validPaths = [];
    
    console.log('🔍 Checking window.electron availability:', {
      hasElectron: !!window.electron,
      hasGetFilePath: !!window.electron?.getFilePath,
      electronKeys: window.electron ? Object.keys(window.electron) : 'N/A'
    });
    
    filesArray.forEach((file) => {
      console.log('🔍 Processing file object:', {
        name: file.name,
        path: file.path,
        type: file.type,
        webkitRelativePath: file.webkitRelativePath,
        allKeys: Object.keys(file)
      });
      
      const fileName = file.name || file.path?.split(/[/\\]/).pop() || '';
      
      // Check if it's a folder (no extension or has webkitRelativePath indicating folder structure)
      const hasExtension = fileName.includes('.');
      const isFolder = !hasExtension || (file.webkitRelativePath && file.webkitRelativePath.includes('/'));
      
      // If it's a file, check if it's allowed
      if (hasExtension && !isFolder) {
        const isAllowed = isAllowedFileType(fileName);
        if (!isAllowed) {
          console.warn(`File "${fileName}" rejected: only PDF and TXT files are allowed`);
          return;
        }
      }
      
      // For folders or allowed files, extract the path
      let path;
      
      // Try webUtils API through electron
      if (window.electron?.getFilePath) {
        console.log('✅ Using window.electron.getFilePath');
        try {
          path = window.electron.getFilePath(file);
          console.log('📍 Got path from electron API:', path);
        } catch (error) {
          console.error('❌ Error calling getFilePath:', error);
          path = file.path || file.name;
        }
      } else {
        // Fallback to direct access
        console.log('⚠️ Using fallback file.path access');
        console.log('⚠️ window.electron exists?', !!window.electron);
        console.log('⚠️ window.electron.getFilePath exists?', !!window.electron?.getFilePath);
        path = file.path || file.name;
        console.log('📍 Got fallback path:', path);
      }
      
      // Only add allowed file types to the list
      if (hasExtension && isAllowedFileType(fileName)) {
        console.log(`✅ Adding file: ${path}`);
        validPaths.push(path);
      } else if (!hasExtension) {
        // It's a folder, add it
        console.log(`📁 Adding folder: ${path}`);
        validPaths.push(path);
      }
    });
    
    console.log('📦 Final valid paths:', validPaths);
    return validPaths;
  };

  const getFileName = (path) => {
    if (!path) return "";
    // Handle both Windows and Unix path separators
    const parts = path.split(/[/\\]/);
    return parts[parts.length - 1] || path;
  };

  const getFileType = (path) => {
    if (!path) return "other";
    const fileName = getFileName(path);
    
    // Check if it's a folder (no file extension)
    if (!fileName.includes('.')) {
      return 'Folder';
    }
    
    const extension = fileName.split('.').pop()?.toLowerCase();
    
    switch (extension) {
      case 'pdf':
        return 'PDF';
      case 'txt':
        return 'TXT';
      default:
        return 'Other';
    }
  };

  const openPicker = async () => {
    // Use Electron dialog if available (works in both dev and production)
    if (window.electron?.openFilesAndFolders) {
      try {
        console.log('🔵 Opening file/folder dialog...');
        const paths = await window.electron.openFilesAndFolders();
        console.log('📂 Raw paths from dialog:', paths);
        console.log('📂 Paths type:', typeof paths, 'Is array:', Array.isArray(paths));
        console.log('📂 Paths length:', paths?.length);
        console.log('📂 First path:', paths?.[0]);
        
        if (paths && paths.length > 0) {
          const newFiles = [...selectedFiles, ...paths];
          console.log('📂 Combined files array:', newFiles);
          setSelectedFiles(newFiles);
          onFilesAdded?.(newFiles);
        }
      } catch (error) {
        console.error('❌ Error opening file dialog:', error);
        // Fall back to native input
        inputRef.current?.click();
      }
    } else {
      // Fallback to native input (shouldn't happen in Electron)
      console.warn('⚠️ Electron dialog API not available, using native input');
      inputRef.current?.click();
    }
  };

  const removeFile = (indexToRemove) => {
    const updatedFiles = selectedFiles.filter((_, index) => index !== indexToRemove);
    setSelectedFiles(updatedFiles);
    
    // Call the parent callback with the updated list
    if (onFilesAdded) {
      onFilesAdded(updatedFiles);
    }
  };

  const addMoreFiles = async () => {
    // Use Electron dialog if available
    if (window.electron?.openFilesAndFolders) {
      try {
        const paths = await window.electron.openFilesAndFolders();
        console.log('📂 Got paths from dialog:', paths);
        
        if (paths && paths.length > 0) {
          const newFiles = [...selectedFiles, ...paths];
          setSelectedFiles(newFiles);
          onFilesAdded?.(newFiles);
        }
      } catch (error) {
        console.error('❌ Error opening file dialog:', error);
        // Fall back to native input
        inputRef.current?.click();
      }
    } else {
      // Fallback to native input
      inputRef.current?.click();
    }
  };

  /* ------------------------------ event handlers --------------------------- */
  const handleSelect = async (e) => {
    // In Electron, prefer using the dialog API instead of the native file input
    // because the native input doesn't provide absolute paths
    console.warn('⚠️ Native file input used - this may not provide absolute paths in Electron');
    
    const paths = extractPaths(e.target.files);
    if (paths.length) {
      const newFiles = [...selectedFiles, ...paths];
      setSelectedFiles(newFiles);
      onFilesAdded?.(newFiles);
    }
    e.target.value = ""; // reset picker
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragCounter(0);
    setIsOver(false);
    
    console.log('🎯 DROP EVENT - dataTransfer.files:', e.dataTransfer.files);
    console.log('🎯 DROP EVENT - files count:', e.dataTransfer.files.length);
    
    const paths = extractPaths(e.dataTransfer.files);
    console.log('🎯 DROP EVENT - extracted paths:', paths);
    
    if (paths.length) {
      const newFiles = [...selectedFiles, ...paths];
      console.log('🎯 DROP EVENT - final newFiles array:', newFiles);
      setSelectedFiles(newFiles);
      onFilesAdded?.(newFiles);
    }
  };

  /* ---------------------------------- UI ---------------------------------- */
  return (
    <GradientBox
      data-drag-drop-area="true"
      className={`h-full min-h-[230px] flex items-start justify-center cursor-pointer select-none transition border-2 border-dashed rounded-4xl ${
        isOver ? "border-emerald-400 bg-emerald-400/10" : "border-white/20"
      }`}
      onDragOver={(e) => {
        console.log('🔄 REACT DRAG OVER triggered');
        e.preventDefault(); // required for windows
        e.dataTransfer.dropEffect = 'copy'; // ← Chrome/Edge need this line
      }}
      onDragEnter={(e) => {
        console.log('➡️ REACT DRAG ENTER triggered');
        e.preventDefault(); // required for Windows
        setDragCounter(prev => prev + 1);
        setIsOver(true);
      }}
      onDragLeave={(e) => {
        console.log('⬅️ REACT DRAG LEAVE triggered');
        e.preventDefault();
        setDragCounter(prev => {
          const newCounter = prev - 1;
          if (newCounter === 0) {
            setIsOver(false);
          }
          return newCounter;
        });
      }}
      onDrop={(e) => {
        console.log('📦 REACT DROP EVENT triggered!', e.dataTransfer.files);
        e.preventDefault();
        setDragCounter(0);
        setIsOver(false);
        
        const files = Array.from(e.dataTransfer.files);
        console.log('Files array:', files);
        
        const paths = extractPaths(e.dataTransfer.files);
        console.log('Extracted paths:', paths);
        
        if (paths.length) {
          const newFiles = [...selectedFiles, ...paths];
          console.log('New files array:', newFiles);
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
        <div className="w-full h-full p-4 flex flex-col max-h-[400px]"> {/* Add max-h constraint */}
          {/* Header with file count and add more button */}
          <div className="flex items-center justify-between mb-4 flex-shrink-0"> {/* Add flex-shrink-0 */}
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
                  {getFileType(filePath) === 'Folder' ? (
                    <Folder className="w-5 h-5 text-blue-400 flex-shrink-0" />
                  ) : (
                    <File className="w-5 h-5 text-emerald-400 flex-shrink-0" />
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <p className="text-white text-sm font-medium truncate">
                        {getFileName(filePath)}
                      </p>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                        getFileType(filePath) === 'PDF' 
                          ? 'bg-red-500/20 text-red-300 border border-red-500/30'
                          : getFileType(filePath) === 'TXT'
                          ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                          : getFileType(filePath) === 'Folder'
                          ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                          : 'bg-gray-500/20 text-gray-300 border border-gray-500/30'
                      }`}>
                        {getFileType(filePath)}
                      </span>
                    </div>
                    <p className="text-white/60 text-xs truncate" style={{ direction: 'rtl', textAlign: 'left' }}>
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

      {/* hidden native file input - only as fallback */}
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".pdf,.txt,application/pdf,text/plain"
        onChange={handleSelect}
        style={{ display: "none" }}
      />
    </GradientBox>
  );
}
