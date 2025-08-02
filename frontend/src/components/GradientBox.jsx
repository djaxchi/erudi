import React from "react";

export default function GradientBox({ children, className = "", ...rest }) {
  return (
    <div {...rest} className={`relative rounded-2xl overflow-hidden shadow-xl ${className}`}>
      <div className="absolute inset-0 opacity-[11%] pointer-events-none"
        style={{
          background:
            "linear-gradient(135deg,rgba(217,217,217,1) 0%,rgba(217,217,217,0.26) 26%,rgba(0,204,133,1) 100%)",
        }}
      />
      <div className="absolute inset-0 mix-blend-overlay pointer-events-none" />
      <div className="relative z-10 p-8">{children}</div>
    </div>
  );
}