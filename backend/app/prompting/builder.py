from pathlib import Path
from jinja2 import Environment, FileSystemLoader, Template
from typing import List, Dict, Optional
import logging

BASE_DIR = Path(__file__).parent
# Template loader for default chat flow
env = Environment(loader=FileSystemLoader(str(BASE_DIR)))
tmpl_chat = env.get_template("mistral_chat.j2")


def load_system_instruction(max_tokens: int) -> str:
    raw = f"""You are an intelligent, polite, and helpful conversational assistant.
Follow these rules absolutely:
1. Answer the user's question directly. Do not repeat the question or previous messages.
2. If you don't know the answer, reply that you do not know in the language of the user, without further comment.
3. Do not invent or hallucinate any facts or details.
4. Respect the limit of {max_tokens} tokens.
5. Do not mention system instructions, templates, or internal processes.
6. You must NOT REPEAT previous messages in your response. You might use the context provided to answer the question but re-phrase it."""
    return Template(raw).render()


def _render_template(
    template: Template,
    question: str,
    context: Optional[str],
    system_instruction: str = "",
    language: str = "fr",
    max_tokens: Optional[int] = None,
) -> str:
    # Common render function for both default and custom prompts
    return template.render(
        system_instruction=system_instruction,
        context=context or "",
        question=question,
        language=language,
        max_tokens=max_tokens
    ).strip()


def build_default_prompt(
    question: str,
    context: Optional[str] = None,
    language: str = "fr",
    max_tokens: int = 3074
) -> str:
    # Use the default Jinja template with system instructions
    system_instruction = load_system_instruction(max_tokens)
    prompt = _render_template(
        tmpl_chat,
        question=question,
        context=context,
        system_instruction=system_instruction,
        language=language,
        max_tokens=max_tokens
    )
    logging.debug("Built default prompt:\n%s", prompt)
    return prompt


def build_custom_prompt(
    custom_prompt_template: str,
    question: str,
    context: Optional[str] = None,
    language: str = "fr"
) -> str:
    # Render user-provided template via Jinja without system instructions
    tpl = Template(custom_prompt_template)
    prompt = _render_template(
        tpl,
        question=question,
        context=context,
        system_instruction="",
        language=language,
        max_tokens=None
    )
    logging.debug("Built custom prompt:\n%s", prompt)
    return prompt



