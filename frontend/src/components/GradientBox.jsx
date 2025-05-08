import React from "react";


export default function GradientBox({ children, className = "" }) {
    return (
      <div className={`relative rounded-2xl overflow-hidden shadow-xl ${className}`}>
        {/* gradient layer (11 % d'opacité) */}
        <div
          className="absolute inset-0 opacity-[11%]"
          style={{
            background:
              "linear-gradient(135deg, rgba(217, 217, 217, 1) 0%, rgba(217, 217, 217, 0.26) 26%, rgba(0, 204, 133, 1) 100%)",
          }}
        />
  
        {/* grain overlay */}
        <div
          className="absolute inset-0 mix-blend-overlay pointer-events-none"
        />
  
        {/* content retains full opacity */}
        <div className="relative z-10 p-8">{children}</div>
      </div>
    );
  }