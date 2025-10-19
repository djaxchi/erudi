// widget.js - adapted for StreamingResponse that yields LLM tokens
// Assumptions:
// - API_BASE = http://127.0.0.1:8000/erudi
// - /llms/local GET -> list of models
// - POST /conversations/ -> create conversation (returns object with id)
// - POST /conversations/{id}/query -> accepts JSON payload with keys:
//     { question, custom_prompt, temperature, top_p, max_new_tokens, n_last_turns_to_get }
//   and returns a StreamingResponse that yields tokens (text/plain chunks).
//
// Behavior:
// - stream tokens as they arrive and append them immediately into the LLM message element
// - abort after TIMEOUT_MS if no data (configurable)
// - fallback to mock streaming if anything fails

(function() {
  const API_BASE = "http://127.0.0.1:8000/erudi";
  const TIMEOUT_MS = 2 * 60 * 1000; // 2 minutes timeout for streaming

  const root = document.getElementById("erudit-root");
  const modelBtn = document.getElementById("modelBtn");
  const settingsToggle = document.getElementById("settingsToggle");
  const settingsPanel = document.getElementById("settingsPanel");
  const customPrompt = document.getElementById("customPrompt");
  const temperatureInput = document.getElementById("temperature");
  const topPInput = document.getElementById("topP");
  const maxTokensInput = document.getElementById("maxTokens");
  const applyBtn = document.getElementById("applySettingsBtn");
  const messages = document.getElementById("messages");
  const inputText = document.getElementById("inputText");
  const sendBtn = document.getElementById("sendBtn");
  const closeBtn = document.getElementById("closeBtn");
  const modalOverlay = document.getElementById("modalOverlay");
  const modalOkBtn = document.getElementById("modalOkBtn");

  // state
  let models = [];
  let selectedModel = null;
  let settings = {
    temperature: 0.7,
    top_p: 0.95,
    max_tokens: 1024,
    custom_prompt: ""
  };
  let conversationId = null; // in-memory only
  let currentStreamController = null;

  // UI helpers
  function appendUser(text) {
    const el = document.createElement("div");
    el.className = "msg user";
    el.textContent = text;
    messages.appendChild(el);
    scrollBottom();
    return el;
  }
  function appendLLMPlaceholder() {
    const el = document.createElement("div");
    el.className = "msg llm";
    el.textContent = ""; // will be filled while streaming
    messages.appendChild(el);
    scrollBottom();
    return el;
  }
  function scrollBottom() {
    messages.scrollTop = messages.scrollHeight;
  }
  function showNoModelModal() {
    modalOverlay.classList.remove("hidden");
  }
  modalOkBtn.addEventListener("click", () => modalOverlay.classList.add("hidden"));

  // load models
  async function loadModels() {
    modelBtn.textContent = "Loading models… ▾";
    try {
      const res = await fetch(`${API_BASE}/llms/local`, { method: "GET" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!Array.isArray(data) || data.length === 0) {
        models = [];
        selectedModel = null;
        modelBtn.textContent = "No model ▾";
        showNoModelModal();
        return;
      }
      models = data;
      selectedModel = models[0];
      modelBtn.textContent = (selectedModel.name || selectedModel.id || "model") + " ▾";
    } catch (err) {
      console.warn("Failed to load models:", err);
      models = [];
      selectedModel = null;
      modelBtn.textContent = "No model ▾";
      showNoModelModal();
    }
  }

  // create conversation
  async function createConversation() {
    if (!selectedModel) throw new Error("No model selected");
    const payload = {
      llm_id: selectedModel.id || selectedModel.name,
      temperature: settings.temperature,
      top_p: settings.top_p,
      max_tokens: settings.max_tokens,
      custom_prompt: settings.custom_prompt || ""
    };
    const res = await fetch(`${API_BASE}/conversations/`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const txt = await res.text().catch(()=>null);
      throw new Error(`create conv failed (${res.status}) ${txt || ""}`);
    }
    const json = await res.json();
    return json.id || json.conversation_id || json.name || (json?.data?.id) || null;
  }

  // query conversation with streaming
  async function queryConversationStream(convId, question, opts = {}) {
    // abort controller for fetch + timeout
    if (currentStreamController) {
      // if a previous stream is active, abort it
      try { currentStreamController.abort(); } catch(e){}
      currentStreamController = null;
    }
    const controller = new AbortController();
    currentStreamController = controller;
    const timeout = setTimeout(() => {
      try { controller.abort(); } catch(e){}
    }, TIMEOUT_MS);

    // build payload compatible with your backend
    const payload = {
      question: question,
      custom_prompt: opts.custom_prompt ?? settings.custom_prompt,
      temperature: opts.temperature ?? settings.temperature,
      top_p: opts.top_p ?? settings.top_p,
      max_new_tokens: opts.max_new_tokens ?? settings.max_tokens,
      // omit n_last_turns_to_get for now (let backend default), but you could add e.g. 3
      // n_last_turns_to_get: opts.n_last_turns_to_get ?? undefined
    };

    const res = await fetch(`${API_BASE}/conversations/${convId}/query`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
      signal: controller.signal
    }).catch(err => {
      // normalize fetch abort vs other errors
      throw err;
    });

    if (!res.ok) {
      clearTimeout(timeout);
      const txt = await res.text().catch(()=>null);
      throw new Error(`query failed (${res.status}) ${txt || ""}`);
    }

    // STREAMING RESPONSE: read reader
    if (!res.body || !res.body.getReader) {
      // non-stream fallback
      const txt = await res.text();
      clearTimeout(timeout);
      currentStreamController = null;
      return { full: txt, streamed: false };
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let done = false;
    let accumulated = "";

    // Create LLM message element and display a cursor while streaming
    const el = appendLLMPlaceholder();
    // typing cursor char
    const CURSOR = "▌";

    try {
      while (true) {
        const { value, done: rdone } = await reader.read();
        if (rdone) break;
        if (value) {
          // decode chunk incrementally
          const chunk = decoder.decode(value, { stream: true });
          accumulated += chunk;
          // show text with cursor at end
          el.textContent = accumulated + CURSOR;
          scrollBottom();
        }
      }
      // finalize decode (flush)
      const remainder = decoder.decode(); // flush
      if (remainder) accumulated += remainder;
      // set final text (remove cursor)
      el.textContent = accumulated;
      scrollBottom();
      clearTimeout(timeout);
      currentStreamController = null;
      return { full: accumulated, streamed: true };
    } catch (err) {
      // abort or network error
      // append error text in message element
      if (err.name === "AbortError") {
        el.textContent = accumulated + "\n\n[STREAM ABORTED]";
      } else {
        el.textContent = accumulated + `\n\n[ERROR] ${String(err)}`;
      }
      clearTimeout(timeout);
      currentStreamController = null;
      throw err;
    } finally {
      // make sure we try to close reader
      try { reader.cancel(); } catch(e) {}
    }
  }

  // fallback mock stream (token-by-token)
  function appendMockStreaming(question) {
    const reply = `Mock reply: I received your question — "${question}".\n\n(Testing mode: this is a local mock response rendered by the extension UI.)`;
    const el = appendLLMPlaceholder();
    let i = 0;
    const speed = 12;
    const id = setInterval(() => {
      i++;
      el.textContent = reply.slice(0, i) + (i < reply.length ? "▌" : "");
      scrollBottom();
      if (i >= reply.length) {
        clearInterval(id);
        el.textContent = reply;
      }
    }, speed);
  }

  // main handler
  async function handleAsk(question) {
    if (!question || question.trim() === "") return;
    appendUser(question);
    inputText.value = "";
    inputText.blur();

    if (!selectedModel) {
      showNoModelModal();
      return;
    }

    try {
      if (!conversationId) {
        conversationId = await createConversation();
        if (!conversationId) throw new Error("No conversation id returned from backend");
      }

      // Try streaming query
      await queryConversationStream(conversationId, question);
      // success -> nothing else to do (stream appends tokens)
    } catch (err) {
      console.warn("Streaming/query failed, using mock. Error:", err);
      // fallback: mock
      appendMockStreaming(question);
    }
  }

  // events
  sendBtn.addEventListener("click", () => {
    const q = inputText.value;
    handleAsk(q);
  });
  inputText.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleAsk(inputText.value);
    }
  });

  // close
  closeBtn.addEventListener("click", () => {
    window.parent.postMessage({ type: "widget.close" }, "*");
  });

  // parent open focus
  window.addEventListener("message", (ev) => {
    if (!ev.data || typeof ev.data !== "object") return;
    if (ev.data.type === "widget.open") {
      inputText.focus();
    }
  }, false);

  // initialise
  (async function init() {
    try {
      await loadModels();
    } catch (e) {
      console.error("Init error:", e);
    }
    setTimeout(() => inputText.focus(), 500);
  })();

})();
