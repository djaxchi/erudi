/**
 * Telemetry Service - Frontend
 * Tracks user interactions and sends to backend
 */

class TelemetryService {
  constructor() {
    this.userId = null;
    this.consentAccepted = false;
    this.baseUrl = 'http://127.0.0.1:8000';
  }

  /**
   * Initialize telemetry service and check consent
   */
  async initialize() {
    try {
      const response = await fetch(`${this.baseUrl}/telemetry/consent`);
      if (response.ok) {
        const data = await response.json();
        this.consentAccepted = data.beta_consent_accepted;
        this.userId = data.user_id;
        return data;
      }
    } catch (error) {
      console.error('Failed to initialize telemetry:', error);
    }
    return null;
  }

  /**
   * Set user consent
   */
  async setConsent(accepted) {
    try {
      const response = await fetch(`${this.baseUrl}/telemetry/consent`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ accepted }),
      });

      if (response.ok) {
        const data = await response.json();
        this.consentAccepted = data.beta_consent_accepted;
        this.userId = data.user_id;
        return true;
      }
    } catch (error) {
      console.error('Failed to set consent:', error);
    }
    return false;
  }

  /**
   * Track a telemetry event
   * Only sends if user has consented
   */
  async track(eventType, properties = {}) {
    // Don't send if no consent
    if (!this.consentAccepted) {
      return;
    }

    try {
      // Send in background, don't wait for response
      fetch(`${this.baseUrl}/telemetry/event`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          event_type: eventType,
          properties,
        }),
      }).catch(err => {
        // Silently fail - telemetry should never break the app
        console.debug('Telemetry event failed:', err);
      });
    } catch (error) {
      console.debug('Telemetry error:', error);
    }
  }

  // Convenience methods for common events

  trackPageView(pageName) {
    this.track('page_view', { page: pageName });
  }

  trackModelDownload(modelId, modelName) {
    this.track('model_download_start', {
      model_id: modelId,
      model_name: modelName,
    });
  }

  trackModelDownloadComplete(modelId, modelName, duration) {
    this.track('model_download_complete', {
      model_id: modelId,
      model_name: modelName,
      duration_seconds: duration,
    });
  }

  trackChatStart(modelId, modelName) {
    this.track('chat_start', {
      model_id: modelId,
      model_name: modelName,
    });
  }

  trackChatMessage(modelId, messageCount) {
    this.track('chat_message', {
      model_id: modelId,
      message_count: messageCount,
    });
  }

  trackConversationContext(modelId, context) {
    this.track('conversation_context', {
      model_id: modelId,
      conversation_id: context.conversationId,
      message_count: context.messageCount,
      total_user_messages: context.userMessageCount,
      total_assistant_messages: context.assistantMessageCount,
      conversation_duration_seconds: context.duration,
      has_custom_prompt: context.hasCustomPrompt,
      model_name: context.modelName,
      // Message metadata (privacy-friendly)
      user_message_length: context.userMessageLength,
      assistant_message_length: context.assistantMessageLength,
      response_time_seconds: context.responseTime,
      message_preview: context.messagePreview, // First 50 chars
      contains_code: context.containsCode,
      message_language: context.language,
    });
  }

  trackMessageInteraction(interactionType, messageId, modelId) {
    this.track('message_interaction', {
      interaction_type: interactionType, // 'copy', 'star', 'unstar'
      message_id: messageId,
      model_id: modelId,
    });
  }

  trackConversationEnd(modelId, context) {
    this.track('conversation_end', {
      model_id: modelId,
      conversation_id: context.conversationId,
      total_messages: context.messageCount,
      duration_seconds: context.duration,
      completed_naturally: context.completedNaturally, // vs navigated away
    });
  }
  
  // Helper to detect if message contains code
  detectCode(text) {
    // Simple heuristic: check for common code patterns
    const codePatterns = [
      /```[\s\S]*?```/g, // Markdown code blocks
      /`[^`]+`/g, // Inline code
      /\b(function|const|let|var|class|import|export|def|public|private)\b/g, // Keywords
      /[{}\[\];()]/g, // Brackets and semicolons
      /=>|->|::/g, // Arrow functions and scope operators
    ];
    
    return codePatterns.some(pattern => pattern.test(text));
  }
  
  // Helper to detect language (simple detection)
  detectLanguage(text) {
    // Very basic language detection
    const firstChars = text.slice(0, 100).toLowerCase();
    
    // Check for non-Latin scripts
    if (/[\u4e00-\u9fff]/.test(firstChars)) return 'chinese';
    if (/[\u3040-\u309f\u30a0-\u30ff]/.test(firstChars)) return 'japanese';
    if (/[\u0600-\u06ff]/.test(firstChars)) return 'arabic';
    if (/[\u0400-\u04ff]/.test(firstChars)) return 'cyrillic';
    
    // Default to latin-based (English, French, Spanish, etc.)
    return 'latin';
  }
  
  // Helper to create message preview (first N chars, sanitized)
  createMessagePreview(text, maxLength = 50) {
    if (!text) return '';
    
    // Remove newlines and extra spaces
    const cleaned = text.replace(/\s+/g, ' ').trim();
    
    // Truncate and add ellipsis if needed
    if (cleaned.length <= maxLength) return cleaned;
    return cleaned.slice(0, maxLength) + '...';
  }

  trackTrainingStart(modelId, datasetSize) {
    this.track('training_start', {
      model_id: modelId,
      dataset_size: datasetSize,
    });
  }

  trackTrainingComplete(modelId, duration, success) {
    this.track('training_complete', {
      model_id: modelId,
      duration_seconds: duration,
      success,
    });
  }

  trackKnowledgeBaseCreate(modelId, fileCount) {
    this.track('knowledge_base_create', {
      model_id: modelId,
      file_count: fileCount,
    });
  }

  trackArenaComparison(model1Id, model2Id) {
    this.track('arena_comparison', {
      model1_id: model1Id,
      model2_id: model2Id,
    });
  }

  trackFeatureUsage(featureName) {
    this.track('feature_usage', {
      feature: featureName,
    });
  }

  trackError(errorType, errorMessage, context = {}) {
    this.track('error_occurred', {
      error_type: errorType,
      error_message: errorMessage,
      ...context,
    });
  }

  trackSettingChange(settingName, newValue) {
    this.track('setting_change', {
      setting: settingName,
      value: newValue,
    });
  }

  // Helper functions for privacy-friendly message metadata
  createMessagePreview(text, maxLength = 50) {
    if (!text) return '';
    return text.substring(0, maxLength).replace(/\s+/g, ' ').trim() + (text.length > maxLength ? '...' : '');
  }

  detectCode(text) {
    // Detect if message contains code patterns
    const codePatterns = [
      /```/,  // Code blocks
      /`[^`]+`/,  // Inline code
      /\bfunction\s+\w+/,  // JavaScript/TypeScript function
      /\bclass\s+\w+/,  // Class definition
      /\bdef\s+\w+/,  // Python function
      /\bimport\s+/,  // Import statement
      /\bfrom\s+.*\s+import/,  // Python import
      /console\.log/,  // Console logging
      /<\/?\w+>/,  // HTML tags
    ];
    return codePatterns.some(pattern => pattern.test(text));
  }

  detectLanguage(text) {
    if (!text) return 'unknown';
    
    // Simple heuristic: if contains non-ASCII characters, likely non-English
    const hasNonAscii = /[^\x00-\x7F]/.test(text);
    
    // Check for common non-English patterns
    const hasCyrillic = /[а-яА-ЯёЁ]/.test(text);
    const hasCJK = /[\u4E00-\u9FFF\u3040-\u309F\u30A0-\u30FF]/.test(text);  // Chinese/Japanese
    const hasArabic = /[\u0600-\u06FF]/.test(text);
    
    if (hasCyrillic) return 'cyrillic';
    if (hasCJK) return 'cjk';
    if (hasArabic) return 'arabic';
    if (hasNonAscii) return 'other-non-english';
    
    return 'english';
  }

  calculateResponseTime(startTime, firstChunkTime) {
    if (!startTime || !firstChunkTime) return null;
    return (firstChunkTime - startTime) / 1000; // seconds
  }
}

// Create singleton instance
const telemetry = new TelemetryService();

export default telemetry;
