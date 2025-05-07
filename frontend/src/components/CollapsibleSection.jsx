import React, { useState } from "react";
import { ChevronDown, ChevronRight, Cog, RefreshCcw, Plus } from "lucide-react";

export default function CollapsibleSection({ title }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="text-gray-200">
      <div
        className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-gray-700/30"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center gap-2">
          {open ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          <span className="font-semibold">{title}</span>
        </div>

        <div className="flex gap-3">
          <Cog className="w-4 h-4 hover:opacity-70" />
          <RefreshCcw className="w-4 h-4 hover:opacity-70" />
          <Plus className="w-4 h-4 hover:opacity-70" />
        </div>
      </div>

      {open && <p className="px-10 py-2 text-sm italic text-gray-500">Nothing here…</p>}
    </div>
  );
}