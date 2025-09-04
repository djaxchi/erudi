import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Cpu } from "lucide-react";

export default function PreparingModal({ isOpen, onClose }) {
  const [visible, setVisible] = useState(isOpen);

  useEffect(() => {
    let timeout;
    let closeTimeout;

    if (isOpen) {
      setVisible(true);

      timeout = setTimeout(() => {
        setVisible(false); // start fade-out
        closeTimeout = setTimeout(onClose, 300); // wait for fade-out animation
      }, 10000); // auto close after 10s
    }

    return () => {
      clearTimeout(timeout);
      clearTimeout(closeTimeout);
    };
  }, [isOpen, onClose]);

  return (
    <AnimatePresence>
      {(isOpen || visible) && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: visible ? 1 : 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
          className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[9999] p-4"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            className="relative w-full max-w-md"
          >
            <div
              className={[
                "relative w-full rounded-[26px] overflow-hidden",
                "border border-white/10",
                "bg-[rgba(22,40,36,0.45)] backdrop-blur-[18px] saturate-[1.4]",
                "shadow-[0_8px_30px_-4px_rgba(0,0,0,0.45),0_2px_6px_-1px_rgba(0,0,0,0.4),inset_0_1px_0_rgba(255,255,255,0.06)]",
              ].join(" ")}
            >
              <div
                aria-hidden
                className="absolute inset-0 pointer-events-none rounded-[26px] mix-blend-overlay"
                style={{
                  background:
                    "linear-gradient(to bottom, rgba(255,255,255,0.18), rgba(255,255,255,0) 40%)",
                }}
              />
              <div
                aria-hidden
                className="absolute inset-0 pointer-events-none rounded-[26px] opacity-35 mix-blend-overlay"
                style={{
                  backgroundImage:
                    'url("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAABVUlEQVRYR+2WvQ3CMAyFPxF0AB1AB1ABN0AHcAF0gA3QATpN0lInyY5kUVqSk4TsSIv8P2RNFpBf6h8Bi5TBSW0AVbAAmwBpjqgA3wD1fYwHzwFR3QAdwDvl7T2JQG4C7gA/H8LwAVtFznGKnyD20PnKQqa5wzwwM3Vl8r9mQwZP4RFL9XPs35SHJxKcVd5jTwK9K1u4ErfJUF2XblI8g4BtMSSYlLQF41f+WAbc42t7CM6ikgs6Y2oT64y8G8BuEorQFrirN4i0cK4erQblIDmI+F6kAD0fYp2RchEot1Hc6S/T/lNa8T1nDjMDPxgg7wM8S+P8Gn8UH2Piu0mV9K/VLBbq+508Quy_ngGBrhV98yYzeBdOL4SqyGoccEqbE6+ZjKlj19qCxgY6N8lH3dy5zvY1/drdEw2d+uHMDuHwrK0Yas7PwAxRxmKJl0VokAAAAASUVORK5CYII=")',
                  backgroundSize: "200px 200px",
                }}
              />

              {/* Content */}
              <div className="relative z-10 p-6">
                <div className="flex items-center gap-4">
                  <div className="relative">
                    {/* Animated background glow */}
                    <motion.div
                      animate={{
                        scale: [1, 1.2, 1],
                        opacity: [0.3, 0.6, 0.3],
                      }}
                      transition={{
                        duration: 2,
                        repeat: Infinity,
                        ease: "easeInOut",
                      }}
                      className="absolute inset-0 bg-emerald-500/30 rounded-full blur-xl"
                    />

                    {/* Spinning border */}
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{
                        duration: 2,
                        repeat: Infinity,
                        ease: "linear",
                      }}
                      className="relative w-12 h-12 rounded-full border-4 border-white/20 border-t-emerald-400"
                    />

                    {/* Center icon */}
                    <div className="absolute inset-0 flex items-center justify-center">
                      <Cpu className="w-5 h-5 text-emerald-400" />
                    </div>
                  </div>

                  <div className="flex-1">
                    <h2 className="text-xl font-semibold tracking-tight text-[#F2F7F4] mb-1">
                      Preparing your model...
                    </h2>
                    <p className="text-sm text-gray-300/80">
                      Should be ready in a couple of minutes
                    </p>
                  </div>
                </div>

                <div className="mt-4 text-xs text-gray-400/60 text-center">
                  This dialog will close automatically
                </div>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
