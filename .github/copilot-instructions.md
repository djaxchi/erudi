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

They create virtual environments and install from `backend/requirements/entrypoints/dev/{platform}.txt` (or `prod/{platform}-prod.txt` for production).

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

### Exception Handling

**Core Principles:**
- All business exceptions inherit from `AppBaseException` (defined in `src/core/exceptions.py`)
- Never use bare `except:` - always catch specific exception types
- All custom exceptions must be defined in `src/core/exceptions.py`
- Exceptions include HTTP status codes, custom error codes, and structured logging

**Exception Hierarchy:**
```python
AppBaseException (base class)
├── ModelNotFoundException (404, MODEL_NOT_FOUND)
├── InvalidInputException (422, INVALID_INPUT)
├── EngineException (500, LLM_ENGINE_FAILURE)
├── EmbeddingError (500, EMBEDDING_FAILURE)
└── [Add new exceptions here following the pattern]
```

**Creating New Exceptions:**
1. Define in `src/core/exceptions.py` inheriting from `AppBaseException`
2. Provide appropriate HTTP status code (use `fastapi.status` constants)
3. Define custom Erudi error code (e.g., "EMBEDDING_FAILURE", "KB_NOT_FOUND")
4. Include clear error messages with remediation hints
5. Document in docstring: when raised, what it means, how to fix

**Example:**
```python
class EmbeddingError(AppBaseException):
    """Exception raised for embedding generation failures.
    
    Raised when sentence-transformers embedding model fails to encode text,
    including model loading errors, out-of-memory conditions, or invalid input.
    
    Examples:
        from src.core.exceptions import EmbeddingError
        try:
            embeddings = embedder.encode(text)
        except Exception as e:
            raise EmbeddingError(f"Failed to embed text: {e}")
    """
    
    def __init__(self, message: str, trace: Optional[str] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            erudi_code="EMBEDDING_FAILURE",
            trace=trace
        )
```

**Usage in Code:**
```python
# ❌ BAD - bare except
try:
    result = risky_operation()
except:
    pass

# ❌ BAD - generic exception without context
try:
    model = load_model(model_id)
except Exception:
    raise Exception("Error loading model")

# ✅ GOOD - specific exception with context
from src.core.exceptions import ModelNotFoundException

try:
    model = load_model(model_id)
except FileNotFoundError as e:
    raise ModelNotFoundException(model_id, trace=str(e))
```

**FastAPI Integration:**
- Global exception handler registered in `src/core/api.py`
- Returns structured JSON responses: `{"success": false, "error": {"type": "...", "message": "..."}}`
- Automatic logging with request path and error details

---

## Documentation

### Management
- **MkDocs + Material theme** for comprehensive documentation
- **Scripts in `scripts/documentation_audit/`** for automated generation and quality control
- **CI/CD integration** with quality gates (90% docstring coverage required)
- **Versioned docs** in `docs/` (narrative guides + API reference)

### Writing New Code
- **Google-style docstrings** required for all public functions, classes, and methods
- **Complete coverage**: Args, Returns, Raises sections with types
- **Update `docs/`** when adding new features or changing APIs
- **Run audit scripts** after changes: `python scripts/documentation_audit/quality_control.py`

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

## Development Workflow

### Code Implementation Requirements

When implementing new code, **always** follow this workflow:

1. **Document First**
   - Write Google-style docstrings for all functions, classes, and methods
   - Include Args, Returns, Raises, Examples sections
   - Update relevant documentation in `docs/` if adding new features

2. **Write Tests**
   - Create unit tests in `backend/tests/test_<domain>.py`
   - Follow the 3-layer architecture (Repository → Service → Endpoints)
   - Use fixtures from `conftest.py` for database and mocks
   - Test both success and error cases

3. **Make Tests Pass**
   - Run tests with `backend/venv/bin/python -m pytest tests/test_<module>.py -v`
   - Fix all failures before moving forward
   - Ensure no regressions in existing tests

### Python Environment Usage

**CRITICAL**: Always use the virtual environment for Python operations:

- **Run Python**: `backend/venv/bin/python` (NOT just `python`)
- **Install packages**: `backend/venv/bin/pip install <package>` (NOT just `pip`)
- **Run pytest**: `backend/venv/bin/python -m pytest` (NOT just `pytest`)
- **Run scripts**: `backend/venv/bin/python scripts/script.py`

This ensures operations run in the correct environment with proper dependencies.

### Package Management

When installing new Python packages:

1. **Development packages** (pytest, black, mypy, etc.):
   - Add to `backend/requirements/meta/dev.txt`
   - Format: `package==version  # comment explaining purpose`

2. **Production packages** (after user validation):
   - Add to appropriate meta file:
     - `backend/requirements/meta/base.txt` (all platforms)
     - `backend/requirements/meta/mac-silicon-specs.txt` (Mac Silicon only)
     - `backend/requirements/meta/cuda-121-specs.txt` (CUDA 12.1 only)
     - etc.
   - Rebuild entrypoint requirements: run appropriate build script

3. **Never install without updating requirements**:
   - All dependencies must be tracked
   - Include version pinning for reproducibility
   - Comment on purpose and platform constraints

### Testing Workflow Example

```bash
# 1. Implement feature with docstrings
# 2. Write tests
# 3. Run tests
cd backend
source venv/bin/activate
python -m pytest tests/test_knowledge_base.py::TestKB_Service -v

# 4. Run all domain tests
python -m pytest tests/test_knowledge_base.py -v

# 5. Check coverage (optional)
python -m pytest tests/test_knowledge_base.py --cov=src.domains.knowledge_base

# 6. Fix any failures and repeat
```

### Package Installation Example

```bash
# Install new dev dependency
cd backend
source venv/bin/activate
pip install httpx==0.28.1

# Immediately update requirements
echo "httpx==0.28.1  # HTTP client for testing" >> requirements/meta/dev.txt

# If approved for production, add to base.txt
echo "httpx==0.28.1  # HTTP client for API requests" >> requirements/meta/base.txt
```

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

Before considering any implementation complete, verify:

### Code Quality
- [ ] Reads context, avoids duplicate work  
- [ ] Respects naming, structure, and placement (snake_case, repository pattern)
- [ ] Works across all supported OS/hardware (Mac Silicon, Linux CUDA, CPU fallback)
- [ ] API backward compatible  
- [ ] Structured, secure logging (no PII, paths, or prompts)
- [ ] No new lint/type errors (ruff, black, mypy pass)

### Documentation
- [ ] Google-style docstrings for all public functions/classes/methods
- [ ] Includes Args, Returns, Raises, Examples sections
- [ ] Updated `docs/` if new features or API changes
- [ ] README.md updated if user-facing changes

### Testing
- [ ] Unit tests written in `backend/tests/test_<domain>.py`
- [ ] Tests cover success cases and error cases
- [ ] All tests passing: `backend/venv/bin/python -m pytest tests/test_<module>.py -v`
- [ ] No skipped tests (unless documented reason)
- [ ] No regressions in existing tests
- [ ] Mock heavy dependencies (FAISS, embeddings, model loading)

### Environment & Dependencies
- [ ] Used `backend/venv/bin/python` and `backend/venv/bin/pip` for all operations
- [ ] New dev packages added to `backend/requirements/meta/dev.txt`
- [ ] New prod packages added to appropriate meta file (after user approval)
- [ ] Version pinning included with explanatory comments
- [ ] Tested in isolated venv to verify dependencies

### Functionality
- [ ] Feature works as intended on target platform(s)
- [ ] Streaming output validated (if applicable)
- [ ] Error messages clear with remediation hints
- [ ] Handles edge cases (empty input, missing files, network errors)

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
