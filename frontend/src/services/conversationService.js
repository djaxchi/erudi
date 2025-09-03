const API = "http://127.0.0.1:8000";

export async function createConversation(llmId) {
  const res = await fetch(`${API}/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ llm_id: llmId }),
  });
  if (!res.ok) throw new Error("Conversation creation failed");
  return res.json();
}

export async function query(conversationId, question, {temperature = 0.2, topP = 0.9, maxTokens = 3074, customPrompt = "", onStreamChunk} = {}) {
  const body = {
    question,
    temperature : temperature,
    top_p: topP,
    max_new_tokens : maxTokens,
    custom_prompt : customPrompt
  }

  console.log(body);
  
  const res = await fetch(`${API}/conversations/${conversationId}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    let errJson;
    try{
      errJson = await res.json();
    }catch{}
    console.error("Query Error",res.status,errJson)
    
    // Store error message in database for conversation continuity
    try {
      await fetch(`${API}/conversations/${conversationId}/store_error_message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      console.log("Error message stored in database");
    } catch (storeError) {
      console.error("Failed to store error message:", storeError);
    }
    
    throw new Error("Query failed");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");

  let fullText = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value, { stream: true });
    fullText += chunk;
    if (onStreamChunk) onStreamChunk(chunk);
  }

  return {
    id: Date.now(),
    content: fullText.trim(),
    sender: "assistant",
  };
}

export async function generateTitle(conversationId, question, {onStreamChunk} = {}) {
  const body = {
    question
  }

  console.log("Generating title with body:", body);
  
  const res = await fetch(`${API}/conversations/${conversationId}/generate_title`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    let errJson;
    try{
      errJson = await res.json();
    }catch{}
    console.error("Title Generation Error",res.status,errJson)
    throw new Error("Title generation failed");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");

  let fullTitle = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value, { stream: true });
    fullTitle += chunk;
    if (onStreamChunk) onStreamChunk(chunk);
  }

  return {
    title: fullTitle.trim(),
  };
}

export async function ask({ question, conversationId = null, llmId = null, temperature, topP, maxTokens, customPrompt = "", onStreamChunk, onTitleChunk }) {
  if (!question.trim()) throw new Error("Question is empty");

  let convId = conversationId;
  let conversation;
  let isNewConversation = false;

  if (!convId) {
    if (!llmId) throw new Error("llmId is required to start a conversation");
    conversation = await createConversation(llmId);
    convId = conversation.id;
    isNewConversation = true;
  }

  if (!isNewConversation && conversationId) {
    try {
      const msgRes = await fetch(`${API}/conversations/${conversationId}/fetch_messages`);
      const messages = await msgRes.json();
      if (messages.length === 0) {
        isNewConversation = true;
      }
    } catch (err) {
      console.warn("Could not check message count, assuming not new conversation");
    }
  }
  const promises = [];

  if (isNewConversation && onTitleChunk) {
    const titlePromise = generateTitle(convId, question, { onStreamChunk: onTitleChunk })
      .catch(err => {
        console.error("Title generation failed:", err);
      });
    promises.push(titlePromise);
  }

  const responsePromise = query(convId, question, {temperature, topP, maxTokens, customPrompt, onStreamChunk});
  promises.push(responsePromise);

  const assistantMessage = await responsePromise;

  if (promises.length > 1) {
    Promise.all(promises).catch(err => {
      console.error("Some background operations failed:", err);
    });
  }

  return {
    conversation: conversation ?? { id: convId },
    assistantMessage,
  };
}

export async function deleteConversations(conversationIds) {
  if (conversationIds.length === 0) return;

  const res = await fetch(`${API}/conversations/delete_bulk`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ conversation_ids: conversationIds }),
  });
  if (!res.ok) throw new Error("Conversation deletion failed");
  return res.json();
}