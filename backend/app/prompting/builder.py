from pathlib import Path
from jinja2 import Environment, FileSystemLoader, Template
from typing import List, Dict, Optional
import logging

BASE_DIR = Path(__file__).parent
# Template loader for default chat flow
env = Environment(loader=FileSystemLoader(str(BASE_DIR)))
tmpl_chat = env.get_template("mistral_chat.j2")


def load_system_instruction(max_tokens: int) -> str:
    raw = (BASE_DIR / "prompt.txt").read_text(encoding="utf-8")
    # Render any {{ max_tokens }} placeholder
    return Template(raw).render(max_tokens=max_tokens)


def _render_template(
    template: Template,
    question: str,
    history: Optional[List[str]],
    context: Optional[str],
    system_instruction: str = "",
    language: str = "fr",
    max_tokens: Optional[int] = None,
) -> str:
    # Common render function for both default and custom prompts
    return template.render(
        system_instruction=system_instruction,
        context=context or "",
        history=history or [],
        question=question,
        language=language,
        max_tokens=max_tokens
    ).strip()


def build_default_prompt(
    question: str,
    history: Optional[List[str]] = None,
    context: Optional[str] = None,
    language: str = "fr",
    max_tokens: int = 10000
) -> str:
    # Use the default Jinja template with system instructions
    system_instruction = load_system_instruction(max_tokens)
    prompt = _render_template(
        tmpl_chat,
        question=question,
        history=history,
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
    history: Optional[List[str]] = None,
    context: Optional[str] = None,
    language: str = "fr"
) -> str:
    # Render user-provided template via Jinja without system instructions
    tpl = Template(custom_prompt_template)
    prompt = _render_template(
        tpl,
        question=question,
        history=history,
        context=context,
        system_instruction="",
        language=language,
        max_tokens=None
    )
    logging.debug("Built custom prompt:\n%s", prompt)
    return prompt



