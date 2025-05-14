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

export async function addMessage(conversationId, content, sender = "user") {
  const res = await fetch(`${API}/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, sender }),
  });
  if (!res.ok) throw new Error("Message creation failed");
  return res.json();
}

export async function query(conversationId, question, onChunk) {
  const res = await fetch(`${API}/conversations/${conversationId}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });

  if (!res.ok) throw new Error("Query failed");

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");

  let fullText = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value, { stream: true });
    fullText += chunk;
    if (onChunk) onChunk(chunk); // send partial result to the caller
  }

  return {
    id: Date.now(),
    content: fullText.trim(),
    sender: "assistant",
  };
}

export async function ask({ question, conversationId = null, llmId = null, onStreamChunk }) {
  if (!question.trim()) throw new Error("Question is empty");

  let convId = conversationId;
  let conversation;

  if (!convId) {
    if (!llmId) throw new Error("llmId is required to start a conversation");
    conversation = await createConversation(llmId);
    convId = conversation.id;
  }

  const userMessage = await addMessage(convId, question);
  
  const assistantMessage = await query(convId, question, onStreamChunk);

  return {
    conversation: conversation ?? { id: convId },
    userMessage,
    assistantMessage,
  };
}
