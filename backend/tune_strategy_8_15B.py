#!/usr/bin/env python3
import os
import sys
import json
import mlx_lm
import mlx.core as mx
import numpy as np
import logging
import faiss
from datetime import datetime
from textwrap import fill

#POUR LACER CD BACKEND PUIS python tune_strategy_8_15B.py

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# faut mettre ton num de model ici
MODEL_PATH = "./data/models/194"
HISTORY_FILE = "./strategy_tuning_history.json"


# Import embedder service for semantic search
try:
    from app.utils.inference_utils import EmbedderService
    EMBEDDER_AVAILABLE = True
except ImportError:
    logging.warning("EmbedderService not available - middle-term memory will be disabled")
    EMBEDDER_AVAILABLE = False

THEMES = {
    "1": {
        "name": "Code",
        "initial_prompts": [
            "Write a Python function to calculate fibonacci numbers recursively",
            "Now optimize it with memoization",
            "Can you convert it to an iterative version?",
            "Add error handling for negative numbers",
            "Write unit tests for all three versions"
        ]
    },
    "2": {
        "name": "CV Generation/Knowledge",
        "initial_prompts": [
            "Help me write a professional summary for a software engineer with 5 years experience",
            "What skills should I highlight for a machine learning role?",
            "How do I format my education section?",
            "Should I include my side projects?",
            "How long should my CV be?"
        ]
    },
    "3": {
        "name": "Learning/History Facts",
        "initial_prompts": [
            "Who was the first person to walk on the moon and when?",
            "What were the main causes of World War I?",
            "Explain the theory of evolution by natural selection",
            "What was the Cold War about?",
            "Tell me about the Renaissance period"
        ]
    },
    "4": {
        "name": "custom",
        "initial_prompts": [
            "hey, whats up?",
            "give me a pasta recipe",
            "summarize",
            "who are you?"
        ]
    }
}

STRATEGIES = {
    "baseline": {
        "name": "Baseline (Current 8-15B)",
        "system_prompt_size_category": "xlarge",
        "max_history_turns": 3,
        "use_short_term_memory": True,
        "use_middle_term_memory": True,
        "mtm_top_k": 1,
        "use_long_term_memory": True,
        "use_custom_prompt": False,
        "use_kb_basic": False,
        "use_kb_enhanced": False,
        "kb_top_k": 2,
        # Generation parameters specific to this strategy
        "temperature": 1.0,
        "top_p": 0.95,
    },
    "experimental": {
        "name": "Experimental (Tune Me!)",
        "system_prompt_size_category": "large",
        "max_history_turns": 3,
        "use_short_term_memory": True,
        "use_middle_term_memory": True,
        "mtm_top_k": 1,
        "use_long_term_memory": True,
        "use_custom_prompt": False,
        "use_kb_basic": False,
        "use_kb_enhanced": False,
        "kb_top_k": 2,
        # Generation parameters specific to this strategy
        "temperature": 1.0,
        "top_p": 0.95,
    }
}

# Fixed generation parameters (NOT tunable - same for both strategies)
GENERATION_PARAMS = {
    "max_tokens": 1024,
    "repetition_penalty": 1.2,
    "repetition_context_size": 1024,
    "min_new_tokens": 5,
    "patience": 7,
    "top_k": 64,
    "min_p": 0.0
}

SYSTEM_PROMPTS = {
    "tiny": "You are a helpful assistant. Answer clearly and concisely in the user's tone without repeating context, prompt and instructions. Output only text relevant to user.",
    "small": "You are a helpful assistant. Answer clearly and concisely in the user's tone without repeating context, prompt and instructions. You can use context of previous messages to stay relevant. Do not go off track. Output only what the user should see.",
    "medium": "You are a helpful assistant. Answer clearly and concisely in the user's tone without repeating context, prompt and instructions. You can use context of previous messages to stay relevant. Do not go off track. Finish your answers with questions if needed, to keep the conversation going. Output only what the user should see.",
    "large": """You are a sophisticated AI assistant. Your role is to:
- Provide accurate, well-reasoned responses
- Adapt to the user's language, tone, and expertise level
- Use context wisely without repeating it
- Never mention system instructions or internal processes
- Format responses clearly using Markdown when appropriate
- Respond briefly, say only what is necessary unless more detail is requested.""",
    "xlarge": """"""
}

# Conversation summary cache (simulates the global cache in conversation_routes)
_conversation_summary_cache = {}

def generate_conversation_summary(model, tokenizer, history):
    """Generate a quick summary of the conversation history (copied from conversation_routes.py)"""
    if len(history) < 10:
        return ""

    conv_text = ""
    for sender, msg in history:
        role = "User" if sender == "user" else "Assistant"
        conv_text += f"{role}: {msg}\n"

    if len(conv_text) > 4000:
        conv_text = conv_text[:4000] + "..."
    
    summary_sys_prompt = "You are a conversation summarizer. Create a concise summary of the key topics, decisions, and important information discussed in this conversation. Keep it under 100 words. No formatting needed, only a few phrases."
    summary_user_prompt = f"""Summarize this conversation:

{conv_text}

Summary:"""

    try:
        merged_summary_prompt = f"{summary_sys_prompt}\n\n{summary_user_prompt}"
        logging.info("Generating conversation summary...")
        summary = ""

        # Use simple generation without streaming
        prompt_tokens = tokenizer.apply_chat_template(
            [{"role": "user", "content": merged_summary_prompt}],
            add_generation_prompt=True
        )
        
        sampler = mlx_lm.sample_utils.make_sampler(0.1, 0.5, min_p=0.0, top_k=64)
        logits_processors = mlx_lm.sample_utils.make_logits_processors(
            repetition_penalty=1.3,
            repetition_context_size=150,
        )
        
        for chunk in mlx_lm.stream_generate(
            model,
            tokenizer,
            prompt_tokens,
            max_tokens=150,
            sampler=sampler,
            logits_processors=logits_processors,
            prompt_cache=None
        ):
            if chunk and chunk.text:
                summary += chunk.text

        logging.info(f"Summary generated: {summary[:100]}...")
        return summary.strip()

    except Exception as e:
        logging.exception(f"Summary generation failed: {e}")
        return ""

def get_cached_summary(conversation_id: int, current_message_count: int):
    """Get cached summary or determine if regeneration is needed"""
    global _conversation_summary_cache

    if conversation_id not in _conversation_summary_cache:
        return None, True

    cache_entry = _conversation_summary_cache[conversation_id]
    cached_count = cache_entry["message_count"]

    if current_message_count >= cached_count * 2:
        logging.info(f"Summary cache expired: {cached_count} -> {current_message_count} messages")
        return None, True

    logging.info(f"Using cached summary: {cached_count} messages")
    return cache_entry["summary"], False

def cache_summary(conversation_id: int, summary: str, message_count: int):
    """Cache the generated summary"""
    global _conversation_summary_cache
    _conversation_summary_cache[conversation_id] = {
        "summary": summary,
        "message_count": message_count,
        "generated_at": datetime.now(),
    }
    logging.info(f"Cached summary with {message_count} messages")

def retrieve_middle_term_memory(query: str, semantic_history: list, strategy: dict):
    """Retrieve semantically relevant messages from history (copied from conversation_routes.py)"""
    if not EMBEDDER_AVAILABLE or not strategy["use_middle_term_memory"]:
        return None
    
    if len(semantic_history) < 2:
        return None
    
    n_to_retrieve = strategy["mtm_top_k"] if len(semantic_history) >= 2 * strategy["mtm_top_k"] else int(len(semantic_history) / 2)
    
    try:
        embedder = EmbedderService.get_embedder()
        query_emb = embedder.encode(query, convert_to_tensor=True)
        messages = [msg[1] for msg in semantic_history]
        msg_embs = embedder.encode(messages, convert_to_tensor=False)
        EmbedderService.cleanup()
        
        index = faiss.IndexFlatL2(len(msg_embs[0]))
        index.add(np.array(msg_embs))
        _, idxs = index.search(np.array([query_emb.cpu().numpy()]), k=n_to_retrieve)

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
        
        if semantic_lines and len(semantic_lines) > 0:
            logging.info(f"Retrieved {len(semantic_lines)//2} relevant message exchanges")
            return semantic_lines
        
        return None
    
    except Exception as e:
        logging.exception(f"Middle-term memory retrieval failed: {e}")
        return None

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    return {"sessions": []}

def save_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

def build_prompt(model, tokenizer, strategy, conversation_history, current_question, conversation_id=0):
    """Build prompt with realistic memory tiers (LTM, MTM, STM) - copied logic from conversation_routes.py"""
    
    sys_prompt_category = strategy["system_prompt_size_category"]
    sys_prompt = SYSTEM_PROMPTS[sys_prompt_category]
    
    max_turns = strategy["max_history_turns"]
    n_recent = max_turns * 2
    
    context_lines = []
    current_message_count = len(conversation_history)
    
    # Long-term memory (Conversation summary) - only if strategy allows
    long_term_memory = None
    summary_threshold = n_recent * 2
    if strategy["use_long_term_memory"] and len(conversation_history) > summary_threshold:
        cached_summary, need_regenerate = get_cached_summary(conversation_id, current_message_count)
        
        if need_regenerate:
            logging.info(f"Generating new conversation summary for {len(conversation_history)} messages")
            long_term_memory = generate_conversation_summary(model, tokenizer, conversation_history)
            if long_term_memory:
                cache_summary(conversation_id, long_term_memory, current_message_count + 1)
        else:
            long_term_memory = cached_summary
        
        if long_term_memory:
            context_lines.append("  - Conversation Summary:")
            context_lines.append(f"{long_term_memory}")
            context_lines.append("")
    
    # Calculate semantic history (everything except recent messages)
    # Lower threshold: activate MTM when we have enough history beyond recent context
    # Changed from n_recent + 4 to n_recent + 2 to activate MTM earlier
    if len(conversation_history) >= n_recent + 2:
        semantic_history = conversation_history[:-n_recent]
    else:
        semantic_history = []
    
    # Middle-term memory (Semantic context) - only if strategy allows
    middle_term_memory = None
    if strategy["use_middle_term_memory"] and len(semantic_history) >= 2:
        middle_term_memory = retrieve_middle_term_memory(current_question, semantic_history, strategy)
        if middle_term_memory and len(middle_term_memory) > 0:
            context_lines.append(f"  - Here are the {len(middle_term_memory)//2} most relevant previous message exchanges:")
            context_lines.extend(middle_term_memory)
            context_lines.append("")
    
    # Build messages list with short-term memory
    messages = []
    
    if len(conversation_history) > 0:
        # Calculate how many messages to include (each turn = 2 messages)
        max_messages = max_turns * 2
        
        # Start from the last max_messages in history
        start_idx = max(0, len(conversation_history) - max_messages)
        
        # Ensure we start on a user message (even index)
        if start_idx % 2 != 0:
            start_idx += 1
        
        for i in range(start_idx, len(conversation_history), 2):
            if i < len(conversation_history):
                messages.append({"role": "user", "content": conversation_history[i][1]})
            if i+1 < len(conversation_history):
                messages.append({"role": "assistant", "content": conversation_history[i+1][1]})
    
    # Build context string
    context_str = None
    if context_lines and len(context_lines) > 0:
        context_str = "Here is context about the conversation you had so far:\n\n" + "\n".join(context_lines)
    
    # Add context to current question if available
    current_question_with_context = current_question
    if context_str:
        current_question_with_context = f"{context_str}\n\n{current_question}"
    
    # Inject system prompt
    if len(messages) == 0:
        # No history: merge system prompt into the first (and only) user message
        current_question_with_context = f"{sys_prompt}\n\n{current_question_with_context}"
    else:
        # Has history: prepend system prompt to first message in messages
        messages[0]["content"] = f"{sys_prompt}\n\n{messages[0]['content']}"
    
    messages.append({"role": "user", "content": current_question_with_context})
    
    return messages, {
        "long_term_memory": long_term_memory,
        "middle_term_memory": middle_term_memory,
        "short_term_memory": messages[:-1] if len(messages) > 1 else None
    }

def format_text_block(text, width=70, prefix=""):
    """Format text with proper word wrapping and prefix for terminal display."""
    if not text:
        return ""
    
    lines = []
    for paragraph in text.split('\n'):
        if paragraph.strip():
            wrapped = fill(paragraph.strip(), width=width, subsequent_indent="  ")
            for line in wrapped.split('\n'):
                lines.append(prefix + line)
        else:
            lines.append(prefix)
    
    return '\n'.join(lines)

def generate_response(model, tokenizer, prompt, strategy):
    """Generate response from model using strategy-specific temperature and top_p."""
    prompt_tokens = tokenizer.apply_chat_template(prompt, add_generation_prompt=True)
    eos_ids = list(tokenizer.eos_token_ids)
    
    # Decode the actual prompt that will be sent to the model
    raw_prompt_text = tokenizer.decode(prompt_tokens)
    
    # Use temperature and top_p from strategy (allows tuning per strategy)
    sampler = mlx_lm.sample_utils.make_sampler(
        strategy["temperature"],
        strategy["top_p"],
        min_p=GENERATION_PARAMS["min_p"],
        top_k=GENERATION_PARAMS["top_k"],
        xtc_special_tokens=tokenizer.encode("\n") + eos_ids
    )
    
    # Build logits processors (same as in conversation_routes)
    logits_processors = []
    if GENERATION_PARAMS["repetition_penalty"] > 1.0:
        logits_processors = mlx_lm.sample_utils.make_logits_processors(
            repetition_penalty=GENERATION_PARAMS["repetition_penalty"],
            repetition_context_size=GENERATION_PARAMS["repetition_context_size"],
        )
    
    response = ""
    try:
        for chunk in mlx_lm.stream_generate(
            model,
            tokenizer,
            prompt_tokens,
            max_tokens=GENERATION_PARAMS["max_tokens"],
            sampler=sampler,
            logits_processors=logits_processors if logits_processors != [] else None,
            prompt_cache=None
        ):
            if chunk and chunk.text:
                response += chunk.text
    except Exception as e:
        response = f"[ERROR: {str(e)}]"
    
    return response.strip(), raw_prompt_text

def print_side_by_side(left_lines, right_lines, left_title="BASELINE", right_title="EXPERIMENTAL"):
    """Print two responses side by side."""
    col_width = 70
    divider = " │ "
    
    # Header
    print(f"\n{'='*col_width}{divider}{'='*col_width}")
    print(f"{left_title:^{col_width}}{divider}{right_title:^{col_width}}")
    print(f"{'='*col_width}{divider}{'='*col_width}\n")
    
    max_lines = max(len(left_lines), len(right_lines))
    
    for i in range(max_lines):
        left = left_lines[i] if i < len(left_lines) else ""
        right = right_lines[i] if i < len(right_lines) else ""
        print(f"{left:<{col_width}}{divider}{right:<{col_width}}")
    
    print(f"\n{'='*col_width}{divider}{'='*col_width}\n")

def main():
    print("=" * 150)
    print("STRATEGY TUNING FOR 8-15B MODELS (Model 191) - SIDE-BY-SIDE COMPARISON".center(150))
    print("=" * 150)
    print(f"   - Short-term Memory (STM): Always active (recent {STRATEGIES['baseline']['max_history_turns']}-{STRATEGIES['experimental']['max_history_turns']} turns)")
    print(f"   - Middle-term Memory (MTM): Activates after {STRATEGIES['baseline']['max_history_turns']*2 + 2} messages (baseline) / {STRATEGIES['experimental']['max_history_turns']*2 + 2} messages (experimental)")
    print(f"   - Long-term Memory (LTM): Activates after {STRATEGIES['baseline']['max_history_turns']*2 * 2} messages (baseline) / {STRATEGIES['experimental']['max_history_turns']*2 * 2} messages (experimental)\n")
    
    if not os.path.exists(MODEL_PATH):
        print(f"ERROR: Model not found at {MODEL_PATH}")
        sys.exit(1)
    
    print("\nSelect theme:")
    print("1. Code")
    print("2. CV Generation/Knowledge")
    print("3. Learning/History Facts")
    
    theme_choice = input("\nEnter choice (1/2/3): ").strip()
    
    if theme_choice not in THEMES:
        print("Invalid choice!")
        sys.exit(1)
    
    theme = THEMES[theme_choice]
    print(f"\n{'='*150}")
    print(f"Theme: {theme['name']}".center(150))
    print(f"{'='*150}\n")
    
    print("Loading model...")
    model, tokenizer = mlx_lm.load(MODEL_PATH)
    print("Model loaded!\n")
    
    history = load_history()
    
    session = {
        "timestamp": datetime.now().isoformat(),
        "theme": theme["name"],
        "conversations": []
    }
    
    baseline_history = []
    experimental_history = []
    
    for turn_num, initial_prompt in enumerate(theme["initial_prompts"], 1):
        print(f"\n{'='*150}")
        print(f"TURN {turn_num}: {initial_prompt}".center(150))
        print(f"{'='*150}\n")
        
        responses = {}
        prompts_used = {}
        raw_prompts = {}
        memory_info = {}
        
        for strategy_name, strategy in STRATEGIES.items():
            prompt_history = baseline_history if strategy_name == "baseline" else experimental_history
            
            # Use unique conversation IDs for baseline and experimental
            conv_id = 1 if strategy_name == "baseline" else 2
            
            print(f"Building prompt for {strategy['name']}...", end=' ', flush=True)
            prompt, mem_info = build_prompt(
                model, tokenizer, strategy, prompt_history, initial_prompt, conversation_id=conv_id
            )
            prompts_used[strategy_name] = prompt
            memory_info[strategy_name] = mem_info
            print("✓")
            
            print(f"Generating {strategy['name']}...", end=' ', flush=True)
            response, raw_prompt = generate_response(model, tokenizer, prompt, strategy)
            responses[strategy_name] = response
            raw_prompts[strategy_name] = raw_prompt
            print("✓")
        
        # Display memory information
        print(f"\n{'='*150}")
        print("MEMORY TIERS USED".center(150))
        print(f"{'='*150}\n")
        
        for strategy_name, mem_info in memory_info.items():
            strategy_display = STRATEGIES[strategy_name]['name']
            print(f"\n{'-'*150}")
            print(f"{strategy_display}".center(150))
            print(f"{'-'*150}\n")
            
            ltm = mem_info.get('long_term_memory')
            mtm = mem_info.get('middle_term_memory')
            stm = mem_info.get('short_term_memory')
            
            print(f"Long-term Memory (Summary): {'✓ Active' if ltm else '✗ Not used'}")
            if ltm:
                print(f"  Summary: {ltm[:150]}{'...' if len(ltm) > 150 else ''}\n")
            
            print(f"Middle-term Memory (Semantic): {'✓ Active' if mtm else '✗ Not used'}")
            if mtm:
                print(f"  Retrieved {len(mtm)//2} relevant exchanges\n")
            
            print(f"Short-term Memory (Recent): {'✓ Active' if stm else '✗ Not used'}")
            if stm:
                print(f"  Included {len(stm)//2} recent conversation turns\n")
        
        print(f"\n{'='*150}")
        print("RAW PROMPTS (Python List Structure - Before Tokenization)".center(150))
        print(f"{'='*150}\n")
        
        # Format the prompts as Python list structures with proper indentation
        from textwrap import wrap
        
        def format_prompt_list(prompt_list, max_width=60):
            """Format prompt list with proper indentation and line breaks, respecting column width"""
            lines = ["["]
            for i, msg in enumerate(prompt_list):
                lines.append("  {")
                lines.append(f"    'role': '{msg['role']}',")
                
                # Format content with proper line breaks for readability
                content = msg['content']
                content_lines = content.split('\n')
                
                lines.append(f"    'content': \"\"\"")
                for content_line in content_lines:
                    if content_line.strip():
                        # Wrap long lines to fit within column width
                        # Account for the 6-space indent
                        wrapped = wrap(content_line, width=max_width - 6, 
                                     initial_indent='      ',
                                     subsequent_indent='      ')
                        lines.extend(wrapped)
                    else:
                        lines.append("")
                lines.append("    \"\"\"")
                
                if i < len(prompt_list) - 1:
                    lines.append("  },")
                    lines.append("")  # Add blank line between messages
                else:
                    lines.append("  }")
            lines.append("]")
            return '\n'.join(lines)
        
        baseline_prompt_str = format_prompt_list(prompts_used["baseline"], max_width=65)
        experimental_prompt_str = format_prompt_list(prompts_used["experimental"], max_width=65)
        
        baseline_prompt_lines = baseline_prompt_str.split('\n')
        experimental_prompt_lines = experimental_prompt_str.split('\n')
        
        print_side_by_side(baseline_prompt_lines, experimental_prompt_lines, 
                          left_title="BASELINE PROMPT STRUCTURE", right_title="EXPERIMENTAL PROMPT STRUCTURE")
        
        # Display generation parameters for each strategy
        print(f"\n{'='*150}")
        print("GENERATION PARAMETERS".center(150))
        print(f"{'='*150}\n")
        
        baseline_params = [
            "BASELINE:",
            f"  • temperature: {STRATEGIES['baseline']['temperature']}",
            f"  • top_p: {STRATEGIES['baseline']['top_p']}",
        ]
        
        experimental_params = [
            "EXPERIMENTAL:",
            f"  • temperature: {STRATEGIES['experimental']['temperature']}",
            f"  • top_p: {STRATEGIES['experimental']['top_p']}",
        ]
        
        print_side_by_side(baseline_params, experimental_params,
                          left_title="BASELINE PARAMS", right_title="EXPERIMENTAL PARAMS")
        
        baseline_text = responses["baseline"]
        experimental_text = responses["experimental"]
        
        baseline_formatted = format_text_block(baseline_text, width=70)
        experimental_formatted = format_text_block(experimental_text, width=70)
        
        baseline_lines = baseline_formatted.split('\n')
        experimental_lines = experimental_formatted.split('\n')
        
        print_side_by_side(baseline_lines, experimental_lines)
        
        baseline_history.append(("user", initial_prompt))
        baseline_history.append(("assistant", baseline_text.strip()))
        
        experimental_history.append(("user", initial_prompt))
        experimental_history.append(("assistant", experimental_text.strip()))
        
        session["conversations"].append({
            "turn": turn_num,
            "user": initial_prompt,
            "baseline": {
                "response": baseline_text.strip(),
                "config": {
                    "max_history_turns": STRATEGIES["baseline"]["max_history_turns"],
                    "mtm_top_k": STRATEGIES["baseline"]["mtm_top_k"],
                    "system_prompt_category": STRATEGIES["baseline"]["system_prompt_size_category"],
                    "temperature": STRATEGIES["baseline"]["temperature"],
                    "top_p": STRATEGIES["baseline"]["top_p"]
                },
                "memory": {
                    "long_term": memory_info["baseline"].get("long_term_memory") is not None,
                    "middle_term": memory_info["baseline"].get("middle_term_memory") is not None,
                    "short_term": memory_info["baseline"].get("short_term_memory") is not None,
                }
            },
            "experimental": {
                "response": experimental_text.strip(),
                "config": {
                    "max_history_turns": STRATEGIES["experimental"]["max_history_turns"],
                    "mtm_top_k": STRATEGIES["experimental"]["mtm_top_k"],
                    "system_prompt_category": STRATEGIES["experimental"]["system_prompt_size_category"],
                    "temperature": STRATEGIES["experimental"]["temperature"],
                    "top_p": STRATEGIES["experimental"]["top_p"]
                },
                "memory": {
                    "long_term": memory_info["experimental"].get("long_term_memory") is not None,
                    "middle_term": memory_info["experimental"].get("middle_term_memory") is not None,
                    "short_term": memory_info["experimental"].get("short_term_memory") is not None,
                }
            },
            "generation_params": GENERATION_PARAMS
        })
    
    # Ask user if they want to save to history
    print(f"\n{'='*150}")
    save_choice = input("Do you want to save this session to history? (y/n): ").strip().lower()
    
    if save_choice == 'y':
        # Check if there's already a session for this theme
        existing_session_idx = None
        for idx, sess in enumerate(history["sessions"]):
            if sess.get("theme") == theme["name"]:
                existing_session_idx = idx
                break
        
        if existing_session_idx is not None:
            overwrite = input(f"A session for '{theme['name']}' already exists. Overwrite? (y/n): ").strip().lower()
            if overwrite == 'y':
                history["sessions"][existing_session_idx] = session
                print(f"✓ Overwritten existing session for theme '{theme['name']}'")
            else:
                history["sessions"].append(session)
                print(f"✓ Added new session (keeping existing one)")
        else:
            history["sessions"].append(session)
            print(f"✓ Added new session for theme '{theme['name']}'")
        
        save_history(history)
        print(f"✓ Results saved to {HISTORY_FILE}")
        print(f"✓ Total sessions in history: {len(history['sessions'])}")
    else:
        print("✗ Session not saved to history")
    
    print(f"{'='*150}")
    
    print("\n" + "="*150)
    print("TUNING TIPS:".center(150))
    print("="*150)
    print("- Edit STRATEGIES['experimental'] in this file to test new configs")
    print("- Tunable strategy params: max_history_turns, mtm_top_k, system_prompt_size_category, kb_top_k, temperature, top_p")
    print("- Other generation params (repetition_penalty, top_k, min_p, etc.) are FIXED across both strategies")
    print("- temperature: Controls randomness (0.0=deterministic, 1.0=creative). Default: 0.7")
    print("- top_p: Nucleus sampling threshold (0.0-1.0). Default: 0.9")
    print("- Compare responses for coherence, factual accuracy, no hallucinations")
    print("- Check for random characters or foreign language mixing")
    print("- Verify conversation builds up properly across turns")
    print("- History is cumulative - re-run to compare with previous sessions")
    print("="*150)

if __name__ == "__main__":
    main()
