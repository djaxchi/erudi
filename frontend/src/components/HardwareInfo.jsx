import React, { useState, useRef, useEffect } from "react";
import InfoRow from "./InfoRow";
import Tooltip from "./Tooltip";
import { Check, X, HelpCircle, Folder } from "lucide-react";


export default function HardwareInfo({ hw }) {
    const [storagePath, setStoragePath] = useState(hw.storage_path || "");
    const [tooltipVisible, setTooltipVisible] = useState(null);
    const [tooltipPosition, setTooltipPosition] = useState({ top: 0, left: 0 });
    
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

    // Helper component for tooltips
    const TooltipIcon = ({ id, text }) => {
        const iconRef = useRef(null);
        
        const handleMouseEnter = () => {
            if (iconRef.current) {
                const rect = iconRef.current.getBoundingClientRect();
                const tooltipWidth = 300; // Approximate tooltip width
                const windowWidth = window.innerWidth;
                
                // Check if tooltip would go off-screen to the right
                const wouldOverflow = rect.right + 8 + tooltipWidth > windowWidth;
                
                setTooltipPosition({
                    top: rect.top + window.scrollY + (rect.height / 2), // Center vertically with the icon
                    left: wouldOverflow 
                        ? rect.left + window.scrollX - 8 - tooltipWidth // Position to the left if would overflow
                        : rect.right + window.scrollX + 8, // 8px to the right of the icon
                    isLeftSide: wouldOverflow
                });
            }
            setTooltipVisible(id);
        };

        const handleMouseLeave = () => {
            setTooltipVisible(null);
        };

        return (
            <div 
                ref={iconRef}
                className="relative"
                onMouseEnter={handleMouseEnter}
                onMouseLeave={handleMouseLeave}
            >
                <HelpCircle className="w-3 h-3 sm:w-4 sm:h-4 text-gray-400 hover:text-emerald-400 transition-colors cursor-help" />
            </div>
        );
    };

    /* helper to determine bullet color for size-based fields */
    const getSizeBulletInfo = (gbString) => {
        // If it's still "fetching..." show red bullet
        if (gbString && gbString.includes("fetching")) {
            return { 
                type: 'bullet', 
                value: "bg-red-500"
            };
        }

        // Try to extract number from string for color coding
        let bulletColor = "bg-red-500"; // Default color
        if (typeof gbString === 'string') {
            const match = gbString.match(/(\d+\.?\d*)/);
            if (match) {
                const n = parseFloat(match[1]);
                if (!isNaN(n)) {
                    if (n >= 50) bulletColor = "bg-green-500";      // Plenty of space/memory
                    else if (n >= 20) bulletColor = "bg-orange-400"; // Moderate space/memory
                    else bulletColor = "bg-red-500";                 // Low space/memory
                }
            }
        }

        return { 
            type: 'bullet', 
            value: bulletColor
        };
    };

    /* helper to determine bullet color for Apple Silicon chip */
    const getChipBulletInfo = (chipModel) => {
        if (!chipModel || chipModel.includes("fetching") || chipModel === "Unknown") {
            return { type: 'bullet', value: "bg-red-500" };
        }
        
        // Color code based on chip generation
        if (chipModel.includes("M4")) return { type: 'bullet', value: "bg-green-500" };
        if (chipModel.includes("M3")) return { type: 'bullet', value: "bg-green-500" };
        if (chipModel.includes("M2")) return { type: 'bullet', value: "bg-orange-400" };
        if (chipModel.includes("M1")) return { type: 'bullet', value: "bg-orange-400" };
        
        return { type: 'bullet', value: "bg-red-500" };
    };

    /* helper to determine bullet color for GPU cores */
    const getGpuCoresBulletInfo = (coresString) => {
        if (!coresString || coresString.includes("fetching") || coresString === "N/A") {
            return { type: 'bullet', value: "bg-red-500" };
        }
        
        // Extract core count from string like "10 cores"
        const match = coresString.match(/(\d+)/);
        if (match) {
            const cores = parseInt(match[1]);
            if (cores >= 20) return { type: 'bullet', value: "bg-green-500" };  // High-end
            if (cores >= 10) return { type: 'bullet', value: "bg-orange-400" }; // Mid-range
            if (cores >= 7) return { type: 'bullet', value: "bg-orange-400" };  // Entry level
        }
        
        return { type: 'bullet', value: "bg-red-500" };
    };

    /* helper to determine bullet color for Neural Engine */
    const getNeuralEngineBulletInfo = (topsString) => {
        if (!topsString || topsString.includes("fetching") || topsString === "N/A") {
            return { type: 'bullet', value: "bg-red-500" };
        }
        
        // Extract TOPS value from string like "18.0 TOPS"
        const match = topsString.match(/(\d+\.?\d*)/);
        if (match) {
            const tops = parseFloat(match[1]);
            if (tops >= 30) return { type: 'bullet', value: "bg-green-500" };  // M4+ level
            if (tops >= 15) return { type: 'bullet', value: "bg-orange-400" }; // M2/M3 level
            if (tops >= 11) return { type: 'bullet', value: "bg-orange-400" }; // M1 level
        }
        
        return { type: 'bullet', value: "bg-red-500" };
    };

    /* helper to determine bullet color for rating field */
    const getRatingBulletInfo = (rating) => {
        // If it's still "fetching..." show red bullet
        if (rating && rating.includes("fetching")) {
            return { type: 'bullet', value: "bg-red-500" };
        }

        // Color code based on rating
        if (rating === "Amazing" || rating === "Excellent" || rating === "Very High") {
            return { type: 'bullet', value: "bg-green-500" };
        } else if (rating === "High" || rating === "Good" || rating === "Medium") {
            return { type: 'bullet', value: "bg-orange-400" };
        } else {
            return { type: 'bullet', value: "bg-red-500" };
        }
    };

    return (
        <div className="relative rounded-2xl shadow-xl flex-1 min-w-[340px] border border-[#385B4F] border-[0.3px]">
            {/* Global tooltip */}
            {tooltipVisible && (
                <div 
                    className="fixed bg-black text-white text-xs rounded-lg px-3 py-2 shadow-xl border border-gray-600 z-[99999]"
                    style={{
                        top: `${tooltipPosition.top}px`,
                        left: `${tooltipPosition.left}px`,
                        transform: 'translateY(-50%)', // Center vertically relative to the icon
                        width: '280px', // Fixed width for consistent sizing
                    }}
                >
                    {tooltipVisible === 'chip' && 'Apple Silicon chip model (M1, M2, M3, M4) that determines overall system capabilities.'}
                    {tooltipVisible === 'storage' && 'Hard drive space for saving your work. More space = bigger models.'}
                    {tooltipVisible === 'ram' && 'Unified memory shared between CPU and GPU. More memory = larger models and faster processing.'}
                    {tooltipVisible === 'gpu-cores' && 'Number of GPU cores in your Apple Silicon chip. More cores = better parallel processing for AI training.'}
                    {tooltipVisible === 'neural-engine' && 'Apple Neural Engine for accelerated machine learning operations (TOPS = Trillion Operations Per Second).'}
                    {tooltipVisible === 'rating' && 'Overall system capability for AI model fine-tuning based on your Apple Silicon hardware specs.'}
                    {/* Arrow pointing left or right depending on position */}
                    {tooltipPosition.isLeftSide ? (
                        <div className="absolute left-full top-1/2 transform -translate-y-1/2 w-0 h-0 border-t-4 border-b-4 border-l-4 border-transparent border-l-black"></div>
                    ) : (
                        <div className="absolute right-full top-1/2 transform -translate-y-1/2 w-0 h-0 border-t-4 border-b-4 border-r-4 border-transparent border-r-black"></div>
                    )}
                </div>
            )}
            
            <div className="absolute inset-0 opacity-[11%] pointer-events-none rounded-2xl overflow-hidden"
                style={{
                    background:
                        "linear-gradient(135deg,rgba(217,217,217,1) 0%,rgba(217,217,217,0.26) 26%,rgba(0,204,133,1) 100%)",
                }}
            />
            <div className="absolute inset-0 mix-blend-overlay pointer-events-none rounded-2xl overflow-hidden" />
            <div className="relative z-10 px-3 py-1.5 sm:px-4 sm:py-2 md:px-6 md:py-2.5 lg:py-3 space-y-2 sm:space-y-2.5">
                {/* storage path */}
                {/* <InfoRow label="Storage Path :" isHeader={true}>
                    <div className="flex items-center gap-2 min-w-0">
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
                </InfoRow> */}

                <InfoRow
                    label={
                        <div className="flex items-center gap-1">
                            <span>Apple Silicon Chip</span>
                            <TooltipIcon id="chip" />
                        </div>
                    }
                    bullet={getChipBulletInfo(hw.cpu_model).value}
                    isHeader={true}
                >
                    {hw.cpu_model || "Unknown"}
                </InfoRow>

                <InfoRow
                    label={
                        <div className="flex items-center gap-1">
                            <span>Available Storage</span>
                            <TooltipIcon id="storage" />
                        </div>
                    }
                    bullet={getSizeBulletInfo(hw.disk_available).value}
                >
                    {hw.disk_available}
                </InfoRow>

                <InfoRow
                    label={
                        <div className="flex items-center gap-1">
                            <span>Total RAM (Unified)</span>
                            <TooltipIcon id="ram" />
                        </div>
                    }
                    bullet={getSizeBulletInfo(hw.total_ram_gb).value}
                >
                    {hw.total_ram_gb}
                </InfoRow>

                <InfoRow
                    label={
                        <div className="flex items-center gap-1">
                            <span>GPU Cores</span>
                            <TooltipIcon id="gpu-cores" />
                        </div>
                    }
                    bullet={getGpuCoresBulletInfo(hw.gpu_cores).value}
                >
                    {hw.gpu_cores}
                </InfoRow>

                <InfoRow
                    label={
                        <div className="flex items-center gap-1">
                            <span>Neural Engine</span>
                            <TooltipIcon id="neural-engine" />
                        </div>
                    }
                    bullet={getNeuralEngineBulletInfo(hw.neural_engine_tops).value}
                >
                    {hw.neural_engine_tops}
                </InfoRow>

                <InfoRow
                    label={
                        <div className="flex items-center gap-1">
                            <span>Fine-Tuning Capability Rating</span>
                            <TooltipIcon id="rating" />
                        </div>
                    }
                    isHeader={true}
                    bullet={getRatingBulletInfo(hw.global_finetuning_label).value}
                >
                    <div className="flex items-center gap-2">
                        <span>{hw.global_finetuning_label || "Poor"}</span>
                        {hw.global_finetuning_score && (
                            <span className="text-xs text-gray-400 bg-gray-800/50 px-2 py-0.5 rounded-full border border-gray-600/30">
                                {hw.global_finetuning_score}
                            </span>
                        )}
                    </div>
                </InfoRow>
            </div>
        </div>
    );
}
