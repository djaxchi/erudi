import React, { useState, useEffect } from "react";
import { HashRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import LandingPage from "./pages/LandingPage";
import ChatPage from "./pages/ChatPage";
import ConversationPage from "./pages/ConversationPage";
import TrainingPage from "./pages/TrainingPage";
import ArenaPage from "./pages/ArenaPage";
import KnowledgeBasePage from "./pages/KnowledgeBasePage";
import { DownloadModalProvider } from "./contexts/DownloadModalContext";
import LoadingScreen from "./components/LoadingScreen";

export default function App() {
  const [isBackendReady, setIsBackendReady] = useState(false);

  useEffect(() => {
    const api = window.electron;
    if (!api) return;
    
    // Au montage, interroge l'état et bascule direct si déjà prêt
    api.getBackendStatus?.().then(s => {
      if (s?.backendReady) setIsBackendReady(true);
    });
    
    const detach = api.onBackendEvent(evt => {
      if (evt.event === 'ready') {
        setIsBackendReady(true);
      }
    });
    return () => detach && detach();
  }, []);

  if (!isBackendReady) {
    return <LoadingScreen />;
  } else {
    return (
      <DownloadModalProvider>
        <Router>
          <Routes>
            <Route path="/" element={<Navigate to="/main_window/models" replace />} />
            <Route path="/main_window" element={<Navigate to="/main_window/models" replace />} />
            <Route path="*" element={<Navigate to="/main_window/models" replace />} />
            <Route path="/main_window/chat" element={<ChatPage />} />
            <Route path="/main_window/models" element={<LandingPage />} />
            <Route path="/main_window/conversations/:id" element={<ConversationPage />} />
            <Route path="/main_window/new-training" element={<TrainingPage />} />
            <Route path="/main_window/arena" element={<ArenaPage />} />
            <Route path="/main_window/attach_knowledge_base" element={<KnowledgeBasePage />} />
          </Routes>
        </Router>
      </DownloadModalProvider>
    );
  }
}