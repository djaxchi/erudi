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

    // Helper component for tooltips
    const TooltipIcon = ({ id }) => {
        const getTooltipText = (id) => {
            switch (id) {
                case 'storage':
                    return 'Hard drive space for saving your work. More space = bigger models.';
                case 'ram':
                    return 'Computer memory for faster processing. More memory = quicker results.';
                case 'cpu':
                    return 'Main processor that prepares data and keeps training smooth.';
                case 'gpu':
                    return 'Graphics card that does the AI training. Powerful card = faster training.';
                case 'gpu-memory':
                    return 'Graphics memory that sets max model size. More memory = bigger models.';
                case 'rating':
                    return 'Overall system capability for AI model fine-tuning based on your hardware specs.';
                default:
                    return '';
            }
        };
        return (
            <Tooltip content={getTooltipText(id)} side="right" width="w-80">
                <HelpCircle className="w-3 h-3 sm:w-4 sm:h-4 text-gray-400 hover:text-emerald-400 transition-colors cursor-help" />
            </Tooltip>
        );
    };

    /* helper to determine bullet color for size-based fields */
    const getSizeBulletInfo = (gbString) => {
        // If it's still "fetching..." show gray bullet
        if (gbString && gbString.includes("fetching")) {
            return { 
                type: 'bullet', 
                value: "bg-gray-500"
            };
        }

        // Try to extract number from string for color coding
        let bulletColor = "bg-gray-500"; // Default color
        if (typeof gbString === 'string') {
            const match = gbString.match(/(\d+\.?\d*)/);
            if (match) {
                const n = parseFloat(match[1]);
                if (!isNaN(n)) {
                    if (n < 10) bulletColor = "bg-red-500";
                    else if (n < 30) bulletColor = "bg-orange-400";
                    else bulletColor = "bg-emerald-400";
                }
            }
        }

        return { 
            type: 'bullet', 
            value: bulletColor
        };
    };

    /* helper to determine bullet color for rating field */
    const getRatingBulletInfo = (rating) => {
        // If it's still "fetching..." show gray bullet
        if (rating && rating.includes("fetching")) {
            return { 
                type: 'bullet', 
                value: "bg-gray-500"
            };
        }

        // Color code based on rating
        let bulletColor = "bg-red-500"; // Default for "Poor"
        if (rating === "Good") {
            bulletColor = "bg-emerald-400";
        } else if (rating === "Average") {
            bulletColor = "bg-orange-400";
        }

        return { 
            type: 'bullet', 
            value: bulletColor
        };
    };

    /* helper to get bullet color based on eval score */
    const getEvalScoreBulletInfo = (scoreString) => {
        // If it's still "fetching..." show gray bullet
        if (scoreString && scoreString.includes("fetching")) {
            return { 
                type: 'bullet', 
                value: "bg-gray-500"
            };
        }

        // Extract score from string like "75/100"
        let bulletColor = "bg-red-500"; // Default for poor performance
        if (typeof scoreString === 'string') {
            const match = scoreString.match(/(\d+)\/100/);
            if (match) {
                const score = parseInt(match[1]);
                if (!isNaN(score)) {
                    if (score >= 70) bulletColor = "bg-emerald-400"; // Good performance
                    else if (score >= 40) bulletColor = "bg-orange-400"; // Average performance
                    // else stays red for poor performance
                }
            }
        }

        return { 
            type: 'bullet', 
            value: bulletColor
        };
    };

    return (
        <div className="relative rounded-2xl shadow-xl flex-1 min-w-[340px] border border-[#385B4F] border-[0.3px] overflow-visible">
            <div className="absolute inset-0 opacity-[11%] pointer-events-none rounded-2xl overflow-hidden"
                style={{
                    background:
                        "linear-gradient(135deg,rgba(217,217,217,1) 0%,rgba(217,217,217,0.26) 26%,rgba(0,204,133,1) 100%)",
                }}
            />
            <div className="absolute inset-0 mix-blend-overlay pointer-events-none rounded-2xl overflow-hidden" />
            <div className="relative z-10 px-3 py-1.5 sm:px-4 sm:py-2 md:px-6 md:py-2.5 lg:py-3 space-y-2 sm:space-y-2.5 overflow-visible">
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
                        <div className="flex items-center gap-1 overflow-visible">
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
                        <div className="flex items-center gap-1 overflow-visible">
                            <span>Total RAM</span>
                            <TooltipIcon id="ram" />
                        </div>
                    }
                    bullet={getSizeBulletInfo(hw.total_ram_gb).value}
                >
                    {hw.total_ram_gb}
                </InfoRow>

                <InfoRow 
                    label={
                        <div className="flex items-center gap-1 overflow-visible">
                            <span>Available CPU</span>
                            <TooltipIcon id="cpu" />
                        </div>
                    }
                    bullet={getEvalScoreBulletInfo(hw.cpu_eval_score).value}
                >
                    {hw.cpu_model}
                </InfoRow>

                <InfoRow 
                    label={
                        <div className="flex items-center gap-1 overflow-visible">
                            <span>Available GPU</span>
                            <TooltipIcon id="gpu" />
                        </div>
                    }
                    bullet={getEvalScoreBulletInfo(hw.gpu_eval_score).value}
                >
                    {hw.gpu_model}
                </InfoRow>

                <InfoRow
                    label={
                        <div className="flex items-center gap-1 overflow-visible">
                            <span>GPU Total Memory</span>
                            <TooltipIcon id="gpu-memory" />
                        </div>
                    }
                    bullet={getSizeBulletInfo(hw.gpu_vram_total).value}
                >
                    {hw.gpu_vram_total}
                </InfoRow>

                <InfoRow
                    label={
                        <div className="flex items-center gap-1 overflow-visible">
                            <span>Fine-Tuning Capability Rating</span>
                            <TooltipIcon id="rating" />
                        </div>
                    }
                    isHeader={true}
                    bullet={getRatingBulletInfo(hw.global_finetuning_label).value}
                >
                    {hw.global_finetuning_label || "Poor"}
                </InfoRow>
            </div>
        </div>
    );
}
