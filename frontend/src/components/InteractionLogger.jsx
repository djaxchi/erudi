import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { createLogger } from "../utils/logger";
import { buildInteractionEntry, truncateValue } from "../utils/interactionLogger";

const uiLog = createLogger("UI");

const TEXT_INPUT_TYPES = new Set(["text", "search", "email", "url", "tel", "number", "password"]);
const CHANGE_INPUT_TYPES = new Set(["range", "checkbox", "radio", "file"]);
const VALUE_MAX_CHARS = 200;

const tagOf = (el) => (el && el.tagName ? el.tagName.toLowerCase() : "");

function isTextEntry(el) {
  const tag = tagOf(el);
  if (tag === "textarea") return true;
  return tag === "input" && TEXT_INPUT_TYPES.has((el.type || "text").toLowerCase());
}

/**
 * Invisible, mounted-once interaction tracer. Attaches plain capture-phase
 * document listeners (capture runs before any component stopPropagation) and
 * emits one "ui.<dom-event-type>" entry per interaction through the renderer
 * log bridge. Holds no React state, so it never triggers re-renders of the
 * app; text inputs are logged once on blur (focusout), never per keystroke.
 */
export default function InteractionLogger() {
  const location = useLocation();
  // The listeners read the current route through a ref so they attach exactly
  // once and never need re-binding on navigation.
  const routeRef = useRef(location.pathname);

  useEffect(() => {
    routeRef.current = location.pathname;
  }, [location.pathname]);

  useEffect(() => {
    const emit = (type, el, extra) => {
      uiLog.info(`ui.${type}`, buildInteractionEntry(type, el, routeRef.current, extra));
    };
    // The tracer must never break the app — swallow everything.
    const safe = (fn) => (event) => {
      try {
        fn(event);
      } catch {
        /* never throw from the tracer */
      }
    };

    const onClick = safe((e) => emit("click", e.target));

    // Text inputs log once, on blur, with the final value — never per keystroke.
    const onFocusOut = safe((e) => {
      if (!isTextEntry(e.target)) return;
      emit("focusout", e.target, { value: truncateValue(e.target.value ?? "", VALUE_MAX_CHARS) });
    });

    // Committed values only: selects, sliders, checkboxes/radios, file pickers.
    const onChange = safe((e) => {
      const el = e.target;
      const tag = tagOf(el);
      if (tag === "select") {
        emit("change", el, { value: truncateValue(String(el.value ?? ""), VALUE_MAX_CHARS) });
        return;
      }
      if (tag !== "input") return;
      const type = (el.type || "").toLowerCase();
      if (!CHANGE_INPUT_TYPES.has(type)) return;
      if (type === "file") {
        const files = Array.from(el.files || []).map((f) => f.name);
        emit("change", el, { input_type: type, files, file_count: files.length });
      } else if (type === "checkbox" || type === "radio") {
        emit("change", el, {
          input_type: type,
          value: String(el.value ?? ""),
          checked: !!el.checked,
        });
      } else {
        emit("change", el, { input_type: type, value: String(el.value ?? "") });
      }
    });

    const onDrop = safe((e) => {
      const files = Array.from(e.dataTransfer?.files || []).map((f) => f.name);
      emit("drop", e.target, { files, file_count: files.length });
    });

    // Paste logs shape only (text length / image presence), not the payload.
    const onPaste = safe((e) => {
      const clipboard = e.clipboardData;
      const text = clipboard?.getData?.("text") ?? "";
      const hasImage = Array.from(clipboard?.items || []).some((item) =>
        (item.type || "").startsWith("image/")
      );
      emit("paste", e.target, { text_length: text.length, has_image: hasImage });
    });

    // Commit/cancel keys only — plain typing is intentionally not traced.
    const onKeyDown = safe((e) => {
      if (e.key !== "Enter" && e.key !== "Escape") return;
      emit("keydown", e.target, { key: e.key });
    });

    const listeners = [
      ["click", onClick],
      ["focusout", onFocusOut],
      ["change", onChange],
      ["drop", onDrop],
      ["paste", onPaste],
      ["keydown", onKeyDown],
    ];
    for (const [type, handler] of listeners) {
      document.addEventListener(type, handler, true);
    }
    return () => {
      for (const [type, handler] of listeners) {
        document.removeEventListener(type, handler, true);
      }
    };
  }, []);

  return null;
}
