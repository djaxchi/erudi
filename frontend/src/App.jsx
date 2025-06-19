import React from "react";
import { HashRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import LandingPage from "./pages/LandingPage";
import LocalModelsPage from "./pages/LocalModelsPage";
import AvailableModelsPage from "./pages/AvailableModelsPage";
import ChatPage from "./pages/ChatPage";
import ConversationPage from "./pages/ConversationPage";
import TrainingPage from "./pages/TrainingPage";
import ArenaPage from "./pages/ArenaPage";

export default function App() {
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
