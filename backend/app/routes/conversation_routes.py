from ..schemas.message_schemas import MessageCreate, MessageResponse
from fastapi import APIRouter, Depends, HTTPException, Body, status
from sqlalchemy.orm import Session
import torch
from datetime import datetime
from transformers import AutoTokenizer, AutoModelForCausalLM, TextIteratorStreamer, pipeline, StoppingCriteria, StoppingCriteriaList, AutoModelForSeq2SeqLM, BitsAndBytesConfig
import logging
from typing import List
from ..database import get_db
from ..models.Conversation import Conversation
from ..models.Llm import Llm
from ..models.Message import Message
from ..schemas.conversation_schemas import ConversationCreate, ConversationDeleteBulk, ConversationQuery, ConversationQueryResponse, ConversationResponse, ConversationUpdate, ConversationWithMessagesResponse
import threading
from fastapi.responses import StreamingResponse
from faiss import IndexFlatL2
from sentence_transformers import SentenceTransformer
import numpy as np
from ..prompting.builder import build_conv_prompt
import re
import os
from dotenv import load_dotenv
load_dotenv()
CACHE_DIR = os.getenv("CACHE_DIR")

loaded_model = None
current_tokenizer  = None
loaded_model_id = None
embedder = None
device = "cuda" if torch.cuda.is_available() else "cpu"

conversation_summary_cache = {}

# The quantization configuration for the model
# It is here for the moment, but it will soon be dynamically adapted based on the model and hardware
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_use_double_quant=True,
)
flash_attn_impl = False

router = APIRouter()

class StopOnEndToken(StoppingCriteria):
    def __init__(self, end_token_id: int):
        super().__init__()
        self.end_token_id = end_token_id
    def __call__(self, input_ids, scores, **kwargs):
        return input_ids[0, -1].item() == self.end_token_id


@router.get("/conversations/{conversation_id}/fetch_messages", response_model=List[MessageResponse])
async def get_messages_by_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """
    Fetch all messages for a specific conversation.
    """
    messages = db.query(Message).filter(Message.conversation_id == conversation_id).all()
    return messages



@router.delete("/messages/{message_id}")
async def delete_message(message_id: int, db: Session = Depends(get_db)):
    """
    Delete a specific message by its ID.
    """
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    db.delete(message)
    db.commit()
    return {"message": "Message deleted successfully"}


@router.get("/conversations", response_model=List[ConversationResponse])
async def get_all_conversations(db: Session = Depends(get_db)):
    """
    Fetch all conversations.
    """
    try:
        conversations = db.query(Conversation).all()
        return conversations
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@router.get("/conversations/{conversation_id}", response_model=ConversationWithMessagesResponse)
async def get_conversation_by_id(conversation_id: int, db: Session = Depends(get_db)):
    """
    Fetch a single conversation by its ID, including messages.
    """
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation

@router.post("/conversations", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
):
    """Create a new conversation for a specific LLM (body JSON)."""

    conversation = Conversation(llm_id=payload.llm_id, name="New Conversation")
    try:
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not create conversation: {str(e)}",
        )
    return conversation

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """
    Delete a conversation by its ID.
    """
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    global conversation_summary_cache
    if conversation_id in conversation_summary_cache:
        del conversation_summary_cache[conversation_id]
        logging.info(f"Cleared summary cache for deleted conversation {conversation_id}")
    
    db.delete(conversation)
    db.commit()
    return {"message": "Conversation deleted successfully"}

@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: int,
    payload: ConversationUpdate,
    db: Session = Depends(get_db),
):
    """Update conversation fields (name and llm_id)."""

    conversation = (
        db.query(Conversation).filter(Conversation.id == conversation_id).first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    updated = False

    if payload.name is not None and payload.name != conversation.name:
        conversation.name = payload.name
        updated = True

    if payload.llm_id is not None and payload.llm_id != conversation.llm_id:
        conversation.llm_id = payload.llm_id
        updated = True

    if updated:
        try:
            db.commit()
            db.refresh(conversation)
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Could not update conversation: {str(e)}",
            )

    return conversation

def get_conversation_history(db: Session, conversation_id: int):
    try:
        messages = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.timestamp.asc()).all()
        messages_to_be_returned = []

        if len(messages) == 0:
            return messages_to_be_returned
        
        for msg in messages:
            messages_to_be_returned.append((msg.sender ,msg.content))
        
        return messages_to_be_returned
    except Exception as e:
        logging.exception(f"Error retrieving conversation history: {e}")
        return []

def retrieve_context(query: str, conversation_history, conversation_id: int, top_k=3, n_last_turns=2, model_type="mistral"):
    """
    Retrieve relevant context from the conversation history based on semantic similarity and recency.
    Uses SentenceTransformer for embeddings and FAISS for similarity search.
    Args:
        query (str): The user's query.
        conversation_history (list): List of (sender, message) tuples.
        conversation_id (int): The ID of the conversation for caching purposes.
        top_k (int): Number of semantically relevant turns to retrieve.
        n_last_turns (int): Number of last turns to include.
        model_type (str): The type of model to use for prompt engineering.
    Returns:
        str: Formatted context string.
    """
    def get_embedder():
        global embedder
        if embedder is None:
            logging.info("Loading the Embedder")
            os.makedirs(CACHE_DIR, exist_ok=True)
            embedder = SentenceTransformer(
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                cache_folder=CACHE_DIR
            )
            logging.info("Embedder loaded")
        return embedder

    def get_cached_summary(conversation_id: int, current_message_count: int):
        """Get cached summary or determine if regeneration is needed."""
        global conversation_summary_cache
        
        if conversation_id not in conversation_summary_cache:
            return None, True
        
        cache_entry = conversation_summary_cache[conversation_id]
        cached_count = cache_entry["message_count"]
        
        if current_message_count >= cached_count * 2:
            logging.info(f"Summary cache expired for conversation {conversation_id}: {cached_count} -> {current_message_count} messages")
            return None, True
        
        logging.info(f"Using cached summary for conversation {conversation_id}: {cached_count} messages")
        return cache_entry["summary"], False

    def cache_summary(conversation_id: int, summary: str, message_count: int):
        """Cache the generated summary."""
        global conversation_summary_cache
        conversation_summary_cache[conversation_id] = {
            "summary": summary,
            "message_count": message_count,
            "generated_at": datetime.now()
        }
        logging.info(f"Cached summary for conversation {conversation_id} with {message_count} messages")

    def generate_conversation_summary(history, model_type="mistral"):
        """
        Generate a quick summary of the conversation history.
        Args:
            history (list): List of (sender, message) tuples.
            model_type (str): The type of model to use for summarization.
        Returns:
            str: The generated summary.
        """
        if not loaded_model or not current_tokenizer or len(history) < 10:
            return ""
        
        conv_text = ""
        for sender, msg in history:
            role = "User" if sender == "user" else "Assistant"
            conv_text += f"{role}: {msg}\n"
        
        if len(conv_text) > 4000:
            conv_text = conv_text[:4000] + "..."
        
        mistral_summary_prompt = f"""<|system|>You are a conversation summarizer. Create a concise summary of the key topics, decisions, and important information discussed in this conversation. Keep it under 100 words.<|end|>

<|user|>Summarize this conversation:

{conv_text}

Summary:<|end|>
<|assistant|>"""
        
        gemma_summary_prompt = f"""<start_of_turn>user
You are a conversation summarizer. Create a concise summary of the key topics, decisions, and important information discussed in this conversation. Keep it under 100 words.

Summarize this conversation:

{conv_text}

Summary:<end_of_turn>
<start_of_turn>model
"""
        try:
            if model_type == "mistral":
                input_ids = current_tokenizer.encode(mistral_summary_prompt, return_tensors="pt").to(device)
                end_ids = current_tokenizer.encode("<|end|>", add_special_tokens=False)
            elif model_type == "gemma":
                input_ids = current_tokenizer.encode(gemma_summary_prompt, return_tensors="pt").to(device)
                end_ids = current_tokenizer.encode("<end_of_turn>", add_special_tokens=False)
            stop_crit = StoppingCriteriaList([StopOnEndToken(end_ids[-1])])
            
            with torch.no_grad():
                output = loaded_model.generate(
                    input_ids,
                    max_new_tokens=150,
                    temperature=0.3,
                    top_p=0.8,
                    do_sample=True,
                    num_beams=1,
                    pad_token_id=current_tokenizer.eos_token_id,
                    stopping_criteria=stop_crit
                )
            
            full_response = current_tokenizer.decode(output[0], skip_special_tokens=True)
            summary = full_response.split("<|assistant|>")[-1].strip()
            summary = re.sub(r"<\|/?(?:assistant|system|user|end)\|>", "", summary).strip()
            
            return summary
            
        except Exception as e:
            logging.exception(f"Summary generation failed: {e}")
            return ""

    history = conversation_history[:-1]
    if not history or len(history) < 2:
        return ""

    context_lines = []
    current_message_count = len(conversation_history)

    # Conv summary context
    summary_threshold = n_last_turns * 2 * 5 
    if len(history) > summary_threshold and loaded_model and current_tokenizer:
        cached_summary, need_regenerate = get_cached_summary(conversation_id, current_message_count)
        
        if need_regenerate:
            logging.info(f"Generating new conversation summary for {len(history)} messages")
            summary = generate_conversation_summary(history, model_type=model_type)
            if summary:
                cache_summary(conversation_id, summary, current_message_count)
        else:
            summary = cached_summary
        
        if summary:
            context_lines.append("  - Conversation Summary:\n")
            context_lines.append(f"{summary}")
            context_lines.append("")

    n_recent = n_last_turns * 2
    if len(history) > n_recent + 5:
        semantic_history = history[:-n_recent]
    else:
        semantic_history = []

    # Semantic context
    if len(semantic_history) >= top_k * 2:
        get_embedder()
        query_emb = embedder.encode(query, convert_to_tensor=True)
        messages = [msg[1] for msg in semantic_history]
        msg_embs = embedder.encode(messages, convert_to_tensor=False)
        index = IndexFlatL2(len(msg_embs[0]))
        index.add(np.array(msg_embs))
        _, idxs = index.search(np.array([query_emb.cpu().numpy()]), k=min(top_k, len(semantic_history)))

        used = set()
        semantic_lines = []
        for idx in idxs[0]:
            sender, msg = semantic_history[idx]
            if msg in used:
                continue
            used.add(msg)
            if sender == "user" and idx + 1 < len(semantic_history):
                next_sender, next_msg = semantic_history[idx + 1]
                if next_msg not in used:
                    semantic_lines.append(f"[user]: {msg}")
                    used.add(next_msg)
                    semantic_lines.append(f"[assistant]: {next_msg}")
            elif sender != "user" and idx > 0:
                prev_sender, prev_msg = semantic_history[idx - 1]
                if prev_msg not in used:
                    semantic_lines.append(f"[user]: {prev_msg}")
                    used.add(prev_msg)
                    semantic_lines.append(f"[assistant]: {msg}")
        if semantic_lines:
            context_lines.append(f"  - Here are the {len(semantic_lines)//2} most relevant previous message exchanges:")
            context_lines.extend(semantic_lines)
            context_lines.append("")

    # Recency context
    recent = history[-n_recent:] if len(history) >= n_recent else history
    if recent:
        context_lines.append(f"  - Here are the {len(recent)} most recent messages:")
        for sender, msg in recent:
            role = "[user]" if sender == "user" else "[assistant]"
            context_lines.append(f"{role}: {msg}")

    if not context_lines:
        return ""
    return "Here is context about the conversation you had so far:\n\n" + "\n".join(context_lines)


@router.post("/conversations/{conversation_id}/generate_title")
async def generate_title(
    conversation_id: int,
    payload: ConversationQuery,
    db: Session = Depends(get_db),
):
    """Generate a title for the conversation based on the first message."""


    logging.info("Generating title for conversation %s", conversation_id)
    
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    llm = db.query(Llm).filter(Llm.id == conversation.llm_id).first()
    if not llm:
        raise HTTPException(status_code=404, detail="LLM not found")
    model_type = llm.type
    global loaded_model, current_tokenizer, loaded_model_id

    try:
        if loaded_model_id != llm.id or loaded_model is None:
            start = datetime.now()
            logging.info(f"Loading model {llm.id} from {llm.link}")
            loaded_model = AutoModelForCausalLM.from_pretrained(
                llm.link,
                local_files_only=True,
                torch_dtype=torch.float16,
                quantization_config=bnb_config if model_type == "mistral" else None,
                attn_implementation="flash_attention_2" if float(torch.version.cuda) >= 11.8 and flash_attn_impl else "sdpa",
                low_cpu_mem_usage=True if model_type == "mistral" else False,
            )
            current_tokenizer = AutoTokenizer.from_pretrained(llm.link, local_files_only=True)
            loaded_model_id = llm.id
            loaded_model.eval()
            loaded_model.to(device)
            logging.info(f"Model {llm.id} loaded in {datetime.now() - start} seconds")
        else:
            logging.info(f"Model {llm.id} already loaded")
            loaded_model.eval()
            loaded_model.to(device)
    except Exception as e:
        logging.exception("Failed to load model or tokenizer")
        raise HTTPException(status_code=500, detail=f"Model loading error: {str(e)}")

    try:
        mistral_title_generation_prompt = f"""<|system|>You are a title generator. You must create VERY SHORT titles. No more than 5 words. Use only essential keywords. No articles (a, an, the). No punctuation.<|end|>

<|user|>Create a 2-to-5-word title for: {payload.question}

Examples:
- How to cook pasta? → Pasta Cooking Guide
- What is machine learning? → Machine Learning Basics
- Help me with Python code → Python Code Help

Your very short title:<|end|>
<|assistant|>"""
        
        gemma_title_generation_prompt = f"""<start_of_turn>user
You are a title generator. You must create VERY SHORT titles. No more than 5 words. Use only essential keywords. No articles (a, an, the). No punctuation. Do NOT add any extra text, polite statements, or whatsoever. ONLY return the title.

Examples you need to follow:
- user: How to cook pasta? model: Pasta Cooking Guide
- user: What is machine learning? model: Machine Learning Basics
- user: Help me with Python code model: Python Code Help
- user: Hey what's up ? model: Chill Conversation
- user: Can you help me with my homework?? I struggle with my maths excercice about Bayes' Theorem. Explain it please.. model: Bayes' Theorem Explained

Create a 2-to-5-word title for: {payload.question}<end_of_turn>
<start_of_turn>model
"""
        if model_type == "mistral":
            input_ids = current_tokenizer.encode(mistral_title_generation_prompt, return_tensors="pt").to(device)
            end_ids = current_tokenizer.encode("<|end|>", add_special_tokens=False)
        elif model_type == "gemma":
            input_ids = current_tokenizer.encode(gemma_title_generation_prompt, return_tensors="pt").to(device)
            end_ids = current_tokenizer.encode("<end_of_turn>", add_special_tokens=False)
        stop_crit = StoppingCriteriaList([StopOnEndToken(end_ids[-1])])
    except Exception as e:
        logging.exception("Failed to tokenize prompt")
        raise HTTPException(status_code=500, detail=f"Tokenization error: {str(e)}")
    
    streamer = TextIteratorStreamer(current_tokenizer, skip_prompt=True, skip_special_tokens=True)

    generation_kwargs = dict(
        input_ids=input_ids,
        streamer=streamer,
        max_new_tokens=15,
        temperature=0.05,
        top_p=0.3,
        do_sample=False,
        num_beams=1,
        pad_token_id=current_tokenizer.eos_token_id,
        stopping_criteria=stop_crit
    )

    def run_title_generation():
        try:
            with torch.no_grad():
                loaded_model.generate(**generation_kwargs)
        except Exception as e:
            logging.exception(f"Title generation failed: {e}")
            raise HTTPException(status_code=500, detail=f"Title generation error: {str(e)}")

    title_thread = threading.Thread(target=run_title_generation)
    title_thread.start()

    async def title_stream():
        generated_title = ""
        try:
            for new_text in streamer:
                if (
                    (model_type == "mistral"
                    and new_text.strip() == "" or "<" in new_text or ">" in new_text or "|" in new_text or "end" in new_text or "assistant" in new_text or "system" in new_text or "user" in new_text or "title" in new_text or "Your very short title" in new_text or "Examples:" in new_text or "Create a 2-to-5-word title for:" in new_text
                    )
                    or (model_type == "gemma"
                    and new_text.strip() == "" or "<start_of" in new_text or "<end_of" in new_text or "_turn>" in new_text or "assistant" in new_text or "system" in new_text or "user" in new_text or "title" in new_text or "Your very short title" in new_text or "Examples:" in new_text or "Create a 2-to-5-word title for:" in new_text
                    )
                ):
                    continue
                cleaned_token = new_text[0].upper() + new_text[1:]
                generated_title += cleaned_token
                logging.info(f"Yielding title token: {cleaned_token}")
                yield cleaned_token
        except Exception as e:
            logging.exception("Title streaming failed")
            raise HTTPException(status_code=500, detail="Title streaming failed")
        finally:
            title_thread.join()
            words = generated_title.strip().split()
            if (
                "\"" in words
                or "\'" in words
                or "“" in words
                or "”" in words
                or "‘" in words
                or "’" in words
                or "«" in words
                or "»" in words
                or "title" in words
                or "your" in words
                or "here's" in words
                or "Okay" in words
                or "," in words
                or ":" in words
            ):
                words.remove("\"")
                words.remove("\'")
                words.remove("“")
                words.remove("”")
                words.remove("‘")
                words.remove("’")
                words.remove("«")
                words.remove("»")
                words.remove("title")
                words.remove("your")
                words.remove("here's")
                words.remove("Okay")
                words.remove(",")
                words.remove(":")
            words = [re.sub(r"<.*?>", "", word) for word in words if word]
            final_title = " ".join(words[:6]) if len(words) >= 6 else " ".join(words)
            
            conversation.name = final_title
            db.add(conversation)
            db.commit()
            logging.info("Title generated and saved: %s", conversation.name)
        
    return StreamingResponse(title_stream(), media_type="text/plain")


@router.post("/conversations/{conversation_id}/query")
async def query_and_respond(
    conversation_id: int,
    payload: ConversationQuery,
    db: Session = Depends(get_db),
):  
    logging.info("Payload reçu : %s", payload.dict())
    user_prompt = payload.custom_prompt
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id)
        .first()
    )
     
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    user_message = Message(
        conversation_id=conversation_id,
        sender="user",
        content=payload.question
    )
    db.add(user_message)
    db.flush()
    
    conversation.last_message_time = datetime.now()
    db.commit()

    llm = db.query(Llm).filter(Llm.id == conversation.llm_id).first()
    if not llm:
        raise HTTPException(status_code=404, detail="LLM not found")
    model_type = llm.type
    global loaded_model, current_tokenizer, loaded_model_id

    try:
        if loaded_model_id != llm.id or loaded_model is None:
            start = datetime.now()
            logging.info(f"Loading model {llm.id} from {llm.link}")
            loaded_model = AutoModelForCausalLM.from_pretrained(
                llm.link,
                local_files_only=True,
                torch_dtype=torch.float16 if model_type == "mistral" else torch.bfloat16,
                quantization_config=bnb_config if model_type == "mistral" else None,
                low_cpu_mem_usage=True if model_type == "mistral" else False,
                attn_implementation="flash_attention_2" if float(torch.version.cuda) >= 11.8 and flash_attn_impl else None,
            )
            current_tokenizer = AutoTokenizer.from_pretrained(llm.link, local_files_only=True)
            loaded_model_id = llm.id
            loaded_model.eval()
            loaded_model.to(device)
            logging.info(f"Model {llm.id} loaded in {datetime.now() - start} seconds")
        else:
            logging.info(f"Model {llm.id} already loaded")
            loaded_model.eval()
            loaded_model.to(device)
    except Exception as e:
        logging.exception("Failed to load model or tokenizer")
        raise HTTPException(status_code=500, detail=f"Model loading error: {str(e)}")

    try :
        conversation_history = get_conversation_history(db, conversation_id)
        if not conversation_history:
            context = ""
            logging.info("No previous messages in conversation, skipping context retrieval")
        else:
            logging.info(f"Retrieving context for conversation {conversation_id}")
            start = datetime.now()
            context = retrieve_context(
                payload.question, 
                conversation_history, 
                conversation_id,
                top_k=payload.n_relevent_msgs_to_get or 3,
                n_last_turns=payload.n_last_turns_to_get  or 2,
                model_type=model_type
            )
            logging.info(f"Found relevant context: {context[:100]}... in {datetime.now() - start} seconds")
    except Exception as e:
        logging.exception("Failed to retrieve context")
        raise HTTPException(status_code=500, detail=f"Context retrieval error: {str(e)}")
    

    lang = payload.language
    max_tokens_out = payload.max_new_tokens or 3074
    custom_sys_prompt = payload.custom_prompt if payload.custom_prompt else None
    messages_starred = []
    if conversation_history:
        for msg in conversation_history:
            msg_starred_object = db.query(Message).filter(Message.content == msg[1], Message.starred == True).first()
            if msg_starred_object:
                messages_starred.append(msg_starred_object.content)
    prompt_text = build_conv_prompt(
            question=payload.question,
            context=context,
            language=lang,
            max_tokens=max_tokens_out,
            custom_sys_prompt=custom_sys_prompt,
            messages_starred=messages_starred,
            model_type=model_type,
        )


    logging.info("Final prompt to model:\n%s", prompt_text)


    try:
        input_ids = current_tokenizer.encode(prompt_text, return_tensors="pt").to(device)
        if model_type == "mistral":
            end_ids = current_tokenizer.encode("<end>", add_special_tokens=False)
        elif model_type == "gemma":
            end_ids = current_tokenizer.encode("<end_of_turn>", add_special_tokens=False)
        stop_crit = StoppingCriteriaList([StopOnEndToken(end_ids[-1])])
    except Exception as e:
        logging.exception("Failed to tokenize prompt")
        raise HTTPException(status_code=500, detail=f"Tokenization error: {str(e)}")
    
    streamer = TextIteratorStreamer(current_tokenizer, skip_prompt=True, skip_special_tokens=True)

    generation_kwargs = dict(
        input_ids=input_ids,
        streamer=streamer,
        max_new_tokens=max_tokens_out,
        temperature=payload.temperature or 0.9,
        top_p= payload.top_p or 0.9,
        do_sample=True,
        num_beams=1,
        pad_token_id=current_tokenizer.eos_token_id,
        stopping_criteria=stop_crit
    )

    logging.info("Generation kwargs for Mistral : %s, %s, %s", generation_kwargs["max_new_tokens"], generation_kwargs["temperature"], generation_kwargs["top_p"])

    def run_response_inference():
        logging.info(f"Generating response for conversation {conversation_id} with question: {payload.question}")
        try:
            with torch.no_grad():
                loaded_model.generate(**generation_kwargs)
        except Exception as e:
            logging.exception(f"Generation failed : {e}")
            raise HTTPException(status_code=500, detail=f"Generation error: {str(e)}")

    response_thread = threading.Thread(target=run_response_inference)
    response_thread.start()

    async def assistant_response_token_stream():
        assistant_response = ""
        try:
            for new_text in streamer:
                if model_type == "mistral":
                    cleand_out_token = re.sub(r"<\|/?(?:assistant|system|user|end)\|>", "", new_text)
                elif model_type == "gemma":
                    gemma_token_pattern = r"<start_of_turn>model|<end_of_turn>|<start_of_turn>|of_turn>|<start_of_turn>|"
                    cleand_out_token = re.sub(gemma_token_pattern, "", new_text)
                assistant_response += cleand_out_token
                logging.info(f"Yielding token: {cleand_out_token}")
                yield cleand_out_token
        except Exception as e:
            logging.exception("Streaming failed")
            raise HTTPException(status_code=500, detail="Streaming failed")
        finally:
            response_thread.join()

            assistant_message = Message(
                conversation_id=conversation_id,
                sender="llm",
                content=assistant_response.strip()
            )
            db.add(assistant_message)
            conversation.last_message_time = datetime.now()
            db.commit()
            
            logging.info("Generation thread finished")
        
    return (StreamingResponse(assistant_response_token_stream(), media_type="text/plain"))

@router.post("/conversations/delete_bulk")
async def delete_bulk(
    payload: ConversationDeleteBulk,
    db: Session = Depends(get_db),
):
    """Delete multiple conversations by their IDs (body JSON)."""
    try:
        conversation_ids = payload.conversation_ids
        
        global conversation_summary_cache
        for conv_id in conversation_ids:
            if conv_id in conversation_summary_cache:
                del conversation_summary_cache[conv_id]
                logging.info(f"Cleared summary cache for deleted conversation {conv_id}")
        
        db.query(Conversation).filter(Conversation.id.in_(conversation_ids)).delete(synchronize_session=False)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not delete conversations: {str(e)}",
        )
    return {"message": "Conversations deleted successfully"}

@router.post("/conversations/{conversation_id}/store_error_message")
async def store_error_message(
    conversation_id: int,
    db: Session = Depends(get_db),
):
    """Store an error message in the conversation when generation fails."""
    
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Create an error message from the assistant
    error_message = Message(
        conversation_id=conversation_id,
        sender="llm",
        content="[ERROR_MESSAGE_SYSTEM] I apologize, but I encountered an error while generating a response. Please try asking your question again."
    )
    
    try:
        db.add(error_message)
        conversation.last_message_time = datetime.now()
        db.commit()
        logging.info(f"Stored error message for conversation {conversation_id}")
        if loaded_model or current_tokenizer :
            loaded_model = None
            current_tokenizer = None
            logging.info("Cleared model cache after error message storage")
        return {"message": "Error message stored successfully", "error_message_id": error_message.id}
    except Exception as e:
        db.rollback()
        logging.exception(f"Failed to store error message for conversation {conversation_id}")
        raise HTTPException(status_code=500, detail=f"Failed to store error message: {str(e)}")
    

@router.post("/conversations/star_message")
async def star_message(
    message: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    """Star a message in the conversation."""
    
    message = db.query(Message).filter(Message.content == message).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message to star not found")
    
    message.starred = True
    try:
        db.commit()
        logging.info(f"Message {message.id} starred successfully.")
        return {
            "state": "success",
            "message": "Message starred successfully"
        }
    except Exception as e:
        db.rollback()
        logging.exception(f"Failed to star message.")
        raise HTTPException(status_code=500, detail=f"Failed to star message: {str(e)}")
    
@router.post("/conversations/unstar_message")
async def unstar_message(
    message: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    """Unstar a message in the conversation."""
    
    message = db.query(Message).filter(Message.content == message).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message to unstar not found")
    
    message.starred = False
    try:
        db.commit()
        logging.info(f"Message {message.id} unstarred successfully.")
        return {
            "state": "success",
            "message": "Message unstarred successfully"
        }
    except Exception as e:
        db.rollback()
        logging.exception(f"Failed to unstar message.")
        raise HTTPException(status_code=500, detail=f"Failed to unstar message: {str(e)}")