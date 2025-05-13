# backend/app/prompting/builder.py
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, Template
from typing import List, Dict, Optional
import logging


BASE_DIR = Path(__file__).parent
env = Environment(loader=FileSystemLoader(str(BASE_DIR)))
tmpl_chat = env.get_template("mistral_chat.j2")


def load_system_instruction(max_tokens: int) -> str:
    raw = (BASE_DIR / "prompt.txt").read_text(encoding="utf-8")
    return Template(raw).render(max_tokens=max_tokens)


def build_prompt(
    question: str,
    history: Optional[List[Dict[str, str]]] = None,
    context: Optional[str] = None,
    language: str = "fr",
    max_tokens: int = 10000
) -> str:
   
    system_instruction = load_system_instruction(max_tokens)
    h = history or []  # garde la liste, jamais de chaîne
    ctx = context or None


    prompt = tmpl_chat.render(
        system_instruction=system_instruction,
        context=ctx,
        history=h,
        question=question,
        language=language
    )
    logging.debug(f"Built prompt:\n{prompt}")
    return prompt.strip()





