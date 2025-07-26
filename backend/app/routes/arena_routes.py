import logging
from ..schemas.arena_schemas import ArenaQueryPayload
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
from ..prompting.builder import build_conv_prompt

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
    payload: ArenaQueryPayload,
    db: Session = Depends(get_db)
):
    """
    Stateless arena query:
    - llm_id: ID du modèle
    - payload: { question, temperature?, topP?, maxNewTokens?, customPrompt? }
    """
    question = payload.question
    temperature = payload.temperature or 0.9
    top_p = payload.top_p or 0.9
    max_new_tokens = payload.max_new_tokens or 200
    custom_prompt = payload.custom_prompt or ""

    if not question:
        raise HTTPException(status_code=400, detail="Missing 'question'")
    logging.info(f"Querying LLM from DB")
    llm = db.query(Llm).filter(Llm.id == llm_id).first()
    logging.info(f"Querying LLM from DB ------------ Finished")
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

    prompt_text = build_conv_prompt(
            question=question,
            max_tokens=max_new_tokens, 
            custom_sys_prompt=custom_prompt
        )

    


    input_ids = _current_tokenizer.encode(prompt_text, return_tensors="pt").to(device)

    # Prépare le stopping
    end_ids = _current_tokenizer.encode("<|end|>", add_special_tokens=False)
    stop_crit = StoppingCriteriaList([StopOnEndToken(end_ids[-1])])

    streamer = TextIteratorStreamer(
        _current_tokenizer, skip_prompt=True, skip_special_tokens=True
    )


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