import React from "react";

export default function GradientBox({
  children,
  className = "",
  contentClassName,
  onClick,
  ...props
}) {
  // Default content wrapper classes: padding, flex layout, full height, hide overflow
  const defaultContentClasses = "p-8 flex flex-col h-full overflow-hidden";

  return (
    <div
      className={`relative rounded-2xl overflow-hidden shadow-xl ${className}`}
      onClick={onClick}
      {...props}
    >
      {/* gradient layer (11% opacity) */}
      <div
        className="absolute inset-0 opacity-[11%]"
        style={{
          background:
            "linear-gradient(135deg, rgba(217, 217, 217, 1) 0%, rgba(217, 217, 217, 0.26) 26%, rgba(0, 204, 133, 1) 100%)",
        }}
      />

      {/* grain overlay */}
      <div className="absolute inset-0 mix-blend-overlay pointer-events-none" />

      {/* content retains full opacity, customizable wrapper */}
      <div
        className={`relative z-10 ${contentClassName || defaultContentClasses}`}
      >
        {children}
      </div>
    </div>
  );
}