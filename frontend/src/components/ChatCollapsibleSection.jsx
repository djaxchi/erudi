import React, { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Cog,
  RefreshCcw,
  Plus,
  Edit3,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

export default function ChatCollapsibleSection({
  title,
  items = [],
  selectedId,
  onSelect,
  onRename, 
}) {
  const [open, setOpen] = useState(true);
  const [editingId, setEditingId] = useState(null);
  const [tempName, setTempName] = useState("");
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  


  const renameConversation = async (id, name) => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/conversations/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });

      if (!res.ok) throw new Error("Rename failed");

      // notify parent so it can refresh its list, if desired
      onRename?.(id, name);
    } catch (err) {
      console.error(err);
      alert("Impossible de renommer la conversation – réessayez.");
    } finally {
      setEditingId(null);
    }
  };

  const renderItems = () => {
    if (loading) return <p className="italic">Loading...</p>;

    if (title === "Previous Chats" && items.length > 0) {
      return items.map((conv) => {
        const isSelected = selectedId === conv.id;
        const isEditing = editingId === conv.id;

        return (
          <div
            key={conv.id}
            onClick={() => {
              if (!isEditing) {
                onSelect?.(conv.id);
                navigate(`/main_window/conversations/${conv.id}`);
              }
            }}
            className={`relative group py-2 px-4 rounded-md cursor-pointer transition-all duration-150 ${
              isSelected
                ? "bg-emerald-500/50 text-white"
                : "hover:bg-gray-700 hover:text-white text-gray-300"
            }`}
          >
            {isEditing ? (
              <input
                value={tempName}
                onChange={(e) => setTempName(e.target.value)}
                onKeyDown={async (e) => {
                  if (e.key === "Enter" && tempName.trim()) {
                    await renameConversation(conv.id, tempName.trim());
+                   e.stopPropagation();
                  }
                  if (e.key === "Escape") {
                    setEditingId(null);
                  }
                }}
                onBlur={() => setEditingId(null)}
                autoFocus
                className="w-full bg-transparent focus:outline-none border-b border-emerald-400"
              />
            ) : (
              <span>{conv.name}</span>
            )}

            <Edit3
              onClick={(e) => {
                e.stopPropagation();
                setEditingId(conv.id);
                setTempName(conv.name);
              }}
              className="absolute right-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400 opacity-0 group-hover:opacity-100 hover:text-gray-200 transition-opacity cursor-pointer"
            />
          </div>
        );
      });
    }

    
    <p className="italic">Nothing here…</p>
  };

  return (
    <div className="text-gray-200">
      <div
        className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-gray-700/30"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center gap-2">
          {open ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
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
