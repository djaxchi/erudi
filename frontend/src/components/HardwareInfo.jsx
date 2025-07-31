import React, { useState } from "react";
import InfoRow from "./InfoRow";
import Tooltip from "./Tooltip";
import { Check, X, HelpCircle, Folder } from "lucide-react";


export default function HardwareInfo({ hw }) {
    const [storagePath, setStoragePath] = useState(hw.storage_path || "");
    
    // Handle directory selection for storage path
    const handleStoragePathSelection = async () => {
        try {
            // Use the Electron API from preload.js
            if (window.electron && window.electron.openDirectory) {
                const result = await window.electron.openDirectory();
                console.log("Storage directory selection result:", result); // Debug log
                
                // Handle different possible result structures
                if (result && !result.canceled) {
                    let selectedPath = null;
                    
                    // Check different possible structures
                    if (result.filePaths && result.filePaths.length > 0) {
                        selectedPath = result.filePaths[0];
                    } else if (result.filePath) {
                        selectedPath = result.filePath;
                    } else if (typeof result === 'string') {
                        selectedPath = result;
                    }
                    
                    if (selectedPath) {
                        setStoragePath(selectedPath);
                        console.log("Selected storage path:", selectedPath);
                    } else {
                        console.log("No directory selected or invalid result structure");
                    }
                } else {
                    console.log("Directory selection was canceled or failed");
                }
            } else {
                console.warn("Electron API not available for selecting directory");
                // Fallback for web environment - create hidden file input
                const input = document.createElement('input');
                input.type = 'file';
                input.webkitdirectory = true; // For directory selection
                input.style.display = 'none';
                
                input.onchange = (e) => {
                    const files = e.target.files;
                    if (files && files.length > 0) {
                        // Get the directory path from the first file
                        const firstFile = files[0];
                        const pathParts = firstFile.webkitRelativePath.split('/');
                        if (pathParts.length > 0) {
                            setStoragePath(pathParts[0]); // Use the directory name
                        }
                    }
                    document.body.removeChild(input);
                };
                
                document.body.appendChild(input);
                input.click();
            }
        } catch (error) {
            console.error('Error selecting storage directory:', error);
        }
    };

    /* helper to determine bullet or icon for size-based fields */
    const getBulletOrIcon = (gbString) => {
        console.log("Data received:", gbString);

        // If it's still "fetching..." show question mark icon
        if (gbString && gbString.includes("fetching")) {
            return { type: 'icon', value: <HelpCircle className="w-3 h-3 sm:w-4 sm:h-4 text-gray-400" /> };
        }

        // Try to extract number from string for color coding
        if (typeof gbString === 'string') {
            const match = gbString.match(/(\d+\.?\d*)/);
            if (match) {
                const n = parseFloat(match[1]);
                if (!isNaN(n)) {
                    if (n < 10) return { type: 'bullet', value: "bg-red-500" };
                    if (n < 30) return { type: 'bullet', value: "bg-orange-400" };
                    return { type: 'bullet', value: "bg-emerald-400" };
                }
            }
        }

        // Default fallback - question mark for unknown data
        return { type: 'icon', value: <HelpCircle className="w-3 h-3 sm:w-4 sm:h-4 text-gray-400" /> };
    };

    /* helper to determine bullet or icon for rating field */
    const getRatingBulletOrIcon = (rating) => {
        console.log("Rating received:", rating);

        // If it's still "fetching..." show question mark icon
        if (rating && rating.includes("fetching")) {
            return { type: 'icon', value: <HelpCircle className="w-3 h-3 sm:w-4 sm:h-4 text-gray-400" /> };
        }

        // Color code based on rating
        if (rating === "Good") {
            return { type: 'bullet', value: "bg-emerald-400" };
        } else if (rating === "Average") {
            return { type: 'bullet', value: "bg-orange-400" };
        } else {
            return { type: 'bullet', value: "bg-red-500" };
        }
    };

    /* Tooltipped icons for different hardware components */
    const getTooltippedIcon = (type) => {
        const tooltips = {
            storage: "Hard drive space for saving your work. More space = bigger models.",
            ram: "Computer memory for faster processing. More memory = quicker results.",
            cpu: "Main processor that prepares data and keeps training smooth.",
            gpu: "Graphics card that does the AI training. Powerful card = faster training.",
            vram: "Graphics memory that sets max model size. More memory = bigger models."
        };

        return (
            <Tooltip content={tooltips[type]} position="left">
                <HelpCircle className="w-3 h-3 sm:w-4 sm:h-4 text-gray-400 hover:text-emerald-400 transition-colors" />
            </Tooltip>
        );
    };

    return (
        <div className="relative rounded-2xl overflow-hidden shadow-xl flex-1 min-w-[340px] border border-[#385B4F] border-[0.3px]">
            <div className="absolute inset-0 opacity-[11%] pointer-events-none"
                style={{
                    background:
                        "linear-gradient(135deg,rgba(217,217,217,1) 0%,rgba(217,217,217,0.26) 26%,rgba(0,204,133,1) 100%)",
                }}
            />
            <div className="absolute inset-0 mix-blend-overlay pointer-events-none" />
            <div className="relative z-10 px-3 py-1.5 sm:px-4 sm:py-2 md:px-6 md:py-2.5 lg:py-3 space-y-3 sm:space-y-4">
                {/* storage path */}
                <InfoRow label="Storage Path :" isHeader={true}>
                    {/* Container to keep things from overflowing in the right column */}
                    <div className="flex items-center gap-2 min-w-0">
                        {/* Path pill with folder icon (clickable) */}
                        <button
                            type="button"
                            onClick={handleStoragePathSelection}
                            className="
         inline-flex items-center gap-2 rounded-full
         bg-white/5 border border-white/10
         px-3 py-1.5 text-[13px] leading-none text-white/90
         shadow-sm backdrop-blur
         hover:bg-white/[0.08] hover:border-white/15
         focus:outline-none focus:ring-2 focus:ring-emerald-400/60
         transition cursor-pointer
         max-w-[220px] sm:max-w-[260px] lg:max-w-[300px]
       "
                            aria-label="Choose storage directory"
                        >
                            <span className="truncate" style={{ direction: 'rtl', textAlign: 'left' }}>
                                {storagePath || "Select Storage"}
                            </span>
                            <Folder className="w-4 h-4 opacity-85 shrink-0" />
                        </button>
                    </div>
                </InfoRow>

                <InfoRow
                    label="Available Storage :"
                    {...(getBulletOrIcon(hw.disk_available).type === 'bullet'
                        ? { bullet: getBulletOrIcon(hw.disk_available).value }
                        : { icon: getTooltippedIcon('storage') })}
                >
                    {hw.disk_available}
                </InfoRow>

                <InfoRow
                    label="Total RAM :"
                    {...(getBulletOrIcon(hw.total_ram_gb).type === 'bullet'
                        ? { bullet: getBulletOrIcon(hw.total_ram_gb).value }
                        : { icon: getTooltippedIcon('ram') })}
                >
                    {hw.total_ram_gb}
                </InfoRow>

                <InfoRow label="Available CPU :" icon={getTooltippedIcon('cpu')}>
                    {hw.cpu_model}
                </InfoRow>

                <InfoRow label="Available GPU :" icon={getTooltippedIcon('gpu')}>
                    {hw.gpu_model}
                </InfoRow>

                <InfoRow
                    label="GPU Total Memory :"
                    {...(getBulletOrIcon(hw.gpu_vram_total).type === 'bullet'
                        ? { bullet: getBulletOrIcon(hw.gpu_vram_total).value }
                        : { icon: getTooltippedIcon('vram') })}
                >
                    {hw.gpu_vram_total}
                </InfoRow>

                {/* CUDA row - commented out to reduce clutter */}
                {/* 
                <InfoRow label="Cuda Installed :">
                    <div className="flex items-center gap-2 min-w-0">
                        <button
                            type="button"
                            onClick={handleCudaPathSelection}
                            className="
         inline-flex items-center gap-2 rounded-full
         bg-white/5 border border-white/10
         px-3 py-1.5 text-[13px] leading-none text-white/90
         shadow-sm backdrop-blur
         hover:bg-white/[0.08] hover:border-white/15
         focus:outline-none focus:ring-2 focus:ring-emerald-400/60
         transition cursor-pointer
         max-w-[220px] sm:max-w-[260px] lg:max-w-[300px]
       "
                            aria-label="Choose CUDA directory"
                        >
                            <span className="truncate" style={{ direction: 'rtl', textAlign: 'left' }}>
                                {cudaPath || "Select CUDA path"}
                            </span>
                            <Folder className="w-4 h-4 opacity-85 shrink-0" />
                        </button>
                        {cudaPath ? (
                            <Check className="w-3 h-3 sm:w-4 sm:h-4 text-emerald-400 flex-shrink-0" />
                        ) : (
                            <X className="w-3 h-3 sm:w-4 sm:h-4 text-red-500 flex-shrink-0" />
                        )}
                    </div>
                </InfoRow>
                */}

                <InfoRow
                    label="Overall Config Rating :"
                    isHeader={true}
                    {...(getRatingBulletOrIcon(hw.rating).type === 'bullet'
                        ? { bullet: getRatingBulletOrIcon(hw.rating).value }
                        : { icon: getRatingBulletOrIcon(hw.rating).value })}
                >
                    {hw.rating || "Poor"}
                </InfoRow>
            </div>
        </div>
    );
}
