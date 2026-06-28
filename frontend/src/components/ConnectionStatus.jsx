import React, { useState, useEffect } from "react";
import { HelpCircle } from "lucide-react";
import Tooltip from "./Tooltip";

/**
 * Live internet-connection indicator for the bottom of the left rail. Uses the
 * browser's online/offline signal so it updates the moment the connection drops or
 * returns. When offline, Hugging Face search and downloads are unavailable; the
 * curated catalog and installed models still work.
 */
export default function ConnectionStatus() {
  const [online, setOnline] = useState(typeof navigator !== "undefined" ? navigator.onLine : true);

  useEffect(() => {
    const goOnline = () => setOnline(true);
    const goOffline = () => setOnline(false);
    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    return () => {
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
  }, []);

  return (
    <div
      className="flex items-center gap-2.5 px-4 py-3 border-t border-white/10"
      title={online ? "Connected to the internet" : "No internet connection"}
    >
      <span className="relative flex w-2.5 h-2.5">
        {online && (
          <span className="absolute inline-flex w-full h-full rounded-full bg-emerald-400/60 animate-ping" />
        )}
        <span
          className={`relative inline-flex w-2.5 h-2.5 rounded-full ${
            online ? "bg-emerald-400" : "bg-gray-500"
          }`}
        />
      </span>
      <span className="text-sm text-gray-300">{online ? "Connected" : "Offline"}</span>
      <Tooltip
        side="top-right"
        width="w-64"
        content="You can chat with installed models without internet. Installing new ones needs a connection."
      >
        <HelpCircle className="w-3.5 h-3.5 text-gray-400 hover:text-emerald-400 transition-colors cursor-help" />
      </Tooltip>
    </div>
  );
}
