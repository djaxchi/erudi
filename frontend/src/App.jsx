import React from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import LandingPage from "./pages/LandingPage";
import LocalModelsPage from "./pages/LocalModelsPage";
import AvailableModelsPage from "./pages/AvailableModelsPage";
import ChatPage from "./pages/ChatPage";
import TrainingPage from "./pages/TrainingPage";
import ConversationPage from "./pages/ConversationPage";

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/main_window" element={<Navigate to="/main_window/models" replace />} />
        <Route path="/main_window/chat" element={<ChatPage />} />
        <Route path="/main_window/models" element={<LandingPage />} />
        <Route path="/main_window/local-models" element={<LocalModelsPage />} />
        <Route path="/main_window/available-models" element={<AvailableModelsPage />} />
        <Route path="/main_window/new-training" element={<TrainingPage />} />
        <Route path="/main_window/conversations/:id" element={<ConversationPage />} />
        </Routes>
    </Router>
  );
}
