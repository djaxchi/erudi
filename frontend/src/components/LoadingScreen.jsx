import React, { useEffect, useState } from "react";
import PropTypes from "prop-types";

// Human labels for the backend's startup-progress phases (backend/run.py +
// the FastAPI lifespan emit these). Unknown/absent → a generic "Starting".
const PHASE_LABELS = {
  starting: "Starting Erudi…",
  preparing_database: "Preparing the database…",
  running_migrations: "Updating the database…",
  loading_catalog: "Loading the model catalog…",
  ready: "Almost ready…",
};

export default function LoadingScreen({ phase, firstRun }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const started = Date.now();
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(id);
  }, []);

  const label = PHASE_LABELS[phase] || "Starting Erudi…";

  return (
    <div
      className="fixed top-0 left-0 w-screen h-screen flex flex-col justify-center items-center z-[9999] px-8 text-center"
      style={{ backgroundColor: "#02130e" }}
    >
      <img
        src={require("../assets/images/logos/logoerudifinal.png")}
        alt="erudi Logo"
        className="mb-2 object-contain"
        style={{ maxWidth: "14rem", maxHeight: "14rem" }}
      />
      <p className="text-xl mt-1 mb-8" style={{ color: "#e0e0e0" }}>
        AI with you, for you
      </p>
      <div className="w-12 h-12 border-4 border-gray-200/20 border-t-gray-200/80 rounded-full animate-spin"></div>
      <p className="text-sm mt-6" style={{ color: "#cfd8d4" }}>
        {label} {elapsed > 0 && <span style={{ color: "#7c8f88" }}>({elapsed}s)</span>}
      </p>
      {firstRun && (
        <p className="text-xs mt-2 max-w-sm" style={{ color: "#9fb0aa" }}>
          First launch — this can take a minute while Erudi sets things up.
        </p>
      )}
    </div>
  );
}

LoadingScreen.propTypes = {
  phase: PropTypes.string,
  firstRun: PropTypes.bool,
};
