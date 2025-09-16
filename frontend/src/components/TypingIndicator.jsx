import React from "react";
export default function TypingIndicator({
  size = 8,
  colorClass = "bg-gray-400",
  gapClass = "gap-1",
  className = "",
}) {
  const dot = (delay) => (
    <span
      className={`inline-block rounded-full animate-bounce ${colorClass}`}
      style={{ width: size, height: size, animationDelay: `${delay}s` }}
    />
  );

  return (
    <div className={`flex items-center ${gapClass} ${className}`}>
      {dot(0)}
      {dot(0.15)}
      {dot(0.3)}
    </div>
  );
}
