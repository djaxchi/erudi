import React, { useState, useEffect, useCallback } from "react";
import { HashRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import LandingPage from "./pages/LandingPage";
import ChatPage from "./pages/ChatPage";
import ConversationPage from "./pages/ConversationPage";
import ArenaPage from "./pages/ArenaPage";
import KnowledgeBasePage from "./pages/KnowledgeBasePage";
import { DownloadModalProvider } from "./contexts/DownloadModalContext";
import { KnowledgeBaseProvider } from "./contexts/KnowledgeBaseContext";
import LoadingScreen from "./components/LoadingScreen";
import BackendErrorScreen from "./components/BackendErrorScreen";
import UpdateBanner from "./components/UpdateBanner";
import { apiClient } from "./services/api/client";
import { describeBackendError, isStartupError } from "./utils/backendStatus";
import { createLogger } from "./utils/logger";

const log = createLogger("App");

// Give up on the /health poll after this long and surface an error instead of
// spinning forever. Generous (boot-to-ready is normally ~17s) so a slow cold boot
// isn't flagged; overridable for E2E via window.__ERUDI_BACKEND_TIMEOUT_MS__.
const DEFAULT_HEALTH_TIMEOUT_MS = 90000;

export default function App() {
  const [isBackendReady, setIsBackendReady] = useState(false);
  const [backendError, setBackendError] = useState(null);
  const [retryNonce, setRetryNonce] = useState(0);

  // Packaged builds: the main process forwards backend lifecycle events. A
  // startup_error gets us off the spinner immediately with a real message.
  useEffect(() => {
    const unsubscribe = window.backendAPI?.onBackendEvent?.((evt) => {
      if (isStartupError(evt)) {
        log.warn("Backend startup error", evt);
        setBackendError(describeBackendError(evt));
      }
    });
    return () => {
      if (typeof unsubscribe === "function") unsubscribe();
    };
  }, []);

  // Canonical readiness signal (works in dev too): poll /health until it answers;
  // give up after the timeout so a silent hang never strands the user.
  useEffect(() => {
    let cancelled = false;
    let timer = null;
    const start = Date.now();
    const timeoutMs = Number(window.__ERUDI_BACKEND_TIMEOUT_MS__) || DEFAULT_HEALTH_TIMEOUT_MS;

    const poll = async () => {
      if (cancelled) return;
      try {
        await apiClient.get("/health/");
        if (!cancelled) {
          log.log("Backend is ready");
          setIsBackendReady(true);
        }
      } catch (error) {
        if (cancelled) return;
        if (Date.now() - start >= timeoutMs) {
          log.warn("Backend unreachable after timeout", error);
          setBackendError((prev) => prev || describeBackendError({ code: "BACKEND_UNREACHABLE" }));
          return;
        }
        log.warn("Backend not ready, retrying...", error);
        timer = setTimeout(poll, 2000);
      }
    };
    poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [retryNonce]);

  const handleRetry = useCallback(() => {
    setBackendError(null);
    setIsBackendReady(false);
    setRetryNonce((n) => n + 1);
  }, []);

  const handleQuit = useCallback(() => {
    window.close();
  }, []);

  if (backendError) {
    return <BackendErrorScreen error={backendError} onRetry={handleRetry} onQuit={handleQuit} />;
  }

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
