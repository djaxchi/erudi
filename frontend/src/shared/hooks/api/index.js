import { useState, useEffect, useCallback } from "react";
import { apiClient } from "../../../services/api/client";
import { createLogger } from "../../../utils/logger";

const log = createLogger("APIHooks");

/**
 * Custom hook for fetching local LLMs
 * @returns {Object} { llms, loading, error }
 */
export function useLLMs() {
  const [llms, setLlms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchLlms = async () => {
      try {
        setLoading(true);
        const data = await apiClient.get("/llms/local");
        setLlms(Array.isArray(data) ? data : []);
        setError(null);
      } catch (err) {
        log.error("Failed to fetch LLMs", err);
        setError(err);
      } finally {
        setLoading(false);
      }
    };

    fetchLlms();
  }, []);

  return { llms, loading, error };
}

/**
 * Custom hook for fetching a single conversation
 * @param {string} conversationId - Conversation ID
 * @returns {Object} { conversation, loading, error }
 */
export function useConversation(conversationId) {
  const [conversation, setConversation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!conversationId) {
      return;
    }

    const fetchConversation = async () => {
      try {
        setLoading(true);
        const data = await apiClient.get(`/conversations/${conversationId}`);
        setConversation(data);
        setError(null);
      } catch (err) {
        log.error(`Failed to fetch conversation ${conversationId}`, err);
        setError(err);
      } finally {
        setLoading(false);
      }
    };

    fetchConversation();
  }, [conversationId]);

  return { conversation, loading, error };
}

/**
 * Custom hook for fetching conversation messages
 * @param {string} conversationId - Conversation ID
 * @returns {Object} { messages, loading, error }
 */
export function useConversationMessages(conversationId) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!conversationId) {
      return;
    }

    const fetchMessages = async () => {
      try {
        setLoading(true);
        const data = await apiClient.get(`/conversations/${conversationId}/fetch_messages`);
        setMessages(Array.isArray(data) ? data : []);
        setError(null);
      } catch (err) {
        log.error(`Failed to fetch messages for conversation ${conversationId}`, err);
        setError(err);
      } finally {
        setLoading(false);
      }
    };

    fetchMessages();
  }, [conversationId]);

  return { messages, loading, error };
}

/**
 * Custom hook for fetching all conversations
 * @returns {Object} { conversations, loading, error }
 */
export function useConversations() {
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refetch = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiClient.get("/conversations/");
      setConversations(Array.isArray(data) ? data : []);
      setError(null);
    } catch (err) {
      log.error("Failed to fetch conversations", err);
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { conversations, loading, error, refetch };
}

/**
 * Custom hook for hardware training info
 * @returns {Object} { trainingInfo, loading, error }
 */
export function useTrainingInfo() {
  const [trainingInfo, setTrainingInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchTrainingInfo = async () => {
      try {
        setLoading(true);
        const data = await apiClient.get("/hardware/training_info");
        setTrainingInfo(data);
        setError(null);
      } catch (err) {
        log.error("Failed to fetch training info", err);
        setError(err);
      } finally {
        setLoading(false);
      }
    };

    fetchTrainingInfo();
  }, []);

  return { trainingInfo, loading, error };
}

/**
 * Custom hook for hardware app startup info
 * @returns {Object} { startupInfo, loading, error }
 */
export function useAppStartupInfo() {
  const [startupInfo, setStartupInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchStartupInfo = async () => {
      try {
        setLoading(true);
        const data = await apiClient.get("/hardware/app_startup");
        setStartupInfo(data);
        setError(null);
      } catch (err) {
        log.error("Failed to fetch app startup info", err);
        setError(err);
      } finally {
        setLoading(false);
      }
    };

    fetchStartupInfo();
  }, []);

  return { startupInfo, loading, error };
}

/**
 * Custom hook for backend health check
 * @returns {Object} { isHealthy, loading, error }
 */
export function useBackendHealth() {
  const [isHealthy, setIsHealthy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        setLoading(true);
        await apiClient.get("/health/");
        setIsHealthy(true);
        setError(null);
      } catch (err) {
        log.error("Backend health check failed", err);
        setIsHealthy(false);
        setError(err);
      } finally {
        setLoading(false);
      }
    };

    checkHealth();
  }, []);

  return { isHealthy, loading, error };
}
