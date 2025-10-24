# 🧠 Erudi — Unified Engineering and Development Guidelines

---

## Vision and Product Context

Erudi is a desktop application **for local LLM inference and specialization**, combining a **FastAPI backend** with an **Electron + React frontend**.  
It enables users to **specialize and use open-source LLMs locally**, attaching knowledge bases, performing RAG, and (soon) performing causal fine-tuning — all **without the cloud**.

### Goals
- Provide a simple, accessible UI (“easy mode”) and a powerful future “advanced mode.”
- Focus on **specialization** (style, jargon, KB attachments) more than raw fine-tuning.
- Support **cross-hardware inference**:
  - **Mac Silicon (MLX_LM)**
  - **Windows/Linux NVIDIA GPUs (CUDA + bitsandbytes)**
  - **CPU fallback** for unsupported systems.
- Remain **multi-OS and multi-engine compatible**.
- Respect strong **software engineering and architectural discipline**.

---

## Architecture Overview

- **Multi-Engine Architecture**:  
  - `BaseEngine` abstraction  
  - Implementations: `MLX_Engine`, `CUDA_Engine`, `CPU_Engine`
  - Auto-selected by `BaseEngine.get_engine()` via platform/hardware detection

- **Domain-driven structure** (`backend/src/domains/`):  
  - `conversations/`: Chat and streaming  
  - `llms/`: Model lifecycle  
  - `knowledge_base/`: RAG with FAISS  
  - `arena/`: Model comparison  
  - `training/`: Fine-tuning  
  - `hardware/`: System monitoring

- **Data Layer**: SQLite with SQLAlchemy ORM + repository pattern  
- **Frontend**: Electron + React + Tailwind with context providers  
- **Communication**: REST API only (no WebSocket)  
- **Memory**: multi-level (short-term, middle-term vector, long-term summaries, KB injection)

---

## Development Workflow

### Setup
Platform-specific setup scripts:  
- Mac Silicon → `setup-mac-silicon.sh`  
- Linux CUDA → `setup-linux-cuda-121.sh`  
- Windows CUDA → `setup-win-cuda-121.ps1`

They create virtual environments and install from `backend/requirements/entrypoints/{platform}.txt`.

### Run
`bash
# Backend
uvicorn src.main:app --reload

# Frontend
npm start
`

---

## File Hierarchy

`plaintext
backend/
├── data/           # SQLite DB, models, cache
├── logs/           # Structured logs
├── src/
│   ├── core/       # Config, logging, exceptions
│   ├── domains/    # Business logic
│   ├── engines/    # LLM inference backends
│   ├── entities/   # SQLAlchemy models
│   └── utils/      # Helpers
`

---

## Coding Standards

### Naming
- Variables, functions, files, directories → `snake_case`
- Classes → `Capitalized_Snake_Case`
- Constants → `UPPER_SNAKE_CASE`
- Migrations/scripts → `snake_case_action.py`

### Style
- Follow **PEP 8**, **mypy --strict**, **black**, **ruff**
- Type hints required
- Use structured logging
- No hardcoded paths (use `pathlib.Path`)
- No bare `except`; define all custom errors in `src/core/exceptions.py`

### Imports
- Always absolute from `src.*`
- Cross-domain imports only via service interfaces

### Structure
- Small modules with single responsibility
- Use FastAPI’s `Depends()` for DI
- No tight coupling or circular imports

### Logging
- Structured logs via `src/core/logging.py`
- DEBUG for internals, INFO for transitions, WARNING/ERROR for problems
- Never log PII, paths, or prompts

### Concurrency
- Engines coordinate via non-blocking mechanisms
- Heavy tasks go to thread executors
- Use `StreamingResponse` for async token generation

### Exceptions
- Specific, meaningful, and raised from core exception classes only

---

## Requirements

### Functional
- Follow FastAPI route patterns
- Preserve token streaming
- Handle model parameters: temperature, top_p, max_tokens
- Maintain RAG and KB compatibility

### Non-functional
- DRY, KISS, SOLID
- Deterministic, modular, small pure functions
- Structured logging and traceability
- No O(n²) behavior on large datasets

### Compatibility
- Code must run identically across dev and prod
- Engine- or OS-specific logic → only inside `backend/src/engines/`
- Graceful degradation (CPU fallback)
- No architecture or API regressions

---

## Constraints

- Domain-driven structure:
  - `API → Service → Repository → Entity`
- No synchronous I/O inside async routes
- Keep engine interface uniform (`BaseEngine`)
- Avoid global locks when possible (prefer queues or batching)

---

## Success Criteria

- Fully tested: unit, integration, e2e
- Green CI: lint, mypy, pytest, ruff
- Works on MLX, CUDA, and CPU
- Streaming responses functional
- No regressions or deadlocks
- Backward compatible with data and API

---

## Engine and OS Rules

- New backend- or OS-sensitive logic lives in `backend/src/engines/`
- Use capability detection instead of OS strings
- Guard optional dependencies
- Keep model paths consistent (`backend/data/models/` and `/models_cache/`)

---

## API Rules

- Routes belong to domain routers
- Pydantic schemas for validation
- Use `StreamingResponse` for streaming
- Versioned or backward-compatible schema changes only

---

## Data and Knowledge Base Rules

- SQLAlchemy models validated and idempotent
- FAISS operations isolated and locked safely
- Datasets: local upload (PDF/TXT)
- RAG: question vectorization → top-N chunk injection

---

## Testing Policy

Unit tests  
- Services and engines with mocks  
- Error cases: model missing, bad params, OOM, timeout  

Integration tests  
- Real FastAPI endpoints  
- Mini FAISS index RAG  

e2e  
- Load a model per engine type  
- Validate generation + RAG  
- Mock engine fallback if needed  

Quality gates  
- ruff, black, mypy, pytest -q  
- No skipped tests in CI

---

## Performance and Memory

- Use generators for large payloads  
- Avoid tensor copies  
- Batch vector searches  
- Timeout I/O and HF downloads  

---

## Operational Readiness

- Clear errors with remediation hints  
- CPU fallback if CUDA/MLX unavailable  
- Config via environment variables only  
- No hardcoded tokens or paths  

---

## Acceptance Checklist

- [ ] Reads context, avoids duplicate work  
- [ ] Respects naming, structure, and placement  
- [ ] Works across all supported OS/hardware  
- [ ] API backward compatible  
- [ ] Structured, secure logging  
- [ ] Tests passing (unit/integration/e2e)  
- [ ] No new lint/type errors  
- [ ] Streaming output validated  

---

## References

- [PEP 8](https://peps.python.org/pep-0008/)  
- [FastAPI](https://fastapi.tiangolo.com/)  
- [SQLAlchemy](https://docs.sqlalchemy.org/)  
- [Pydantic](https://docs.pydantic.dev/)  
- [Uvicorn](https://www.uvicorn.org/)  
- [FAISS](https://github.com/facebookresearch/faiss)  
- [Transformers](https://huggingface.co/docs/transformers/)  
- [bitsandbytes](https://github.com/TimDettmers/bitsandbytes)  
- [MLX](https://github.com/ml-explore/mlx)  
- [Electron](https://www.electronjs.org/docs)  
- [React](https://react.dev/)  
- [Tailwind](https://tailwindcss.com/docs)

---

## Example Templates

Engine extension  
`# backend/src/engines/cpu_engine.py  
from src.engine.base_engine import BaseEngine  

class CPU_Engine(BaseEngine):  
    def is_available(self) -> bool:  
        return True  

    async def generate_stream(self, prompt: str, params: dict):  
        # yield tokens without blocking event loop  
        yield from self._run_in_executor(prompt, params)`

API endpoint  
`# backend/src/domains/conversations/api.py  
from fastapi import APIRouter, Depends  
from starlette.responses import StreamingResponse  
from .schemas import GenerateRequest  
from .service import Conversation_Service  
from src.core import config  

router = APIRouter()  

@router.post("/generate")  
async def generate(req: GenerateRequest, svc: Conversation_Service = Depends()):  
    stream = config.LLM_Engine.generate_stream(req.prompt, req.params.dict())  
    return StreamingResponse(stream, media_type="text/plain")`

---

## Responses to user guidelines
- When talking directly to the user (not when writing code in the files), be clear and concise.
- Ask clarifying questions if the request is ambiguous or lacks context.
- Once you finished writing code, provide a brief explanation of what was done, don't over-explain.

## Final Directive

When defining a new **task or code objective**, always:  
1. Understand the **big picture** (architecture, engine, OS, UX).  
2. Verify **existing modules** before writing code.  
3. Implement **modular, DRY, typed, testable** components.  
4. Ensure functionality works on **all engines and OS**.  
5. Keep CI green, code documented, and architecture intact.

Follow this unified document for all agentic and Copilot code generations inside Erudi.
