#!/usr/bin/env python3
"""
Simple Gemma Prompt Testing Script
Just edit the variables below and run the script to test different prompts
"""

import mlx_lm
from transformers import AutoTokenizer

# ============================================================================
# EDIT THESE VARIABLES TO TEST DIFFERENT PROMPTS
# ============================================================================

# Your Jinja2 chat template (or use None to use model's default)
CUSTOM_TEMPLATE = None

  # Set to None to use model's built-in template
# Example custom template:
# CUSTOM_TEMPLATE = """{{ bos_token }}{% for message in messages %}<start_of_turn>{{ message['role'] }}
# {{ message['content'] }}<end_of_turn>
# {% endfor %}<start_of_turn>model
# """

# System instruction (the "personality" of the assistant)
SYSTEM_INSTRUCTION = "You are gemma 3 1B, a concise and helpful assistant; answer directly in the user's tone without repeating context or mentioning instructions."

# RAG context (relevant information to include, or None)
RAG_CONTEXT = None
# Example RAG context:
# RAG_CONTEXT = """
# Relevant information:
# - Paris is the capital and largest city of France
# - It has a population of over 2 million people
# """

# Custom prompt (additional instructions, or None)
CUSTOM_PROMPT = None
# Example: "Answer in French"

# Conversation history (previous messages, or None for no history)
# This simulates memory of past conversation
CONVERSATION_HISTORY = None
# Example with history:
CONVERSATION_HISTORY = [
    ("Hello!", "Hi! How can I help you today?"),
    ("What's 2+2?", "2+2 equals 4."),
]

# The question to test
QUESTION = "are you sure?"

# Model path
MODEL_PATH = "./data/models/833"  # Gemma 3B

# Generation settings
TEMPERATURE = 0.1
TOP_P = 0.5
MAX_TOKENS = 3200

# ============================================================================
# SCRIPT (don't need to edit below unless you want to)
# ============================================================================

def main():
    print("="*80)
    print("GEMMA PROMPT TESTER")
    print("="*80)
    
    # Load model and tokenizer
    print(f"\nLoading model from: {MODEL_PATH}")
    model, tokenizer = mlx_lm.load(MODEL_PATH)
    print("✓ Model loaded")
    
    # Show where the default template comes from
    print("\n" + "="*80)
    print("CHAT TEMPLATE INFO:")
    print("="*80)
    
    if CUSTOM_TEMPLATE:
        print("\n✓ Using CUSTOM Jinja2 template (defined in this script)")
        print("\nYour custom template:")
        print(CUSTOM_TEMPLATE)
        tokenizer.chat_template = CUSTOM_TEMPLATE
    else:
        print("\n✓ Using MODEL'S DEFAULT template")
        print(f"\nTemplate loaded from: {MODEL_PATH}/tokenizer_config.json")
        
        if hasattr(tokenizer, 'chat_template') and tokenizer.chat_template:
            print("\nThe default template is:")
            print("-" * 80)
            print(tokenizer.chat_template)
            print("-" * 80)
        else:
            print("\n⚠ Warning: No chat template found in model!")
    
    # Build the system message
    sys_msg = SYSTEM_INSTRUCTION
    
    if CUSTOM_PROMPT:
        sys_msg += f"\nAdditional instructions: {CUSTOM_PROMPT}"
    
    if RAG_CONTEXT:
        sys_msg += f"\nRelevant context:\n{RAG_CONTEXT}"
    
    # Create messages with conversation history
    messages = []
    
    if CONVERSATION_HISTORY and len(CONVERSATION_HISTORY) > 0:
        # With history: merge system message into first user message
        first_user_msg = f"{sys_msg}\n\n{CONVERSATION_HISTORY[0][0]}"
        messages.append({"role": "user", "content": first_user_msg})
        messages.append({"role": "assistant", "content": CONVERSATION_HISTORY[0][1]})
        
        # Add remaining history
        for user_msg, assistant_msg in CONVERSATION_HISTORY[1:]:
            messages.append({"role": "user", "content": user_msg})
            messages.append({"role": "assistant", "content": assistant_msg})
    
    # Add the current question
    if len(messages) == 0:
        # No history: merge system into current question
        user_message = f"{sys_msg}\n\n{QUESTION}"
        messages.append({"role": "user", "content": user_message})
    else:
        # Has history: just add the question
        messages.append({"role": "user", "content": QUESTION})
    
    # Show what we're sending
    print("\n" + "="*80)
    print("PROMPT BEING SENT:")
    print("="*80)
    print(f"\nSystem Instruction:")
    print(f"  {SYSTEM_INSTRUCTION}")
    
    if CUSTOM_PROMPT:
        print(f"\nCustom Prompt:")
        print(f"  {CUSTOM_PROMPT}")
    
    if RAG_CONTEXT:
        print(f"\nRAG Context:")
        print(f"  {RAG_CONTEXT}")
    
    if CONVERSATION_HISTORY:
        print(f"\nConversation History ({len(CONVERSATION_HISTORY)} turns):")
        for i, (user_msg, assistant_msg) in enumerate(CONVERSATION_HISTORY, 1):
            print(f"  {i}. User: {user_msg[:60]}...")
            print(f"     Assistant: {assistant_msg[:60]}...")
    else:
        print(f"\nConversation History: None (fresh conversation)")
    
    print(f"\nCurrent Question:")
    print(f"  {QUESTION}")
    
    # Format with template
    print("\n" + "="*80)
    print("FORMATTED PROMPT (after applying chat template):")
    print("="*80)
    formatted_prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )
    print(formatted_prompt)
    
    # Tokenize
    prompt_tokens = tokenizer.apply_chat_template(messages, add_generation_prompt=True)
    print(f"\nToken count: {len(prompt_tokens)}")
    
    # Create sampler
    eos_id = tokenizer.eos_token_id
    sampler = mlx_lm.sample_utils.make_sampler(
        TEMPERATURE,
        TOP_P,
        min_p=0.0,
        top_k=64,
        xtc_special_tokens=tokenizer.encode("\n") + [eos_id]
    )
    
    # Generate
    print("\n" + "="*80)
    print(f"GENERATING RESPONSE (temp={TEMPERATURE}, top_p={TOP_P}, max_tokens={MAX_TOKENS}):")
    print("="*80)
    
    response_text = ""
    for chunk in mlx_lm.stream_generate(
        model,
        tokenizer,
        prompt_tokens,
        max_tokens=MAX_TOKENS,
        sampler=sampler,
        prompt_cache=None
    ):
        response_text += chunk.text
    
    # Clean up response (remove extra end tokens)
    clean_response = response_text.split('<end_of_turn>')[0].strip()
    
    print("\n" + "="*80)
    print("CLEAN RESPONSE (use this for conversation history):")
    print("="*80)
    print(clean_response)
    
    print("\n" + "="*80)
    print("RAW RESPONSE (with tokens):")
    print("="*80)
    print(response_text[:500])  # First 500 chars
    
    print("\n" + "="*80)
    print("TO ADD THIS TO CONVERSATION HISTORY:")
    print("="*80)
    print("Copy this into your CONVERSATION_HISTORY list:")
    print(f'    ("{QUESTION}", "{clean_response}"),')
    
    print("\n✓ Done!")

if __name__ == "__main__":
    main()
