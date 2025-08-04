import React, { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Cog,
  RefreshCcw,
  Plus,
  Edit3,
  X
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { API_BASE_URL } from "../config/api";

export default function ChatCollapsibleSection({
  title,
  items = [],
  selectedId,
  onSelect,
  onRename,
  onDelete,
  onRefresh,
  disabled = false,
}) {
  const [open, setOpen] = useState(true);
  const [editingId, setEditingId] = useState(null);
  const [tempName, setTempName] = useState("");
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [pendingDeleteId, setPendingDeleteId] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [showErrorPopup, setShowErrorPopup] = useState(false);

  const renameConversation = async (id, name) => {
    try {
      const res = await fetch(`${API_BASE_URL}/conversations/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });

      if (!res.ok) throw new Error("Rename failed");

      onRename?.(id, name);
    } catch (err) {
      console.error(err);
      alert("Impossible de renommer la conversation - réessayez.");
    } finally {
      setEditingId(null);
    }
  };

  const deleteConversation = async (id) => {
    try {
      const res = await fetch(`${API_BASE_URL}/conversations/${id}`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
      });

      if (!res.ok) throw new Error("Delete failed");

      onDelete?.(id);
    } catch (err) {
      console.error(err);
      alert("Deleting conversation failed.");
    } finally {
      setEditingId(null);
    }
  };

  const renderItems = () => {
    if (loading) return (
      <div className="flex items-center justify-center py-4">
        <div className="w-5 h-5 border-2 border-gray-400 border-t-emerald-400 rounded-full animate-spin"></div>
      </div>
    );

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
                    e.stopPropagation();
                  }
                  if (e.key === "Escape") {
                    setEditingId(null);
                  }
                }}
                onBlur={() => setEditingId(null)}
                autoFocus
                className="w-full bg-transparent focus:outline-none focus:ring-0 focus:shadow-none focus:border-transparent border-b border-emerald-400"
              />
            ) : (
              <span>{conv.name}</span>
            )}

            <div className="absolute right-2 top-1/2 -translate-y-1/2 flex gap-2 opacity-0 group-hover:opacity-100">
              <Edit3
                onClick={(e) => {
                  e.stopPropagation();
                  setEditingId(conv.id);
                  setTempName(conv.name);
                }}
                className="w-4 h-4 text-gray-400 hover:text-gray-200 cursor-pointer"
              />
              <X
                onClick={(e) => {
                  e.stopPropagation();
                  setPendingDeleteId(conv.id);
                  setShowDeleteConfirm(true);
                }}
                className="w-4 h-4 text-red-400 hover:text-red-300 cursor-pointer"
              />
            </div>
          </div>
        );
      });
    }

    return <p className="italic">Nothing here…</p>;
  };

  return (
    <div
      className={`text-gray-200 h-full ${disabled ? "pointer-events-none opacity-50 select-none" : ""}`}
    >
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
          <RefreshCcw
            className="w-6 h-6 hover:opacity-70 hover:bg-gray-600/30 rounded-full p-1 -m-1 cursor-pointer"
            onClick={async (e) => {
              e.stopPropagation();
              setLoading(true);
              await new Promise((resolve) => setTimeout(resolve, 300));
              try {
                await onRefresh?.();
              } catch (err) {
                console.error("Failed to refresh conversations:", err);
                setErrorMessage(`Failed to refresh conversations: ${err.message || 'Network error'}`);
                setShowErrorPopup(true);
              } finally {
                setLoading(false);
              }
            }}
          />
          <Plus
            className="w-6 h-6 hover:opacity-70 hover:bg-gray-600/30 rounded-full p-1 -m-1 cursor-pointer"
            onClick={(e) => {
              e.stopPropagation();
              navigate('/main_window/chat');
            }}
          />
        </div>
      </div>

      {open && (
        <div className="px-4 py-2 max-h-[88%] overflow-y-auto overflow-x-visible custom-scroll">
          {renderItems()}
        </div>
      )}

      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-[#272727] text-white rounded-lg p-6 w-full max-w-sm shadow-lg">
            <h2 className="text-lg font-semibold mb-4">Are you sure to delete this conversation ?</h2>
            <p className="text-sm mb-6">This action is irreversible.</p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="px-4 py-2 text-sm bg-gray-600 hover:bg-gray-700 rounded"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  deleteConversation(pendingDeleteId);
                  setShowDeleteConfirm(false);
                }}
                className="px-4 py-2 text-sm bg-red-600 hover:bg-red-700 rounded"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Error Popup */}
      {showErrorPopup && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md mx-4 shadow-xl">
            <div className="flex items-center mb-4">
              <div className="bg-red-100 rounded-full p-2 mr-3">
                <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-gray-900">Error</h3>
            </div>
            <p className="text-gray-700 mb-4">{errorMessage}</p>
            <div className="flex justify-end">
              <button
                onClick={() => setShowErrorPopup(false)}
                className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}