import React, { useState, useRef, useEffect } from "react";
import { ArrowRight } from "lucide-react";

export default function QuestionInput({
  placeholder = "Ask a question…",
  onSend,
  disabled = false,
  backgroundClass = "", // (legacy) ignoré, on force le style glassy
  className = "",
}) {
  const [value, setValue] = useState("");
  const textareaRef = useRef(null);

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed) return;
    onSend?.(trimmed);
    setValue("");
    resizeTextarea();
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const resizeTextarea = () => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 160) + "px";
    }
  };
  useEffect(() => { resizeTextarea(); }, [value]);

  return (
    <div className={["relative w-full", className].join(" ")}>
      {/* Panel "glassy" with emerald-900 tint */}
      <div
        className={[
          "relative flex items-center w-full rounded-[20px] overflow-hidden",
          "border border-emerald-200/20",
          "bg-emerald-200/5 backdrop-blur-[10px] saturate-[1.3]",
          "shadow-[0_10px_30px_-6px_rgba(0,0,0,0.5),0_2px_6px_-1px_rgba(0,0,0,0.45)]",
        ].join(" ")}
      >
        {/* Frost overlays with emerald tint */}
        <div aria-hidden className="pointer-events-none absolute inset-0 rounded-[20px] mix-blend-overlay"
             style={{background:"linear-gradient(180deg, rgba(16,185,129,0.12) 0%, rgba(16,185,129,0.06) 28%, rgba(16,185,129,0.02) 60%, rgba(16,185,129,0) 100%)"}}/>
        <div aria-hidden className="pointer-events-none absolute inset-0 rounded-[20px] opacity-20 mix-blend-overlay"
             style={{backgroundImage:'url("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAABVUlEQVRYR+2WvQ3CMAyFPxF0AB1AB1ABN0AHcAF0gA3QATpN0lInyY5kUVqSk4TsSIv8P2RNFpBf6h8Bi5TBSW0AVbAAmwBpjqgA3wD1fYwHzwFR3QAdwDvl7T2JQG4C7gA/H8LwAVtFznGKnyD20PnKQqa5wzwwM3Vl8r9mQwZP4RFL9XPs35SHJxKcVd5jTwK9K1u4ErfJUF2XblI8g4BtMSSYlLQF41f+WAbc42t7CM6ikgs6Y2oT64y8G8BuEorQFrirN4i0cK4erQblIDmI+F6kAD0fYp2RchEot1Hc6S/T/lNa8T1nDjMDPxgg7wM8S+P8Gn8UH2Piu0mV9K/VLBbq+508Quy_ngGBrhV98yYzeBdOL4SqyGoccEqbE6+ZjKlj19qCxgY6N8lH3dy5zvY1/drdEw2d+uHMDuHwrK0Yas7PwAxRxmKJl0VokAAAAASUVORK5CYII=")', backgroundSize:"200px 200px"}}/>
        <div aria-hidden className="pointer-events-none absolute inset-0 rounded-[20px]"
             style={{boxShadow:"inset 0 1px 0 rgba(16,185,129,0.15), inset 0 -1px 0 rgba(16,185,129,0.08)"}}/>

        <textarea
          ref={textareaRef}
          rows={1}
          placeholder={placeholder}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          style={{ maxHeight: "160px" }}
          className={[
            "w-full bg-transparent px-4 md:px-5 py-3 md:py-4",
            "border-0 text-gray-100 placeholder-gray-300",
            "focus:outline-none focus:ring-0 focus:shadow-none",
            "disabled:opacity-50 resize-none overflow-y-auto",
            "text-[0.95rem] md:text-[1rem] leading-6",
          ].join(" ")}
        />

        <div className="pr-0 md:pr-2 flex items-center">
          <button
            onClick={handleSend}
            disabled={disabled || value.trim() === ""}
            className={[
              "inline-flex items-center justify-center",
              "p-2",
              "text-white/70 hover:text-white disabled:opacity-50 transition",
            ].join(" ")}
            aria-label="Send"
          >
            <ArrowRight className="w-6 h-6" />
          </button>
        </div>
      </div>
    </div>
  );
}
