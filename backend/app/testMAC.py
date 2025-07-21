from threading import Thread
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, QuantoConfig, TextIteratorStreamer
import dotenv, os

dotenv.load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")
os.environ["TOKENIZERS_PARALLELISM"] = "true"


device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
print(f"Using device: {device}")
if device.type == "mps":
    torch.mps.empty_cache()
    print("MPS cache cleared.")

# Quanto quantization config — smallest footprint
quant_config = QuantoConfig(
    weights="int8",
    activations=None,
)
print("Downloading and quantizing with Quanto...")
model = AutoModelForCausalLM.from_pretrained(
    "mistralai/Mistral-7B-Instruct-v0.3",
    quantization_config=quant_config,
    torch_dtype=torch.float16,       # let Quanto override to int8/float8
    low_cpu_mem_usage=True,
    token=HF_TOKEN,
    cache_dir="data/models_cache"
)
model.eval()

# Compile the model to improve runtime memory & speed
# model = torch.compile(model)

model.to(device)
print("Model quantized and compiled.")

print("Downloading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(
    "mistralai/Mistral-7B-Instruct-v0.3",
    cache_dir="data/models_cache",
    token=HF_TOKEN,
    padding=True
)

prompt = input("🕺 Enter your prompt: ")
try:
    input_ids = tokenizer.encode(prompt, return_tensors="pt").to(device)
except Exception as e:
    print("Failed to tokenize prompt")

streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)

generation_kwargs = dict(
    input_ids=input_ids,
    streamer=streamer,
    max_new_tokens=30,
    temperature=0.9,
    top_p=0.9,
    do_sample=True,
    num_beams=1,
    pad_token_id=tokenizer.eos_token_id,
)

thread = Thread(target=model.generate, kwargs=generation_kwargs)
thread.start()

# Consume tokens as they appear
print("Generated response:")
for token in streamer:  # token is a string chunk
    print(token, end="", flush=True)

thread.join()
print("\n✅ Done")

print("Cleanup...")
del model, tokenizer
torch.mps.empty_cache()
print("Done.")
