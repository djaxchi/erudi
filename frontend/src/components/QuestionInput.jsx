import React, { useState, useRef, useEffect } from "react";
import PropTypes from "prop-types";
import { ArrowRight, ImagePlus, X } from "lucide-react";

const MAX_IMAGES = 4;

export default function QuestionInput({
  placeholder = "Ask a question…",
  onSend,
  disabled = false,
  className = "",
  canAttachImages = true,
}) {
  const [value, setValue] = useState("");
  const [images, setImages] = useState([]);
  const [imagePaths, setImagePaths] = useState([]);
  const [dragging, setDragging] = useState(false);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);

  const canSend = !disabled && (value.trim() !== "" || images.length > 0);

  // Clipboard images have no source path, so persist their bytes to a real file
  // and use that path; otherwise they'd be stored as a bare [image] placeholder
  // and vanish on reload (#136). File-origin images already have a path.
  const persistPastedImage = async (dataUrl) => {
    if (!window.imageAPI?.savePasted) {
      return "";
    }
    try {
      return (await window.imageAPI.savePasted(dataUrl)) || "";
    } catch {
      return "";
    }
  };

  const addFiles = (files) => {
    // Single gate for the button, paste and drag-and-drop: a non-vision model
    // never collects an image the backend would just strip (#133).
    if (!canAttachImages) {
      return;
    }
    const imageFiles = Array.from(files || []).filter((f) => f.type.startsWith("image/"));
    imageFiles.forEach((file) => {
      const knownPath = window.electron?.getFilePath?.(file) || "";
      const reader = new FileReader();
      reader.onload = async () => {
        // No source path (clipboard paste) -> persist to disk to obtain one.
        const filePath = knownPath || (await persistPastedImage(reader.result));
        setImages((prev) => (prev.length >= MAX_IMAGES ? prev : [...prev, reader.result]));
        setImagePaths((prev) => (prev.length >= MAX_IMAGES ? prev : [...prev, filePath]));
      };
      reader.readAsDataURL(file);
    });
  };

  const removeImage = (idx) => {
    setImages((prev) => prev.filter((_, i) => i !== idx));
    setImagePaths((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed && images.length === 0) {
      return;
    }
    onSend?.(trimmed, images, imagePaths);
    setValue("");
    setImages([]);
    setImagePaths([]);
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
      {/* Attached images live in their own glass panel (matching the chat
          header) above the composer; the text input yields beneath it. */}
      {images.length > 0 && (
        <div
          className={[
            "mb-2 w-full rounded-[20px] p-2.5",
            "border border-white/10",
            "bg-[rgba(22,40,36,0.45)] backdrop-blur-[18px] saturate-[1.4]",
            "shadow-[0_10px_30px_-6px_rgba(0,0,0,0.5)]",
          ].join(" ")}
        >
          <div className="flex flex-wrap gap-2">
            {images.map((src, idx) => (
              <div key={idx} className="relative">
                <img
                  src={src}
                  alt={`attachment ${idx + 1}`}
                  className="h-20 w-20 object-cover rounded-xl border border-white/10"
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
        {/* Image attach is a vision-only affordance: a text model can't read
            images, so the icon isn't shown at all (not just disabled). */}
        {canAttachImages && (
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
        )}

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
  canAttachImages: PropTypes.bool,
};
