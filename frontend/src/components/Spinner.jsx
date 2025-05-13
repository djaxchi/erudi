import React from "react";

export default function SpinnerDots({
  size = 40,
  dotSize = 8,
  colorClass = "bg-emerald-500",
}) {
  const dotCount = 8;
  const dots = Array.from({ length: dotCount });

  return (
    <div
      className="relative animate-spin"
      style={{ width: size, height: size }}
    >
      {dots.map((_, i) => {
        const angle = (360 / dotCount) * i;
        const radius = size / 2 - dotSize / 2;
        const x =
          radius * Math.cos((angle * Math.PI) / 180) + size / 2 - dotSize / 2;
        const y =
          radius * Math.sin((angle * Math.PI) / 180) + size / 2 - dotSize / 2;
        return (
          <div
            key={i}
            className={`${colorClass} absolute rounded-full`}
            style={{
              width: dotSize,
              height: dotSize,
              top: y,
              left: x,
            }}
          />
        );
      })}
    </div>
  );
}



