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
import BetaConsentModal from "./components/BetaConsentModal";
import telemetry from "./services/telemetry";

export default function App() {
  const [isBackendReady, setIsBackendReady] = useState(false);
  const [showConsentModal, setShowConsentModal] = useState(false);
  const [consentChecked, setConsentChecked] = useState(false);

  
  useEffect(() => {
    const checkBackendHealth = async () => {
      try {
        const response = await fetch('http://127.0.0.1:8000/main_window/health', {
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

  // Check beta consent after backend is ready
  useEffect(() => {
    if (isBackendReady && !consentChecked) {
      checkConsent();
    }
  }, [isBackendReady, consentChecked]);

  const checkConsent = async () => {
    try {
      const consentData = await telemetry.initialize();
      
      if (consentData && !consentData.beta_consent_accepted) {
        setShowConsentModal(true);
      }
      
      setConsentChecked(true);
    } catch (error) {
      console.error('Failed to check consent:', error);
      setConsentChecked(true);
    }
  };

  const handleAcceptConsent = async () => {
    const success = await telemetry.setConsent(true);
    if (success) {
      setShowConsentModal(false);
      // Track app launch after consent
      telemetry.track('app_launched', {
        platform: navigator.platform,
        user_agent: navigator.userAgent,
      });
    }
  };

  const handleDeclineConsent = async () => {
    await telemetry.setConsent(false);
    // User declined, exit the app
    if (window.electronAPI && window.electronAPI.quit) {
      window.electronAPI.quit();
    } else {
      alert('Please close the application. Data collection consent is required for the beta version.');
    }
  };

  if (!isBackendReady || !consentChecked) {
    return <LoadingScreen />;
  }

  if (showConsentModal) {
    return (
      <BetaConsentModal 
        onAccept={handleAcceptConsent}
        onDecline={handleDeclineConsent}
      />
    );
  }

  return (
    <DownloadModalProvider>
      <KnowledgeBaseProvider>
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
      </KnowledgeBaseProvider>
    </DownloadModalProvider>
  );
}