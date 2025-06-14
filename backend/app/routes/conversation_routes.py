from ..schemas.message_schemas import MessageCreate, MessageResponse
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import torch
from datetime import datetime
from transformers import AutoTokenizer, AutoModelForCausalLM, TextIteratorStreamer, pipeline, StoppingCriteria, StoppingCriteriaList, AutoModelForSeq2SeqLM
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
from ..prompting.builder import build_default_prompt, build_custom_prompt
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

router = APIRouter()

class StopOnEndToken(StoppingCriteria):
    def __init__(self, end_token_id: int):
        super().__init__()
        self.end_token_id = end_token_id
    def __call__(self, input_ids, scores, **kwargs):
        # arrête si le dernier token généré est <|end|>
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

def retrieve_context(query: str, conversation_history, top_k=3):

    def get_embedder():
        global embedder
        if embedder is None:
            logging.info("Loading the Embedder")
            start = datetime.now()

            os.makedirs(CACHE_DIR, exist_ok=True)

            embedder = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", cache_folder=CACHE_DIR)
            logging.info(f"Embedder loaded in {datetime.now() - start} seconds")
        return embedder

    if conversation_history is None or len(conversation_history) < 2:
        return ""
   
    embedder = get_embedder()
    semantic_context = "* The most relevant previous messages based on semantic similarity:\n"
    recency_context = "* The last two turns between you and the user:\n"
    if len(conversation_history) >= 4:
        logging.info("Using semantic search for context retrieval")
        query_embedding = embedder.encode(query, convert_to_tensor=True)
        message_embeddings = embedder.encode([msg[1] for msg in conversation_history], convert_to_tensor=False)
    
        dimension = len(message_embeddings[0])
        index = IndexFlatL2(dimension)
        index.add(np.array(message_embeddings))
    
        _, indices = index.search(np.array([query_embedding.cpu().numpy()]), k=min(top_k, len(conversation_history)))

        already_used_messages = set()
        already_used_messages.add(query)
        for idx in indices[0]:
            sender = conversation_history[idx][0]
            message_text = conversation_history[idx][1]
            if message_text in already_used_messages:
                continue
            
            if sender != "user":
                sender = "[assistant]"
            else:
                sender = "[user]"

            if sender == "[assistant]" and idx > 0:
                prev_sender, prev_msg = conversation_history[idx - 1]
                if (prev_msg) not in already_used_messages:
                    semantic_context += f"[user]: {prev_msg}\n"
                    already_used_messages.add(prev_msg)
                    semantic_context += f"{sender}: {message_text}\n"
                    already_used_messages.add(message_text)
            elif sender == "[user]" and idx + 1 < len(conversation_history):
                next_sender, next_msg = conversation_history[idx + 1]
                if (next_msg) not in already_used_messages:
                    semantic_context += f"{sender}: {message_text}\n"
                    already_used_messages.add(message_text)
                    semantic_context += f"[assistant]: {next_msg}\n"
                    already_used_messages.add(next_msg)
                    



        last_two_turns = conversation_history[-5:-1]
        recency_context += "\n".join([f"[assistant]: {msg}" if sender != "user" else f"[user]: {msg}" for sender, msg in last_two_turns])
    else:
        recency_context += "\n".join([f"[assistant]: {msg}" if sender != "user" else f"[user]: {msg}" for sender, msg in conversation_history])
    
    relevant_context = "Here is some context about the conversation you had so far:\n\n"
    if semantic_context != "* The most relevant previous messages based on semantic similarity:\n":
        relevant_context += semantic_context
        relevant_context +="\n\n"
        relevant_context += recency_context
    else:
        relevant_context += recency_context

    return relevant_context


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
    
    global loaded_model, current_tokenizer, loaded_model_id

    try:
        if loaded_model_id != llm.id or loaded_model is None:
            start = datetime.now()
            logging.info(f"Loading model {llm.id} from {llm.link}")
            loaded_model = AutoModelForCausalLM.from_pretrained(
                llm.link, local_files_only=True, torch_dtype=torch.float16
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
        title_generation_prompt = f"""<|system|>You are a title generator. You must create VERY SHORT titles. No more than 5 words. Use only essential keywords. No articles (a, an, the). No punctuation.<|end|>

<|user|>Create a 2-to-5-word title for: {payload.question}

Examples:
- How to cook pasta? → Pasta Cooking Guide
- What is machine learning? → Machine Learning Basics
- Help me with Python code → Python Code Help

Your very short title:<|end|>
<|assistant|>"""
        input_ids = current_tokenizer.encode(title_generation_prompt, return_tensors="pt").to(device)
        end_ids = current_tokenizer.encode("<|end|>", add_special_tokens=False)
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
                if new_text.strip() == "" or "<" in new_text or ">" in new_text or "|" in new_text:
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
            if "\"" in words or "\'" in words or "“" in words or "”" in words or "‘" in words or "’" in words or "«" in words or "»" in words: 
                words.remove("\"")
                words.remove("\'")
                words.remove("“")
                words.remove("”")
                words.remove("‘")
                words.remove("’")
                words.remove("«")
                words.remove("»")
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

    # Add user message to database
    user_message = Message(
        conversation_id=conversation_id,
        sender="user",
        content=payload.question
    )
    db.add(user_message)
    db.flush()
    
    conversation.last_message_time = datetime.utcnow()
    db.commit()

    # Get LLM for response generation
    llm = db.query(Llm).filter(Llm.id == conversation.llm_id).first()
    if not llm:
        raise HTTPException(status_code=404, detail="LLM not found")
    
    global loaded_model, current_tokenizer, loaded_model_id

    try:
        if loaded_model_id != llm.id or loaded_model is None:
            start = datetime.now()
            logging.info(f"Loading model {llm.id} from {llm.link}")
            loaded_model = AutoModelForCausalLM.from_pretrained(
                llm.link, local_files_only=True, torch_dtype=torch.float16
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
            context = retrieve_context(payload.question, conversation_history, top_k=payload.n_msgs_to_get_from_conv or 3)
            logging.info(f"Found relevant context: {context[:100]}... in {datetime.now() - start} seconds")
    except Exception as e:
        logging.exception("Failed to retrieve context")
        raise HTTPException(status_code=500, detail=f"Context retrieval error: {str(e)}")
    

    lang = payload.language
    max_tokens_out = payload.max_new_tokens or 3074

    prompt_text = build_default_prompt(
            question=payload.question,
            context=context,
            language=lang,
            max_tokens=max_tokens_out
        )

    if payload.custom_prompt:
        logging.info("➡️ Rendering custom prompt via Jinja")
        prompt_text_customized = build_custom_prompt(
            payload.custom_prompt,
            payload.question,
            context,
            lang
        )
        prompt_text = ( prompt_text + "\n Instructions Utilisateur Personnalisées : " + prompt_text_customized )


    logging.info("Final prompt to model:\n%s", prompt_text)


    try:
        input_ids = current_tokenizer.encode(prompt_text, return_tensors="pt").to(device)
        end_ids = current_tokenizer.encode("<|end|>", add_special_tokens=False)
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
                cleand_out_token = re.sub(r"<\|/?(?:assistant|system|user|end)\|>", "", new_text)
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
            conversation.last_message_time = datetime.utcnow()
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
        db.query(Conversation).filter(Conversation.id.in_(conversation_ids)).delete(synchronize_session=False)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not delete conversations: {str(e)}",
        )
    return {"message": "Conversations deleted successfully"}