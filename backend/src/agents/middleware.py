"""Per-turn request-time agent middleware (KB merge, image/tool-result hygiene).

Factored out of ``runner.py`` so the runner module itself stays free of
module-level LangChain imports: this module subclasses ``AgentMiddleware`` at
class-definition time, so it is imported LAZILY (inside the runner's methods)
and the whole LangChain agent stack only loads on the first turn, not at boot
(issue #160).
"""

from __future__ import annotations

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage


def _split_multimodal(content):
    """Split message content into (joined_text, image_parts).

    For plain-string content, returns (content, []). For OpenAI multimodal
    content (a list of ``{"type": "text"|"image_url", ...}`` parts), returns
    the joined text of the text parts and the list of image parts.
    """
    if isinstance(content, str):
        return content, []
    text = " ".join(
        p["text"]
        for p in content
        if isinstance(p, dict) and p.get("type") == "text" and p.get("text")
    )
    images = [p for p in content if isinstance(p, dict) and p.get("type") == "image_url"]
    return text, images


def _flatten_without_images(content) -> str:
    """Plain-text rendering of multimodal content; each image -> ``[image]``."""
    if isinstance(content, str):
        return content
    out = []
    for p in content:
        if isinstance(p, dict):
            if p.get("type") == "text" and p.get("text"):
                out.append(p["text"])
            elif p.get("type") == "image_url":
                out.append("[image]")
    return " ".join(out).strip()


class _KbContextMiddleware(AgentMiddleware):
    """Merge the per-turn KB block into the model request's LAST user message.

    Request-time only (``request.override``): the checkpointer keeps the
    clean question, so past turns never re-expose stale excerpts (no
    context pollution, no parroting fuel). Rationale: on small local
    models, grounding/language instructions dissolve with turn depth when
    they live in the system prompt (chat templates prepend it before the
    whole history) — the tail of the last user message is the one spot
    that always stays inside the effective window.

    Layout: excerpts+rules block, then the question, then the answer-
    language request LAST in the user's voice — pre-question language
    lines are ignored as block metadata (run-4 eval), in-question
    requests are honored (T5).
    """

    def __init__(self, context_block: str, language_line: str):
        super().__init__()
        self.context_block = context_block
        self.language_line = language_line

    def _merge(self, request):
        messages = list(request.messages)
        last = messages[-1]
        # No "Question:" label: any English structural string near the
        # question feeds the English attractor (run-5 eval finding).
        question_text, image_parts = _split_multimodal(last.content)
        merged_text = f"{self.context_block}\n\n{question_text}\n\n{self.language_line}"
        if image_parts:
            # Multimodal turn: merge the KB block into the text part and keep
            # the screenshot(s) attached for the VLM.
            merged = HumanMessage(
                content=[{"type": "text", "text": merged_text}, *image_parts]
            )
        else:
            merged = HumanMessage(content=merged_text)
        return request.override(messages=[*messages[:-1], merged])

    def wrap_model_call(self, request, handler):
        return handler(self._merge(request))

    async def awrap_model_call(self, request, handler):
        return await handler(self._merge(request))


class _StripStaleImagesMiddleware(AgentMiddleware):
    """Keep only the CURRENT turn's images in the model request.

    The checkpointer stores each turn's multimodal ``HumanMessage``, so without
    this every past screenshot would be re-sent on each follow-up and blow the
    (small, local) VLM context. Vision is therefore single-turn: an image is
    seen only on the turn it is sent; in later turns it collapses to an
    ``[image]`` text marker. The current turn — the last human message, even
    across tool-call loops where a ToolMessage is last — keeps its images.
    """

    def _strip(self, request):
        messages = list(request.messages)
        human_idxs = [i for i, m in enumerate(messages) if m.type == "human"]
        if not human_idxs:
            return request
        keep = human_idxs[-1]
        changed = False
        for i, m in enumerate(messages):
            if i == keep or not isinstance(m.content, list):
                continue
            messages[i] = m.model_copy(
                update={"content": _flatten_without_images(m.content)}
            )
            changed = True
        return request.override(messages=messages) if changed else request

    def wrap_model_call(self, request, handler):
        return handler(self._strip(request))

    async def awrap_model_call(self, request, handler):
        return await handler(self._strip(request))


class _StripImagesForTextModel(AgentMiddleware):
    """Flatten ALL image content when the model is not known to see images (#133).

    A text-only model (no MLX ``vision_config`` / no llama.cpp ``mmproj``) would
    either crash or silently ignore image parts, so every ``image_url`` part —
    the current turn included — collapses to an ``[image]`` text marker before
    the request reaches the model server. The answer stays clean text instead of
    broken inference. The caller adds this whenever ``supports_vision is not
    True`` (#212): unknown capability (None) strips too — the services prepend a
    user-facing notice — and only a positively-detected vision model keeps its
    images.
    """

    def _strip(self, request):
        messages = list(request.messages)
        changed = False
        for i, m in enumerate(messages):
            if isinstance(m.content, list):
                messages[i] = m.model_copy(
                    update={"content": _flatten_without_images(m.content)}
                )
                changed = True
        return request.override(messages=messages) if changed else request

    def wrap_model_call(self, request, handler):
        return handler(self._strip(request))

    async def awrap_model_call(self, request, handler):
        return await handler(self._strip(request))


class _StripStaleKbToolMessages(AgentMiddleware):
    """Placeholder the ``search_knowledge_base`` results of PAST turns.

    The checkpointer persists every KB ToolMessage, so without this each
    follow-up would re-send every past turn's (bulky) excerpts and re-introduce
    the multi-turn context pollution the request-time design of issue #81 had
    eliminated. The CURRENT turn's KB result stays intact (the model just
    fetched it and must read it); only past ones shrink to a short marker. We
    rewrite content only, never dropping the message, so the
    ``AIMessage(tool_calls) -> ToolMessage`` pairing the chat template requires
    stays valid. The checkpointer keeps the full result, so the UI is
    unaffected — symmetric to ``_StripStaleImagesMiddleware`` for images.
    """

    _MARKER = "[knowledge base results from an earlier turn omitted]"

    def _strip(self, request):
        messages = list(request.messages)
        human_idxs = [i for i, m in enumerate(messages) if m.type == "human"]
        if not human_idxs:
            return request
        keep = human_idxs[-1]  # last human marks the current turn; earlier = past
        changed = False
        for i, m in enumerate(messages):
            if i >= keep:
                continue
            if m.type == "tool" and getattr(m, "name", None) == "search_knowledge_base":
                messages[i] = m.model_copy(update={"content": self._MARKER})
                changed = True
        return request.override(messages=messages) if changed else request

    def wrap_model_call(self, request, handler):
        return handler(self._strip(request))

    async def awrap_model_call(self, request, handler):
        return await handler(self._strip(request))
