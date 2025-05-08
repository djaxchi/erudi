import React, { useState, useEffect } from "react";
import { ChevronDown, ChevronRight, Cog, RefreshCcw, Plus } from "lucide-react";
import { useNavigate } from "react-router-dom";

export default function CollapsibleSection({ title, items = [], selectedId, onSelect }) {
  const [open, setOpen] = useState(true);
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate(); // 👈 pour redirection

  const renderItems = () => {
    if (loading) return <p className="italic">Loading...</p>;

    if (title === "Previous Chats" && items.length > 0) {
      return items.map((conv) => {
        const isSelected = selectedId === conv.id;
        return (
          <div
            key={conv.id}
            onClick={() => {
              onSelect?.(conv.id);
              navigate(`/main_window/conversations/${conv.id}`); // 👈 redirection
            }}
            className={`py-2 px-4 rounded-md cursor-pointer transition-all duration-150 ${
              isSelected
                ? "bg-emerald-500 text-white"
                : "hover:bg-gray-700 hover:text-white text-gray-300"
            }`}
          >
            Conversation #{conv.id}
          </div>
        );
      });
    }

    const list = models.length > 0 ? models : [];
    return list.length > 0 ? (
      list.map((model) => (
        <p key={model.id} className="py-1">
          {model.name}
        </p>
      ))
    ) : (
      <p className="italic">Nothing here…</p>
    );
  };

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

      {open && <div className="px-4 py-2">{renderItems()}</div>}
    </div>
  );
}
