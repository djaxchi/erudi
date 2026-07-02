/**
 * Turn a stored message's raw content into the readable text shown in the chat.
 *
 * Stored user messages can carry internal attachment markers — [image] for
 * this-session attachments, [image_path:<path>] for persisted ones — that the
 * UI renders as thumbnails or placeholders, never as text. Error messages
 * carry the [ERROR_MESSAGE_SYSTEM] sentinel displayed as a ❌ prefix.
 *
 * Single source of truth used by BOTH the chat display and the
 * copy-to-clipboard action, so copying yields exactly what the user sees
 * (#136).
 *
 * @param {string} content - Raw message content as stored/streamed.
 * @returns {string} The human-readable text, markers removed.
 */
export function getDisplayContent(content) {
  if (content.includes("[ERROR_MESSAGE_SYSTEM]")) {
    return content.replace("[ERROR_MESSAGE_SYSTEM] ", "❌ ");
  }
  return content
    .replace(/\[image\]/g, "")
    .replace(/\[image_path:[^\]]*\]/g, "")
    .trim();
}
