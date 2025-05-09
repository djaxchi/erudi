import React, { useState } from "react";
import GradientBox from "./GradientBox";
import InfoRow from "./InfoRow";
import { Check, X } from "lucide-react";




export default function HardwareInfo({ hw }) {
  const [cudaPath, setCudaPath] = useState(hw.cuda_installed.path);

    return (
        <GradientBox className="flex-1 min-w-[300px]">
            <InfoRow label="Storage Path :">
            <input
                className="bg-gray-800/60 border border-transparent rounded-full px-4 py-1 placeholder-white text-sm truncate max-w-[180px] focus:border-emerald-400/50 focus:ring-0 focus:outline-none "
                placeholder={hw.storage_path}
            />
            </InfoRow>
            <InfoRow label="Available Storage :">{hw.disk_available}</InfoRow>
            <InfoRow label="Available RAM :">{hw.ram_available} </InfoRow>
            <InfoRow label="Available CPU :">{hw.cpu_model}</InfoRow>
            <InfoRow label="Available GPU :">{hw.gpu_model}</InfoRow>
            <InfoRow label="Cuda Installed :">
            <div className="flex items-center gap-2">
                <input
                value={cudaPath}
                onChange={(e) => setCudaPath(e.target.value)}
                className="bg-gray-800/60 border border-transparent rounded-full px-4 py-1 placeholder-white text-sm truncate max-w-[180px] focus:border-emerald-400/50 focus:ring-0 focus:outline-none"
                placeholder="Click to specify path"
                />
                {cudaPath ? (
                <Check className="w-5 h-5 text-emerald-400" />
                ) : (
                <X className="w-5 h-5 text-red-500" />
                )}
            </div>
            </InfoRow>
        </GradientBox>
    );
}