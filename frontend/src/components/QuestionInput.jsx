import React, { useState, useRef, useEffect } from "react";
import PropTypes from "prop-types";
import { ArrowRight, ImagePlus, X } from "lucide-react";

const MAX_IMAGES = 4;

export default function QuestionInput({
  placeholder = "Ask a question…",
  onSend,
  disabled = false,
  className = "",
}) {
  const [value, setValue] = useState("");
  const [images, setImages] = useState([]);
  const [dragging, setDragging] = useState(false);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);

  const canSend = !disabled && (value.trim() !== "" || images.length > 0);

  const addFiles = (files) => {
    const imageFiles = Array.from(files || []).filter((f) => f.type.startsWith("image/"));
    imageFiles.forEach((file) => {
      const reader = new FileReader();
      reader.onload = () => {
        setImages((prev) => (prev.length >= MAX_IMAGES ? prev : [...prev, reader.result]));
      };
      reader.readAsDataURL(file);
    });
  };

  const removeImage = (idx) => setImages((prev) => prev.filter((_, i) => i !== idx));

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed && images.length === 0) {
      return;
    }
    onSend?.(trimmed, images);
    setValue("");
    setImages([]);
    resizeTextarea();
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handlePaste = (e) => {
    const items = e.clipboardData?.items;
    if (!items) {
      return;
    }
    const files = [];
    for (const item of items) {
      if (item.kind === "file" && item.type.startsWith("image/")) {
        const f = item.getAsFile();
        if (f) {
          files.push(f);
        }
      }
    }
    if (files.length) {
      e.preventDefault();
      addFiles(files);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer?.files?.length) {
      addFiles(e.dataTransfer.files);
    }
  };

  const resizeTextarea = () => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 160) + "px";
    }
  };
  useEffect(() => {
    resizeTextarea();
  }, [value]);

  return (
    <div className={["relative w-full", className].join(" ")}>
      {/* Attached-image thumbnails */}
      {images.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-2 px-1">
          {images.map((src, idx) => (
            <div key={idx} className="relative">
              <img
                src={src}
                alt={`attachment ${idx + 1}`}
                className="h-16 w-16 object-cover rounded-lg border border-emerald-200/20"
              />
              <button
                type="button"
                onClick={() => removeImage(idx)}
                aria-label="Remove image"
                className="absolute -top-2 -right-2 rounded-full bg-black/70 p-0.5 text-white/90 hover:text-white"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Panel "glassy" with emerald-900 tint */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={[
          "relative flex items-center w-full rounded-[20px] overflow-hidden",
          "border",
          dragging ? "border-emerald-400/60" : "border-emerald-200/20",
          "bg-emerald-200/5 backdrop-blur-[10px] saturate-[1.3]",
          "shadow-[0_10px_30px_-6px_rgba(0,0,0,0.5),0_2px_6px_-1px_rgba(0,0,0,0.45)]",
        ].join(" ")}
      >
        {/* Frost overlays with emerald tint */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 rounded-[20px] mix-blend-overlay"
          style={{
            background:
              "linear-gradient(180deg, rgba(16,185,129,0.12) 0%, rgba(16,185,129,0.06) 28%, rgba(16,185,129,0.02) 60%, rgba(16,185,129,0) 100%)",
          }}
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 rounded-[20px] opacity-20 mix-blend-overlay"
          style={{
            backgroundImage:
              'url("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAABVUlEQVRYR+2WvQ3CMAyFPxF0AB1AB1ABN0AHcAF0gA3QATpN0lInyY5kUVqSk4TsSIv8P2RNFpBf6h8Bi5TBSW0AVbAAmwBpjqgA3wD1fYwHzwFR3QAdwDvl7T2JQG4C7gA/H8LwAVtFznGKnyD20PnKQqa5wzwwM3Vl8r9mQwZP4RFL9XPs35SHJxKcVd5jTwK9K1u4ErfJUF2XblI8g4BtMSSYlLQF41f+WAbc42t7CM6ikgs6Y2oT64y8G8BuEorQFrirN4i0cK4erQblIDmI+F6kAD0fYp2RchEot1Hc6S/T/lNa8T1nDjMDPxgg7wM8S+P8Gn8UH2Piu0mV9K/VLBbq+508Quy_ngGBrhV98yYzeBdOL4SqyGoccEqbE6+ZjKlj19qCxgY6N8lH3dy5zvY1/drdEw2d+uHMDuHwrK0Yas7PwAxRxmKJl0VokAAAAASUVORK5CYII=")',
            backgroundSize: "200px 200px",
          }}
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 rounded-[20px]"
          style={{
            boxShadow: "inset 0 1px 0 rgba(16,185,129,0.15), inset 0 -1px 0 rgba(16,185,129,0.08)",
          }}
        />

        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          onChange={(e) => {
            addFiles(e.target.files);
            e.target.value = "";
          }}
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled || images.length >= MAX_IMAGES}
          className="pl-3 md:pl-4 text-white/70 hover:text-white disabled:opacity-40 transition"
          aria-label="Attach image"
          title="Attach image (or paste / drag and drop)"
        >
          <ImagePlus className="w-5 h-5" />
        </button>

        <textarea
          ref={textareaRef}
          rows={1}
          placeholder={placeholder}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          disabled={disabled}
          style={{ maxHeight: "160px" }}
          className={[
            "w-full bg-transparent px-3 md:px-4 py-3 md:py-4",
            "border-0 text-gray-100 placeholder-gray-300",
            "focus:outline-none focus:ring-0 focus:shadow-none",
            "disabled:opacity-50 resize-none overflow-y-auto",
            "text-[0.95rem] md:text-[1rem] leading-6",
          ].join(" ")}
        />

        <div className="pr-0 md:pr-2 flex items-center">
          <button
            onClick={handleSend}
            disabled={!canSend}
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

QuestionInput.propTypes = {
  placeholder: PropTypes.string,
  onSend: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
  className: PropTypes.string,
};
