import { getApiBaseUrl } from "../config/api.js";
export async function askArena({
  question,
  llmId,
  temperature,
  topP,
  maxNewTokens,
  quantize,
  customPrompt,
  onStreamChunk,
}) {
  if (!question.trim()) {
    throw new Error("Question is empty");
  }

  const res = await fetch(`${getApiBaseUrl()}/arena/${llmId}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question: question,
      temperature: temperature,
      top_p: topP,
      max_new_tokens: maxNewTokens,
      quantize: quantize,
      custom_prompt: customPrompt,
    }),
  });
  if (!res.ok) {
    throw new Error("Arena query failed");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let fullText = "";

  let streamDone = false;
  while (!streamDone) {
    const { done, value } = await reader.read();
    streamDone = done;
    if (done) {
      break;
    }
    const chunk = decoder.decode(value, { stream: true });
    fullText += chunk;
    onStreamChunk?.(chunk);
  }

  return fullText.trim();
}
