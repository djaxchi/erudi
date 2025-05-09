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

export async function ask({ question, conversationId = null, llmId = null }) {
    if (!question.trim()) throw new Error("Question is empty");
  
    let convId = conversationId;
    let conversation;
  
    if (!convId) {
      if (!llmId) throw new Error("llmId is required to start a conversation");
      conversation = await createConversation(llmId);
      convId = conversation.id;
    }
  
    const message = await addMessage(convId, question);
  
    return { conversation: conversation ?? { id: convId }, message };
  }