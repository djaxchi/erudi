import React from "react";
import { Folder } from "lucide-react";
import GradientBox from "./GradientBox";

export default function DragDropArea() {
  return (
    <GradientBox
      className="flex-1 h-full min-h-[230px]"
      contentClassName="relative z-10 flex items-center justify-center w-full h-full"
    >
      <div className="flex flex-col items-center text-white/80 gap-4">
        <Folder className="w-14 h-14" />
        <p className="text-lg">Drag and Drop</p>
      </div>
    </GradientBox>
  );
}
