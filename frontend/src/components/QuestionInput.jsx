import React, { useState, useRef, useEffect } from "react";
import { SendHorizontal } from "lucide-react";

export default function QuestionInput({
  placeholder = "Ask a question…",
  onSend,
  disabled = false,
  backgroundClass = "bg-emerald-900",
  className = "",
}) {
  const [value, setValue] = useState("");
  const textareaRef = useRef(null);

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed) return;
    onSend?.(trimmed);
    setValue("");
    resizeTextarea(); // reset height
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const resizeTextarea = () => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto"; // reset
      textarea.style.height = Math.min(textarea.scrollHeight, 160) + "px"; // max ≈ 4 lignes
    }
  };

  useEffect(() => {
    resizeTextarea();
  }, [value]);

  return (
    <div
      className={`flex items-end rounded-2xl overflow-hidden ${backgroundClass} ${className} w-full`}
    >
      <textarea
        ref={textareaRef}
        rows={1}
        placeholder={placeholder}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        style={{ maxHeight: "100px" }}
        className="w-full bg-transparent font-thin px-8 py-4 border-0 text-white placeholder-white focus:outline-none focus:ring-0 focus:shadow-none disabled:opacity-50 resize-none overflow-y-auto"
      />
      <button
        onClick={handleSend}
        disabled={disabled || value.trim() === ""}
        className="pr-6 pb-3 disabled:opacity-50"
      >
        <SendHorizontal className="w-6 h-6 text-white" />
      </button>
    </div>
  );
}
