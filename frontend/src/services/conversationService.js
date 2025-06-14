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

export async function query(conversationId, question, {temperature = 0.5, topP = 0.9, maxTokens = 3074, customPrompt = "", onStreamChunk} = {}) {
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
    if (onStreamChunk) onStreamChunk(chunk); // send partial result to the caller
  }

  return {
    id: Date.now(),
    content: fullText.trim(),
    sender: "assistant",
  };
}

export async function ask({ question, conversationId = null, llmId = null, temperature, topP, maxTokens, customPrompt = "", onStreamChunk }) {
  if (!question.trim()) throw new Error("Question is empty");

  let convId = conversationId;
  let conversation;

  if (!convId) {
    if (!llmId) throw new Error("llmId is required to start a conversation");
    conversation = await createConversation(llmId);
    convId = conversation.id;
  }

  const assistantMessage = await query(convId, question, {temperature, topP, maxTokens, customPrompt, onStreamChunk});

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