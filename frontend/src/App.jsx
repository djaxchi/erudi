import React, { useState, useEffect } from "react";
import { HashRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import LandingPage from "./pages/LandingPage";
import ChatPage from "./pages/ChatPage";
import ConversationPage from "./pages/ConversationPage";
import TrainingPage from "./pages/TrainingPage";
import ArenaPage from "./pages/ArenaPage";
import KnowledgeBasePage from "./pages/KnowledgeBasePage";
import { DownloadModalProvider } from "./contexts/DownloadModalContext";
import { KnowledgeBaseProvider } from "./contexts/KnowledgeBaseContext";
import LoadingScreen from "./components/LoadingScreen";
import { API_BASE_URL } from "./config/api";

export default function App() {
  const [isBackendReady, setIsBackendReady] = useState(false);

  
  useEffect(() => {
    const checkBackendHealth = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/health`, {
          method: 'GET',
        });
        
        if (response.ok) {
          setIsBackendReady(true);
        } else {
          throw new Error('Backend not ready');
        }
      } catch (error) {
        setTimeout(checkBackendHealth, 2000);
      }
    };
    checkBackendHealth();
  }, []);

  if (!isBackendReady) {
    return <LoadingScreen />;
  } else {
    return (
      <DownloadModalProvider>
        <KnowledgeBaseProvider>
          <Router>
            <Routes>
              <Route path="/" element={<Navigate to="/erudi/models" replace />} />
              <Route path="/erudi" element={<Navigate to="/erudi/models" replace />} />
              <Route path="*" element={<Navigate to="/erudi/models" replace />} />
              <Route path="/erudi/chat" element={<ChatPage />} />
              <Route path="/erudi/models" element={<LandingPage />} />
              <Route path="/erudi/conversations/:id" element={<ConversationPage />} />
              <Route path="/erudi/new-training" element={<TrainingPage />} />
              <Route path="/erudi/arena" element={<ArenaPage />} />
              <Route path="/erudi/attach_knowledge_base" element={<KnowledgeBasePage />} />
            </Routes>
          </Router>
        </KnowledgeBaseProvider>
      </DownloadModalProvider>
    );
  }
}