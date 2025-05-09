import React, { useState } from "react";
import { SendHorizontal } from "lucide-react";

/**
 * Champ de question réutilisable.
 *
 * Props
 * - placeholder: string                (texte d’aide)
 * - onSend(message): function          (callback quand l’utilisateur envoie)
 * - disabled: boolean                  (désactive input & bouton)
 * - backgroundClass: string            (classes Tailwind pour le fond, ex: "bg-gray-900/80")
 * - className: string                  (classes additionnelles sur le conteneur)
 */
export default function QuestionInput({
  placeholder = "Ask a question…",
  onSend,
  disabled = false,
  backgroundClass = "bg-gray-900/80",
  className = "",
}) {
  const [value, setValue] = useState("");

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed) return;
    onSend?.(trimmed);
    setValue("");
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div
      className={`flex items-center rounded-full overflow-hidden ${backgroundClass} ${className}`}
    >
      <input
        type="text"
        placeholder={placeholder}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        className="flex-1 bg-transparent font-thin px-8 py-4 border-0 text-white placeholder-white focus:outline-none disabled:opacity-50"
      />
      <button
        onClick={handleSend}
        disabled={disabled || value.trim() === ""}
        className="pr-6 disabled:opacity-50"
      >
        <SendHorizontal className="w-6 h-6 text-white" />
      </button>
    </div>
  );
}
