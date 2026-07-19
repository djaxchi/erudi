import React, { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import ChatCollapsibleSection from "../components/ChatCollapsibleSection";
import QuestionInput from "../components/QuestionInput";
import HeaderBar from "../components/HeaderBar";
import CustomizePromptModal from "../components/modals/CustomizePromptModal";
import { Copy, Check, Star } from "lucide-react";
import TypingIndicator from "../components/TypingIndicator";
import MarkdownRenderer from "../components/MarkdownRenderer";
import TraceStrip from "../components/TraceStrip";
import { API_BASE_URL } from "../config/api.js";
import apiClient, { tracedFetch } from "../services/api/client";
import { createLogger } from "../utils/logger";
import { conversationPath } from "../utils/routes";
import { canAttachImages, maxImagesForModel } from "../utils/modelCapabilities";
import { getDisplayContent } from "../utils/messageContent";

const log = createLogger("ConversationPage");

export default function ConversationPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  const [messages, setMessages] = useState([]);
  const [copiedMessageId, setCopiedMessageId] = useState(null);
  const [starredIds, setStarredIds] = useState({});
  const [conversations, setConversations] = useState([]);
  const scrollRef = useRef(null);
  const [, setCurrentTitle] = useState("");

  const [showPromptModal, setShowPromptModal] = useState(false);
  const [customPrompt, setCustomPrompt] = useState("");
  const [initialHandled, setInitialHandled] = useState(false);
  const [loading, setLoading] = useState(false);
  const [models, setModels] = useState([]);
  const [currentModel, setCurrentModel] = useState("");
  // The conversation's assigned model id, recorded when the conversation loads.
  // The header picker's selected value is derived from this + `models` below.
  const [conversationLlmId, setConversationLlmId] = useState(null);
  // Both load independently; the orphan check below only fires once each has
  // resolved, so we never flash the "missing model" state during initial load.
  const [conversationLoaded, setConversationLoaded] = useState(false);
  const [modelsLoaded, setModelsLoaded] = useState(false);
  const [settings, setSettings] = useState({
    temperature: 0.2,
    topP: 0.5,
    maxTokens: 1024,
  });
  const [collapsed, setCollapsed] = useState(false);
  const [firstReplyPending, setFirstReplyPending] = useState(false);
  // A ref, not state: the scroll handler updates it on every scroll event, and
  // reading it from the auto-scroll effect must NOT re-run that effect. As state
  // it did (the effect depended on it), so toggling it near the bottom snapped
  // the view back down and the user could not scroll freely.
  const userScrolledUpRef = useRef(false);

  // Refs to avoid putting messages.length in useCallback deps, which
  // would cascade into the loadConversationData useEffect and overwrite
  // in-flight streaming state with stale DB data.
  const messagesLengthRef = useRef(0);
  messagesLengthRef.current = messages.length;
  const isStreamingRef = useRef(false);

  const toggleSidebar = () => {
    setCollapsed((prev) => !prev);
  };

  useEffect(() => {
    if (!window.fsAPI?.readImageAsDataURL) return;
    // undefined = not yet attempted; [] = attempted but file gone; [...] = loaded
    const needsRestore = messages.some(
      (m) => m.images === undefined && /\[image_path:[^\]]+\]/.test(m.content)
    );
    if (!needsRestore) return;
    let cancelled = false;
    (async () => {
      const restored = await Promise.all(
        messages.map(async (m) => {
          if (m.images !== undefined || !/\[image_path:[^\]]+\]/.test(m.content)) return m;
          const paths = [...m.content.matchAll(/\[image_path:([^\]]+)\]/g)].map((x) => x[1]);
          const images = (
            await Promise.all(
              paths.map((p) => window.fsAPI.readImageAsDataURL(p).catch(() => null))
            )
          ).filter(Boolean);
          return { ...m, images };
        })
      );
      if (!cancelled) setMessages(restored);
    })();
    return () => {
      cancelled = true;
    };
  }, [messages]);

  // Load the available models list. The header picker's selected value is
  // hydrated by the dedicated effect below, not here: the models list and the
  // conversation's assigned model arrive from two independent fetches and
  // either can win the race.
  useEffect(() => {
    tracedFetch(`${API_BASE_URL}/llms/local`)
      .then((res) => res.json())
      .then((data) => {
        setModels(Array.isArray(data) ? data : []);
      })
      .catch((err) => {
        log.error("Failed to fetch models", err);
      })
      .finally(() => {
        setModelsLoaded(true);
      });
  }, []);

  // Hydrate the header model picker's selected value once BOTH the models list
  // and the conversation's assigned llm_id are known. They come from two
  // independent effects with no guaranteed order, so deriving here (instead of
  // inside either loader) makes hydration order-independent and keeps the
  // picker populated on reopen and during generation (#217).
  useEffect(() => {
    if (conversationLlmId === null || models.length === 0) {
      return;
    }
    const model = models.find((m) => m.id === conversationLlmId);
    if (model) {
      setCurrentModel(model.name);
    }
  }, [conversationLlmId, models]);

  const handleModelChange = async (modelName) => {
    setCurrentModel(modelName);
    const model = models.find((m) => m.name === modelName);
    if (!model) {
      return;
    }
    // Keep the derived-picker source of truth aligned with the new selection.
    setConversationLlmId(model.id);
    // Call API to update conversation's llm_id
    await tracedFetch(`${API_BASE_URL}/conversations/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ llm_id: model.id }),
    });
    // // Optionally, refresh conversations state here
    // fetchMessagesAndConversations();
  };

  // Function to save conversation parameters
  const saveConversationParameters = async (newSettings, newCustomPrompt) => {
    try {
      await tracedFetch(`${API_BASE_URL}/conversations/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          temperature: newSettings.temperature,
          top_p: newSettings.topP,
          max_tokens: newSettings.maxTokens,
          // ?? (not ||): an explicit empty string means "clear the prompt"
          // and must be persisted as-is, not swallowed by the state fallback.
          custom_prompt: newCustomPrompt ?? customPrompt,
        }),
      });
    } catch (error) {
      log.error("Failed to save conversation parameters", error);
    }
  };

  const fetchMessagesAndConversations = useCallback(async () => {
    try {
      const [msgRes, convRes] = await Promise.all([
        tracedFetch(`${API_BASE_URL}/conversations/${id}/fetch_messages`),
        tracedFetch(`${API_BASE_URL}/conversations/`),
      ]);
      const msgs = await msgRes.json();
      // initialize starred state from backend
      const starredMap = {};
      msgs.forEach((m) => {
        if (m.starred) {
          starredMap[m.id] = true;
        }
      });
      setStarredIds(starredMap);
      const convs = await convRes.json();
      convs.sort((a, b) => new Date(b.last_message_time) - new Date(a.last_message_time));
      setMessages((prev) => msgs.map((m, i) => ({ ...m, images: prev[i]?.images || m.images })));
      setConversations(convs);
    } catch (err) {
      log.error("Failed to fetch messages and conversations", err);
    }
  }, [id]);

  const handleAskWithParams = useCallback(
    async (
      question,
      images = [],
      explicitSettings = null,
      explicitCustomPrompt = null,
      imagePaths = []
    ) => {
      const settingsToUse = explicitSettings || settings;
      const customPromptToUse = explicitCustomPrompt !== null ? explicitCustomPrompt : customPrompt;

      setLoading(true);
      isStreamingRef.current = true;

      const isFirstMessage = messagesLengthRef.current === 0;

      if (isFirstMessage) {
        setCurrentTitle("");
        setFirstReplyPending(true);
      }

      const userMessage = {
        id: Date.now(),
        sender: "user",
        content: question,
        images,
      };

      const assistantMessage = {
        id: Date.now() + 1,
        sender: "llm",
        content: "",
        // Live NDJSON trace (#90): thinking / tool_call / tool_result events
        // collected as they stream, replayed by the TraceStrip above the bubble.
        // `streaming` gates the strip's expanded-while-only-content behavior.
        trace: [],
        streaming: true,
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);

      try {
        // Start title generation in parallel (don't await) so it doesn't block streaming
        if (isFirstMessage) {
          (async () => {
            try {
              const titleRes = await tracedFetch(
                `${API_BASE_URL}/conversations/${id}/generate_title`,
                {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ question }),
                }
              );

              if (titleRes.ok) {
                const reader = titleRes.body.getReader();
                const decoder = new TextDecoder("utf-8");
                let fullTitle = "";

                let titleDone = false;
                while (!titleDone) {
                  const { done, value } = await reader.read();
                  titleDone = done;
                  if (done) {
                    break;
                  }

                  const chunk = decoder.decode(value, { stream: true });
                  fullTitle += chunk;

                  setCurrentTitle(() => {
                    setConversations((prevConvs) =>
                      prevConvs.map((conv) =>
                        conv.id === Number(id)
                          ? { ...conv, name: fullTitle.trim() || "New Conversation" }
                          : conv
                      )
                    );
                    return fullTitle;
                  });
                }
              }
            } catch (err) {
              log.error("Title generation failed", err);
            }
          })();
        }

        // Stream response using fetch + ReadableStream
        const responseRes = await tracedFetch(`${API_BASE_URL}/conversations/${id}/query`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            question,
            images,
            image_paths: imagePaths,
            temperature: settingsToUse.temperature,
            top_p: settingsToUse.topP,
            max_new_tokens: settingsToUse.maxTokens,
            custom_prompt: customPromptToUse,
          }),
        });

        if (responseRes.ok) {
          // NDJSON reader (#90): the body is one JSON event per line
          // (application/x-ndjson). We split on "\n" and carry the trailing
          // partial line across reads. Answer events stream into the bubble
          // exactly as raw text did before; thinking / tool_call / tool_result
          // accrue into the message's live trace; error maps to the red bubble;
          // done is terminal. Unknown event types are ignored (forward compat).
          // NOTE: the title-gen reader above is a SEPARATE plain-text loop.
          const reader = responseRes.body.getReader();
          const decoder = new TextDecoder("utf-8");
          let buffer = ""; // partial-line carry across reads
          let answerText = ""; // accumulated answer bubble text
          const traceEvents = []; // ordered thinking / tool_call / tool_result
          let gotFirstEvent = false;
          let sawError = false;
          let sawDone = false;

          // Push the current accumulators onto the streaming assistant message.
          const flushMessage = () => {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMessage.id
                  ? { ...msg, content: answerText, trace: traceEvents.slice() }
                  : msg
              )
            );
          };

          const handleEvent = (evt) => {
            if (!evt || typeof evt !== "object") {
              return;
            }
            switch (evt.t) {
              case "answer":
                answerText += evt.text || "";
                break;
              case "thinking":
              case "tool_call":
              case "tool_result":
                traceEvents.push(evt);
                break;
              case "error":
                // The wire error event replaces the old in-band sentinel; map it
                // back to the SAME red bubble the persisted sentinel produces
                // (getDisplayContent / bubbleClass detect the sentinel substring).
                // The backend error text is already sentinel-prefixed.
                sawError = true;
                answerText =
                  evt.text ||
                  "[ERROR_MESSAGE_SYSTEM] I apologize, but I encountered an error while generating a response. Please try asking your question again.";
                break;
              case "done":
                sawDone = true;
                break;
              default:
                // Unknown event type: ignore for forward compatibility.
                break;
            }
          };

          const processLine = (rawLine) => {
            const line = rawLine.trim();
            if (!line) {
              return;
            }
            let evt;
            try {
              evt = JSON.parse(line);
            } catch (parseError) {
              log.error("Failed to parse NDJSON line", parseError);
              return;
            }
            handleEvent(evt);
            if (!gotFirstEvent) {
              gotFirstEvent = true;
              setLoading(false);
              setFirstReplyPending(false);
            }
            flushMessage();
          };

          try {
            let responseDone = false;
            while (!responseDone && !sawDone) {
              const { done, value } = await reader.read();
              responseDone = done;
              if (done) {
                break;
              }

              buffer += decoder.decode(value, { stream: true });
              let newlineIdx;
              while (!sawDone && (newlineIdx = buffer.indexOf("\n")) !== -1) {
                const rawLine = buffer.slice(0, newlineIdx);
                buffer = buffer.slice(newlineIdx + 1);
                processLine(rawLine);
              }
            }
            // Defensive flush of any trailing line (NDJSON ends every line with
            // "\n", so this normally no-ops).
            if (!sawDone && buffer.trim()) {
              processLine(buffer);
              buffer = "";
            }
          } catch (streamError) {
            log.error("Streaming error during response generation", streamError);
            answerText +=
              "\n\n[ERROR_MESSAGE_SYSTEM] Connection interrupted while generating response.";
            sawError = true;
            flushMessage();
          } finally {
            assistantMessage.content = answerText;
            // Turn is over: stop the live strip (it settles to the collapsed
            // summary) and drop the trace on an error turn to match persisted
            // history (the backend persists no trace for error turns).
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMessage.id
                  ? {
                      ...msg,
                      content: answerText,
                      trace: sawError ? null : traceEvents.slice(),
                      streaming: false,
                    }
                  : msg
              )
            );
          }
        } else {
          log.error("Server error during response generation", { status: responseRes.status });

          try {
            await tracedFetch(`${API_BASE_URL}/conversations/${id}/store_error_message`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
            });
          } catch (storeError) {
            log.error("Failed to store error message", storeError);
          }

          assistantMessage.content =
            "[ERROR_MESSAGE_SYSTEM] I apologize, but I encountered an error while generating a response. Please try asking your question again.";
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessage.id
                ? { ...msg, content: assistantMessage.content, trace: null, streaming: false }
                : msg
            )
          );
        }
      } catch (err) {
        log.error("Failed to send message", err);
      }

      isStreamingRef.current = false;
      await fetchMessagesAndConversations();

      if (isFirstMessage) {
        setTimeout(() => setCurrentTitle(""), 3000);
        setFirstReplyPending(false);
      }

      setLoading(false);
    },
    [id, fetchMessagesAndConversations]
  );

  const handleAsk = useCallback(
    async (question, images = [], imagePaths = []) => {
      return handleAskWithParams(question, images, settings, customPrompt, imagePaths);
    },
    [handleAskWithParams, settings, customPrompt]
  );

  // Load conversation data when ID changes
  useEffect(() => {
    if (!id) {
      return;
    }

    // Don't overwrite in-flight streaming state with stale DB data
    if (isStreamingRef.current) {
      return;
    }

    const loadConversationData = async () => {
      // Re-check inside async in case streaming started between effect trigger and execution
      if (isStreamingRef.current) {
        return;
      }

      try {
        const [convRes, msgRes, convDetailRes] = await Promise.all([
          tracedFetch(`${API_BASE_URL}/conversations/`),
          tracedFetch(`${API_BASE_URL}/conversations/${id}/fetch_messages`),
          tracedFetch(`${API_BASE_URL}/conversations/${id}`),
        ]);

        // Load conversations
        const convs = await convRes.json();
        convs.sort((a, b) => new Date(b.last_message_time) - new Date(a.last_message_time));
        setConversations(convs);

        // Load messages
        const msgs = await msgRes.json();
        const starredMap = {};
        msgs.forEach((m) => {
          if (m.starred) {
            starredMap[m.id] = true;
          }
        });
        setStarredIds(starredMap);
        setMessages((prev) => msgs.map((m, i) => ({ ...m, images: prev[i]?.images || m.images })));

        // Load conversation parameters
        if (convDetailRes.ok) {
          const conversation = await convDetailRes.json();
          setSettings({
            temperature: conversation.temperature,
            topP: conversation.top_p,
            maxTokens: conversation.max_tokens,
          });
          setCustomPrompt(conversation.custom_prompt || "");

          // Record the conversation's assigned model; the header picker's
          // selected value is derived from this + the models list in the
          // dedicated effect above, so hydration no longer depends on which
          // of the two fetches lands first (#217).
          setConversationLlmId(conversation.llm_id);
          // llm_id can be null after the model was deleted (conversations
          // survive, no auto-fallback, #225). Marking the detail loaded lets
          // the orphan check below decide whether to block the composer.
          setConversationLoaded(true);
        }
      } catch (err) {
        log.error("Failed to fetch conversations", err);
      }

      if (location.state && location.state.initialQuestion && !initialHandled) {
        setInitialHandled(true);

        const settingsToUse = location.state.initialSettings || settings;
        const customPromptToUse = location.state.initialCustomPrompt || customPrompt;

        if (location.state.initialSettings) {
          setSettings(location.state.initialSettings);
        }

        if (location.state.initialCustomPrompt) {
          setCustomPrompt(location.state.initialCustomPrompt);
        }

        await handleAskWithParams(
          location.state.initialQuestion,
          location.state.initialImages || [],
          settingsToUse,
          customPromptToUse,
          location.state.initialImagePaths || []
        );
        navigate(location.pathname, { replace: true, state: {} });
      } else if (!location.state || !location.state.initialQuestion) {
        try {
          const msgs = await apiClient.get(`/conversations/${id}/fetch_messages`);
          // initialize starred state on initial load
          const starredMap = {};
          msgs.forEach((m) => {
            if (m.starred) {
              starredMap[m.id] = true;
            }
          });
          setStarredIds(starredMap);
          setMessages((prev) => {
            const imagesByContent = new Map(
              prev.filter((m) => m.images?.length > 0).map((m) => [m.content, m.images])
            );
            return msgs.map((m) => ({ ...m, images: imagesByContent.get(m.content) || m.images }));
          });
        } catch (err) {
          log.error("Failed to fetch messages", err);
        }
      }
    };

    loadConversationData();
  }, [id, location.state, handleAskWithParams, navigate, location.pathname, initialHandled]);

  // Detect when user manually scrolls
  useEffect(() => {
    const scrollContainer = scrollRef.current;
    if (!scrollContainer) {
      return;
    }

    let scrollTimeout;
    let lastScrollTop = scrollContainer.scrollTop;

    const handleScroll = () => {
      const currentScrollTop = scrollContainer.scrollTop;

      // If user scrolled up (not down), immediately stop auto-scrolling
      if (currentScrollTop < lastScrollTop) {
        userScrolledUpRef.current = true;
      }

      lastScrollTop = currentScrollTop;

      // Clear any pending timeout
      clearTimeout(scrollTimeout);

      // Wait a bit before checking position to avoid false positives during auto-scroll
      scrollTimeout = setTimeout(() => {
        const { scrollTop, scrollHeight, clientHeight } = scrollContainer;
        const isAtBottom = scrollHeight - scrollTop - clientHeight < 100; // Increased threshold to 100px

        // Only mark as scrolled up if user is significantly away from bottom
        userScrolledUpRef.current = !isAtBottom;
      }, 100); // Small delay to debounce
    };

    scrollContainer.addEventListener("scroll", handleScroll);
    return () => {
      clearTimeout(scrollTimeout);
      scrollContainer.removeEventListener("scroll", handleScroll);
    };
  }, []);

  // Auto-scroll only when streaming is done or user hasn't scrolled up
  useEffect(() => {
    // Only auto-scroll if user hasn't manually scrolled up
    // OR if loading just finished (scroll once to final position)
    if (scrollRef.current && !userScrolledUpRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages]);

  const handleConversationClick = (newId) => navigate(conversationPath(newId));

  const handleRename = (cid, newName) =>
    setConversations((prev) => prev.map((c) => (c.id === cid ? { ...c, name: newName } : c)));

  const handleDelete = async (cid) => {
    // Ownership contract (#228): ChatCollapsibleSection owns the DELETE request.
    // This parent handler runs AFTER the child has deleted and does post-delete
    // UI only — optimistic filter, server refresh, and navigating away from a
    // now-deleted open conversation. It must NOT issue its own DELETE, or the
    // request fires twice (~10ms apart, distinct request ids).
    setConversations((prev) => prev.filter((conv) => conv.id !== cid));
    await fetchMessagesAndConversations();
    if (cid === Number(id)) {
      navigate("/erudi/chat");
    }
  };

  // Toggle star state optimistically, then reconcile with the server.
  const toggleStar = async (msgId) => {
    const isStarred = starredIds[msgId];
    const url = `${API_BASE_URL}/conversations/${isStarred ? "unstar_message" : "star_message"}`;
    // Optimistic: flip immediately so the star responds on click.
    setStarredIds((prev) => ({ ...prev, [msgId]: !isStarred }));
    try {
      const res = await tracedFetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message_id: msgId }),
      });
      // fetch only rejects on network errors — a non-ok status is also a failure.
      if (!res.ok) {
        throw new Error(`star toggle failed with status ${res.status}`);
      }
    } catch (err) {
      // Rollback must stay SILENT (owner decision, #136): no toast, no modal —
      // a star is low-stakes, so the only trace is this debug-level log line.
      setStarredIds((prev) => ({ ...prev, [msgId]: isStarred }));
      log.debug("Star toggle failed, reverting optimistic update", err);
    }
  };

  // Orphaned conversation (#225): its assigned model was deleted (llm_id null)
  // or no longer exists in the installed list. Sending is blocked and the header
  // picker turns red until the user explicitly switches to an installed model.
  // An assigned model whose weights are gone (an orphaned KB assistant,
  // weights_available === false) can only fail, so it blocks the same way;
  // undefined/null weights_available (remote or older backend) never blocks.
  const assignedModel = models.find((m) => m.id === conversationLlmId);
  const isModelOrphaned =
    conversationLoaded &&
    modelsLoaded &&
    (conversationLlmId === null || !assignedModel || assignedModel.weights_available === false);

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        disabled={loading}
        showCollapsible={true}
        onToggleSidebar={toggleSidebar}
        collapsed={collapsed}
      />

      <aside
        className={`relative bg-[#272727] text-white transition-all duration-300 ease-in-out ${
          collapsed ? "w-0 p-0" : "w-80 p-6 flex flex-col"
        }`}
      >
        {!collapsed && (
          <>
            <h1 className="text-3xl font-bold mb-6 flex-shrink-0">History</h1>
            {/*<ChatCollapsibleSection title="Hot Chats"
              disabled={loading}
            />} coming in next version*/}
            <div className="flex-1 mb-4 overflow-hidden">
              <ChatCollapsibleSection
                title="Previous Chats"
                items={conversations}
                selectedId={Number(id)}
                onSelect={handleConversationClick}
                onRename={handleRename}
                onDelete={handleDelete}
                disabled={loading}
              />
            </div>
          </>
        )}
      </aside>
      <main className="flex-1 flex flex-col bg-gradient-to-br from-[#041915] to-[#0f2d27] overflow-hidden">
        <div className="relative flex justify-center w-full px-8 pt-6">
          <HeaderBar
            initialTemperature={settings.temperature}
            initialTopP={settings.topP}
            initialMaxTokens={settings.maxTokens}
            onApply={(newSettings) => {
              setSettings(newSettings);
              saveConversationParameters(newSettings, customPrompt);
            }}
            onCustomizePrompt={() => setShowPromptModal(true)}
            disabled={loading}
            models={models}
            currentModel={currentModel}
            onModelChange={handleModelChange}
            pickerAttention={isModelOrphaned}
            pickerAttentionMessage="Please select a model"
          />
        </div>

        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto px-10 pt-10 pb-4"
          style={{
            scrollbarWidth: "none",
            msOverflowStyle: "none",
          }}
        >
          <style>{"::-webkit-scrollbar { display: none; }"}</style>
          <div className="flex flex-col gap-6">
            {messages.map((msg) => {
              const isUser = msg.sender === "user";
              const isError = !isUser && msg.content.includes("[ERROR_MESSAGE_SYSTEM]");
              const alignmentClass = isUser ? "items-end" : "items-start";
              const bubbleClass = isUser
                ? "bg-[#191919] ml-auto rounded-tr-none text-white"
                : isError
                  ? "text-red-400 mr-auto rounded-tl-none"
                  : " text-white mr-auto rounded-tl-none";

              // Reasoning/trace strip (#90): only for assistant turns that carried
              // non-answer activity, never for error turns (they have no trace,
              // matching persisted history). `traceLive` is true while the strip
              // is the only content (streaming, no answer yet) -> expanded; it
              // flips false on the first answer event -> auto-collapse.
              const traceEvents = !isUser ? msg.trace : null;
              const showTrace =
                !isUser && !isError && Array.isArray(traceEvents) && traceEvents.length > 0;
              const traceLive = showTrace && !!msg.streaming && !msg.content;

              // Show TypingIndicator for assistant messages that are loading, but
              // not once the live trace strip has taken over the pre-answer wait.
              const showTypingIndicator = !isUser && loading && !msg.content && !showTrace;

              // Attached images (this session) render in their OWN panel,
              // separate from the text bubble. `displayText` is the readable
              // text with internal attachment markers stripped.
              const hasImages = isUser && msg.images?.length > 0;
              const displayText = getDisplayContent(msg.content);

              return (
                <div key={msg.id} className={`group flex flex-col mb-2 ${alignmentClass}`}>
                  {showTrace && <TraceStrip events={traceEvents} live={traceLive} />}
                  {/* Attached images: their OWN glass panel (chat-header
                      material), a sibling of the text bubble, not nested in it. */}
                  {hasImages && (
                    <div
                      className={[
                        "mb-2 w-fit max-w-[75%] rounded-2xl p-2",
                        "border border-white/10",
                        "bg-[rgba(22,40,36,0.45)] backdrop-blur-[18px] saturate-[1.4]",
                      ].join(" ")}
                    >
                      <div className="flex flex-wrap gap-2">
                        {msg.images.map((src, i) => (
                          <img
                            key={i}
                            src={src}
                            alt={`attachment ${i + 1}`}
                            className="max-h-64 max-w-full rounded-xl border border-white/10"
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Text bubble. Skipped for an image-only user message so no
                      empty bubble shows beneath the picture. */}
                  {(!hasImages || displayText || showTypingIndicator) && (
                    <div
                      className={`break-words w-fit max-w-[75%] p-4 rounded-2xl overflow-wrap break-word ${bubbleClass}`}
                    >
                      {showTypingIndicator ? (
                        <div className="flex flex-col gap-2">
                          <div className="flex items-start pt-1">
                            <TypingIndicator size={8} colorClass="bg-gray-400" className="-mt-1" />
                          </div>
                          {firstReplyPending && (
                            <div className="text-xs text-gray-400 italic mt-1">
                              First response may take a bit longer while loading the model into
                              memory...
                            </div>
                          )}
                        </div>
                      ) : isUser || msg.content.includes("[ERROR_MESSAGE_SYSTEM]") ? (
                        // Keep user messages and error messages as plain text.
                        <div className="flex flex-col gap-2">
                          {/* Reloaded sessions without image bytes: placeholder
                              markers, only when there are no real images above. */}
                          {!hasImages &&
                            (() => {
                              const fallbackCount = (
                                msg.content.match(/\[image\]|\[image_path:[^\]]*\]/g) || []
                              ).length;
                              return Array.from({ length: fallbackCount }, (_, i) => (
                                <span
                                  key={i}
                                  className="inline-flex items-center gap-1 text-xs text-[var(--ink-faint)] border border-[var(--line)] rounded px-2 py-0.5 w-fit"
                                >
                                  🖼 image attachment
                                </span>
                              ));
                            })()}
                          {displayText && (
                            <pre className="whitespace-pre-wrap font-sans">{displayText}</pre>
                          )}
                        </div>
                      ) : (
                        // Assistant normal messages: render markdown
                        <MarkdownRenderer content={msg.content} />
                      )}
                    </div>
                  )}
                  <div className="flex mt-1 space-x-2 opacity-0 group-hover:opacity-100">
                    {/* Copy button */}
                    <button
                      onClick={() => {
                        // Copy the readable text the user sees, not the raw
                        // stored content with internal attachment markers.
                        navigator.clipboard.writeText(getDisplayContent(msg.content)).then(() => {
                          setCopiedMessageId(msg.id);
                          setTimeout(() => setCopiedMessageId(null), 1000);
                        });
                      }}
                      className="text-gray-400 hover:text-white transition-colors"
                      title="Copy message"
                    >
                      {copiedMessageId === msg.id ? (
                        <Check size={16} className="text-green-400" />
                      ) : (
                        <Copy size={16} />
                      )}
                    </button>
                    {/* Star button */}
                    <button
                      onClick={() => toggleStar(msg.id)}
                      className="text-gray-400 hover:text-white transition-colors"
                      title="Star message"
                    >
                      <Star
                        size={16}
                        className={starredIds[msg.id] ? "text-yellow-400" : ""}
                        fill={starredIds[msg.id] ? "currentColor" : "none"}
                      />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
        <div className="sticky bottom-0 left-0 right-0 px-10 py-10 backdrop-blur-md flex justify-center w-full">
          <div className="w-full max-w-lg">
            <QuestionInput
              onSend={handleAsk}
              disabled={loading || isModelOrphaned}
              canAttachImages={canAttachImages(models.find((m) => m.name === currentModel))}
              maxImages={maxImagesForModel(models.find((m) => m.name === currentModel))}
            />
          </div>
        </div>
      </main>

      {/* Customize Prompt Modal */}
      <CustomizePromptModal
        isOpen={showPromptModal}
        onClose={() => setShowPromptModal(false)}
        customPrompt={customPrompt}
        onSave={(newPrompt) => {
          // Saving in the modal persists immediately — closing without
          // clicking Apply in the header must not lose the prompt (#136).
          setCustomPrompt(newPrompt);
          saveConversationParameters(settings, newPrompt);
        }}
        title="Customize System Prompt"
      />
    </div>
  );
}
