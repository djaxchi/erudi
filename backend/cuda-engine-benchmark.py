import asyncio, os, logging, time
from huggingface_hub import HfApi, HfFileSystem
import sys
# try:
#     import llmcompressor
# except Exception as e:
#     print("[WARN] llmcompressor not importable:", e, file=sys.stderr)
#     raise
# try:
#     import vllm
# except Exception as e:
#     print("[WARN] vllm not importable:", e, file=sys.stderr)
#     raise
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN", None)
non_quant_dir = Path("data", "models", "llmcompressor", "base-gemma-4B")

####################### POUR TELECHARGER UN MODELE #######################
# async def download_files_concurrent(
#     fs,
#     tasks,
#     local_dir,
# ) -> None:
#     """
#     Download multiple files concurrently using asyncio Executor.

#     Args:
#         fs (HfFileSystem): Hugging Face filesystem instance.
#         callback (Callback): Callback for progress updates.
#         tasks (List[Tuple[str,str]]): List of (repo_id, file_path).
#         local_dir (str): Base local directory to save files.
#     """
#     loop = asyncio.get_running_loop()
#     coros = []
#     for repo_id, path in tasks:
#         remote = f"{repo_id}/{path}"
#         dest = os.path.join(local_dir, path)
#         os.makedirs(os.path.dirname(dest), exist_ok=True)
#         coros.append(loop.run_in_executor(None, fs.get_file, remote, dest))
#     await asyncio.gather(*coros)

# async def download_llm(
#     model_link: str,
#     save_dir: str,
# ) -> str:
#     """
#     Download a Hugging Face repo with progress tracking and optional DB updates.

#     Args:
#         model_link (str): Hugging Face repo ID (could be original or MLX-quantized).
#         final_save_dir (str): Final directory for model.

#     Returns:
#         str: Final local path containing downloaded files.
#     """
    
#     actual_download_link = model_link
    
#     os.makedirs(save_dir, exist_ok=True)

#     # Initialize HF API & filesystem
#     api = HfApi(token=HF_TOKEN)
#     fs = HfFileSystem(token=HF_TOKEN)

#     # Gather file sizes and compute total
#     info = api.repo_info(actual_download_link, files_metadata=True)
#     file_sizes = {
#         s.rfilename: s.size
#         for s in info.siblings
#         if s.size
#     }

#     # Split tasks into misc and shard files
#     all_files = [f for f in api.list_repo_files(actual_download_link) if f in file_sizes]
#     misc = [f for f in all_files if not f.endswith(".safetensors")]
#     shards = [f for f in all_files if f.endswith(".safetensors")]

#     # Download misc sequentially
#     for path in misc:
#         await asyncio.to_thread(fs.get_file, f"{actual_download_link}/{path}", os.path.join(save_dir, path))
#         logging.info(f"Downloaded {path}")

#     # Download shards concurrently
#     shard_tasks = [(actual_download_link, path) for path in shards]
#     await download_files_concurrent(fs, shard_tasks, save_dir)
#     logging.info("All shards downloaded")
    
#     logging.info("Download complete")

#     return save_dir

# async def main():
#     print("Downloading Base LLM")
#     t0 = time.time()
#     await download_llm(model_link="google/gemma-3-4b-it", save_dir=non_quant_dir)
#     dt=time.time()-t0
#     print(f"[INFO] LLM downloaded in {dt:.1f}s in {non_quant_dir}")

# asyncio.run(main())



####################### VLLM TESTS #######################
# def stream_inference_vllm(model_path: str, prompt: str, max_tokens: int = 128, temperature: float = 0.2):
    
#     """
#     Run a streaming inference with vLLM and print token deltas as they arrive.
#     Uses vLLM Python API: LLM + SamplingParams.
#     """

#     print(f"[INFO] Instantiating vLLM with model='{model_path}' ...")
#     t0 = time.time()
#     llm = vllm.LLM(model=str(model_path))
#     print(f"[INFO] vLLM instantiated in {time.time() - t0:.2f}s")

#     sampling_params = vllm.SamplingParams(temperature=float(temperature), max_tokens=int(max_tokens))
#     print(f"[INFO] Starting generation (temperature={temperature}, max_tokens={max_tokens})")
#     prev_text = ""

#     # generate() returns an iterator over streaming results in modern vLLM versions.
#     gen = llm.generate(inputs=[prompt], sampling_params=sampling_params)

#     try:
#         for step in gen:
#             # Common shape: step.outputs[0].text
#             text = None
#             try:
#                 if hasattr(step, "outputs") and len(step.outputs) > 0:
#                     text = step.outputs[0].text
#                 elif isinstance(step, (list, tuple)) and len(step) > 0 and hasattr(step[0], "text"):
#                     text = step[0].text
#                 else:
#                     text = str(step)
#             except Exception:
#                 text = str(step)

#             if text is None:
#                 continue

#             # compute delta (new suffix)
#             if not text.startswith(prev_text):
#                 # longest common prefix heuristic
#                 lp = 0
#                 max_lp = min(len(prev_text), len(text))
#                 while lp < max_lp and prev_text[lp] == text[lp]:
#                     lp += 1
#                 delta = text[lp:]
#             else:
#                 delta = text[len(prev_text):]

#             if delta:
#                 # print chunk without newline to simulate streaming
#                 print(delta, end="", flush=True)
#                 prev_text = text
#     except TypeError:
#         # fallback: generate may have returned a full completed object instead of streaming
#         print("\n[WARN] vLLM generate object not iterable, falling back to single-call extract.")
#         out = gen
#         # try to read final text
#         final = None
#         try:
#             if isinstance(out, list) and out:
#                 candidate = out[0]
#                 final = candidate.outputs[0].text if hasattr(candidate, "outputs") else str(candidate)
#             else:
#                 final = str(out)
#         except Exception:
#             final = str(out)
#         # stream the final text token-by-token (simple whitespace split)
#         import re
#         tokens = re.findall(r"\S+|\n", final)
#         for tok in tokens:
#             print(tok, end=" ", flush=True)
#     print("\n[INFO] Generation complete.")










####################### OPTIMUM/AUTO-GPTQ TESTS #######################

# from transformers import AutoModelForCausalLM, AutoTokenizer
# from optimum.gptq import GPTQQuantizer, load_quantized_model
# import torch
# model_name = str(non_quant_dir)
# print("Loading base model")
# tokenizer = AutoTokenizer.from_pretrained(model_name)
# model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float16)
# print("Base model loaded")

# print("Creating config for GPTQ Quantizer")
# quantizer = GPTQQuantizer(
#     bits=4,
#     cache_block_outputs=False,
#     dataset="c4"
# )
# print("Config created")

# print("Quantizing model")
# quantized_model = quantizer.quantize_model(model, tokenizer)
# print("Model Quantized")

# print("Saving quantized model")
# quant_dir = Path("data", "models", "llmcompressor", "awq-gemma-4B")
# quantizer.save(model, str(quant_dir))
# print("Quantized model saved")

# print("Loading quantized model")
# from accelerate import init_empty_weights
# with init_empty_weights():
#     empty_model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float16)
# empty_model.tie_weights()
# quantized_model = load_quantized_model(empty_model, save_folder=str(quant_dir), device_map="auto")

# # Tokenize input
# prompt = "Tell me two phrases about AWQ Quantization"
# temperature = 0.2
# max_tokens = 1024

# inputs = tokenizer(prompt, return_tensors="pt").to(quantized_model.device)

# # Prepare streamer
# # Sampling parameters
# gen_kwargs = dict(
#     **inputs,
#     max_new_tokens=max_tokens,
#     temperature=temperature,
#     do_sample=True,
# )

# print(f"[INFO] Starting Generation (temperature={temperature}, max_tokens={max_tokens})")
# v0 = time.time()
# out = quantized_model.generate(**gen_kwargs)
# dt = time.time() - v0
# print(f"Generated in {dt:.1f}s.\nPrompt is: {prompt}\nResponse is: {out}")











####################### LLMCOMPRESSOR TESTS #######################

# t0 = time.time()
# quant_dir = Path("data", "models", "llmcompressor", "awq-gemma-4B")
# recipe = [
#     llmcompressor.modifiers.smoothquant.SmoothQuantModifier(smoothing_strength=0.8),
#     llmcompressor.modifiers.quantization.GPTQModifier(scheme="W8A8", targets="Linear", ignore=["lm_head"]),
# ]
# llmcompressor.oneshot(
#     model=str(non_quant_dir),
#     dataset="open-platypus",
#     output_dir=quant_dir,
#     recipe=recipe,
#     save_compressed=True,
#     max_seq_length=2048,
#     num_calibration_samples=512,
#     # recipe can be left default or pass modifiers (AWQ/GPTQ)
# )

# dt = time.time() - t0
# print(f"[INFO] oneshot finished in {dt:.1f}s. Compressed model saved to: {quant_dir}")

# test_prompt = "Explique la quantization AWQ en deux phrases simples."
# try:
#     print("Testing quantized model")
#     tstart = time.time()
#     stream_inference_vllm(quant_dir, test_prompt, max_tokens=128, temperature=0.2)
#     print(f"[INFO] Inference roundtrip time: {time.time() - tstart:.2f}s")
# except Exception as e:
#     print("[ERROR] Inference failed:", e, file=sys.stderr)

# try:
#     print("Testing non quantized model")
#     tstart = time.time()
#     stream_inference_vllm(non_quant_dir, test_prompt, max_tokens=128, temperature=0.2)
#     print(f"[INFO] Inference roundtrip time: {time.time() - tstart:.2f}s")
# except Exception as e:
#     print("[ERROR] Inference failed:", e, file=sys.stderr)
