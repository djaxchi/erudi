import React from "react";
import { HashRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import LandingPage from "./pages/LandingPage";
import LocalModelsPage from "./pages/LocalModelsPage";
import AvailableModelsPage from "./pages/AvailableModelsPage";
import ChatPage from "./pages/ChatPage";
import ConversationPage from "./pages/ConversationPage";
import TrainingPage from "./pages/TrainingPage";
import ArenaPage from "./pages/ArenaPage";
import LoadingPage from "./pages/LoadingPage";
import { useState, useEffect } from "react";

export default function App() {
  const [backendReady, setBackendReady] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    let mounted = true;

    // Poll every 500ms until /health returns OK or we hit an error
    const checkBackend = async () => {
      try {
        const res = await fetch("http://127.0.0.1:8000/health");
        if (!mounted) return;
        if (res.ok) {
          setBackendReady(true);
          return;
        }
      } catch (e) {
        // ignore, retry
      }
      // After 10s of retries, show an error screen
      if (mounted && !backendReady && !error) {
        setTimeout(checkBackend, 500);
      }
    };

    checkBackend();

    return () => {
      mounted = false;
    };
  }, []);

  // While waiting for backend:
  if (!backendReady) {
    return <LoadingPage />;
  }

  // Once ready, render your normal router
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Navigate to="/main_window/models" replace />} />
        <Route path="/main_window" element={<Navigate to="/main_window/models" replace />} />
        <Route path="*" element={<Navigate to="/main_window/models" replace />} />
        <Route path="/main_window/chat" element={<ChatPage />} />
        <Route path="/main_window/models" element={<LandingPage />} />
        <Route path="/main_window/local-models" element={<LocalModelsPage />} />
        <Route path="/main_window/available-models" element={<AvailableModelsPage />} />
        <Route path="/main_window/conversations/:id" element={<ConversationPage />} />
        <Route path="/main_window/new-training" element={<TrainingPage />} />
        <Route path="/main_window/arena" element={<ArenaPage />} />
      </Routes>
    </Router>
  );
}