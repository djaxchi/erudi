import React, { useState, useEffect } from "react";
import { ChevronDown, ChevronRight, Cog, RefreshCcw, Plus } from "lucide-react";

export default function CollapsibleSection({ title }) {
  const [open, setOpen] = useState(true);
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(false);

useEffect(() => {
    const fetchModels = async () => {
        setLoading(true);
        try {
            if (title === "Local Models") {
                const response = await fetch("http://127.0.0.1:8000/main_window/llms/local");
                if (response.ok) {
                    const data = await response.json();
                    setModels(data);
                } else {
                    console.error("Failed to fetch local models");
                }
            } else {
                const response = await fetch("http://127.0.0.1:8000/main_window/llms/remote");
                if (response.ok) {
                    const data = await response.json();
                    setModels(data);
                } else {
                    console.error("Failed to fetch remote models");
                }
            }
        } catch (error) {
            console.error("Error fetching models:", error);
        } finally {
            setLoading(false);
        }
    };

    fetchModels();
}, [title]);
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

      {open && (
        <div className="px-10 py-2 text-sm text-gray-500">
          {loading ? (
            <p className="italic">Loading...</p>
          ) : title === "Local Models" && models.length > 0 ? (
            models.map((model) => (
              <p key={model.id} className="py-1">
                {model.name}
              </p>
            ))
          ) : (
            <p className="italic">Nothing here…</p>
          )}
        </div>
      )}
    </div>
  );
}