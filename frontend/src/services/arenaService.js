const API = "http://127.0.0.1:8000";

export async function askArena({
  question,
  llmId,
  temperature,
  topP,
  maxNewTokens,
  customPrompt,
  onStreamChunk,
}) {
  if (!question.trim()) throw new Error("Question is empty");

  const res = await fetch(`${API}/arena/${llmId}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question: question,
      temperature: temperature,
      top_p: topP,
      max_new_tokens: maxNewTokens,
      custom_prompt: customPrompt,
    }),
  });
  if (!res.ok) throw new Error("Arena query failed");

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let fullText = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value, { stream: true });
    fullText += chunk;
    onStreamChunk?.(chunk);
  }

  return fullText.trim();
}