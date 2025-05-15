from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TextIteratorStreamer,
    StoppingCriteria,
    StoppingCriteriaList,
)
import torch, re, threading
from ..database import get_db
from ..models.Llm import Llm
from ..prompting.builder import build_default_prompt, build_custom_prompt

router = APIRouter(prefix="/arena", tags=["arena"])

class StopOnEndToken(StoppingCriteria):
    def __init__(self, end_token_id: int):
        self.end_token_id = end_token_id
    def __call__(self, input_ids, scores, **kwargs):
        return input_ids[0, -1].item() == self.end_token_id

# Globals to cache model/tokenizer
_loaded_model = None
_current_tokenizer = None
_loaded_model_id = None

@router.post("/{llm_id}/query")
async def query_arena(
    llm_id: int,
    payload: dict,
    db: Session = Depends(get_db)
):
    """
    Stateless arena query:
    - llm_id: ID du modèle
    - payload: { question, temperature?, topP?, maxNewTokens?, customPrompt? }
    """
    question = payload.get("question")
    if not question:
        raise HTTPException(status_code=400, detail="Missing 'question'")
    llm = db.query(Llm).filter(Llm.id == llm_id).first()
    if not llm:
        raise HTTPException(status_code=404, detail="LLM not found")

    global _loaded_model, _current_tokenizer, _loaded_model_id
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if _loaded_model_id != llm_id or _loaded_model is None:
        _loaded_model = AutoModelForCausalLM.from_pretrained(
            llm.link, local_files_only=True, torch_dtype=torch.float16
        )
        _current_tokenizer = AutoTokenizer.from_pretrained(
            llm.link, local_files_only=True
        )
        _loaded_model.to(device).eval()
        _loaded_model_id = llm_id

    # Construit un prompt minimal (pas d'historique)
    prompt = f"{payload.get('customPrompt','')}\n{question}".strip()

    prompt_text = build_default_prompt(
            question=question,
            history=None,
            context=None,
            language="fr",
            max_tokens=payload.get("maxNewTokens")
        )

    if payload.get("customPrompt"):
        prompt_text_customized = build_custom_prompt(
            payload["customPrompt"],
            question,
            None,
            None,
            "fr"
        )
        prompt_text = ( prompt_text + "\n Instructions Utilisateur Personnalisées : " + prompt_text_customized )


    input_ids = _current_tokenizer.encode(prompt_text, return_tensors="pt").to(device)

    # Prépare le stopping
    end_ids = _current_tokenizer.encode("<|end|>", add_special_tokens=False)
    stop_crit = StoppingCriteriaList([StopOnEndToken(end_ids[-1])])

    streamer = TextIteratorStreamer(
        _current_tokenizer, skip_prompt=True, skip_special_tokens=True
    )

    max_new_tokens = payload.get("maxNewTokens",1000)
    temperature = payload.get("temperature", 0.5 )
    top_p = payload.get("toP, 0.9")

    def run_generation():
        with torch.no_grad():
            _loaded_model.generate(
                input_ids=input_ids,
                streamer=streamer,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                do_sample=True,
                pad_token_id=_current_tokenizer.eos_token_id,
                stopping_criteria=stop_crit,
            )
    threading.Thread(target=run_generation).start()

    async def event_stream():
        pattern = re.compile(r"<\|/?(?:assistant|system|user|end)\|>")
        for token in streamer:
            yield pattern.sub("", token)

    return StreamingResponse(event_stream(), media_type="text/plain")