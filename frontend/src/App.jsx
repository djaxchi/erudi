import React, { useState, useEffect } from "react";
import { HashRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import LandingPage from "./pages/LandingPage";
import ChatPage from "./pages/ChatPage";
import ConversationPage from "./pages/ConversationPage";
import ArenaPage from "./pages/ArenaPage";
import KnowledgeBasePage from "./pages/KnowledgeBasePage";
import { DownloadModalProvider } from "./contexts/DownloadModalContext";
import { KnowledgeBaseProvider } from "./contexts/KnowledgeBaseContext";
import LoadingScreen from "./components/LoadingScreen";
import UpdateBanner from "./components/UpdateBanner";
import { apiClient } from "./services/api/client";
import { createLogger } from "./utils/logger";

const log = createLogger("App");

export default function App() {
  const [isBackendReady, setIsBackendReady] = useState(false);

  useEffect(() => {
    const checkBackendHealth = async () => {
      try {
        await apiClient.get("/health/");
        log.log("Backend is ready");
        setIsBackendReady(true);
      } catch (error) {
        log.warn("Backend not ready, retrying...", error);
        setTimeout(checkBackendHealth, 2000);
      }
    };
    checkBackendHealth();
  }, []);

  if (!isBackendReady) {
    return <LoadingScreen />;
  }

  return (
    <DownloadModalProvider>
      <KnowledgeBaseProvider>
        <UpdateBanner />
        <Router>
          <Routes>
            <Route path="/" element={<Navigate to="/erudi/models" replace />} />
            <Route path="/erudi" element={<Navigate to="/erudi/models" replace />} />
            <Route path="*" element={<Navigate to="/erudi/models" replace />} />
            <Route path="/erudi/chat" element={<ChatPage />} />
            <Route path="/erudi/models" element={<LandingPage />} />
            <Route path="/erudi/conversations/:id" element={<ConversationPage />} />
            <Route path="/erudi/arena" element={<ArenaPage />} />
            <Route path="/erudi/attach_knowledge_base" element={<KnowledgeBasePage />} />
          </Routes>
        </Router>
      </KnowledgeBaseProvider>
    </DownloadModalProvider>
  );
}
