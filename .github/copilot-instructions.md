# 🧠 Erudi — Engineering Guidelines

---

## Context
Erudi is a **desktop app** for **local LLM specialization**, built with **FastAPI (backend)** and **Electron + React (frontend)**.  
It supports **Mac Silicon (MLX)**, **NVIDIA CUDA**, and **CPU fallback** — all offline.

---

## Architecture
- **Engines**: `BaseEngine` + `MLX_Engine`, `CUDA_Engine`, `CPU_Engine`
- **Domains**: `conversations`, `llms`, `knowledge_base`, `arena`, `training`, `hardware`
- **Data**: SQLite + SQLAlchemy ORM  
- **Frontend**: React + Tailwind  
- **Communication**: REST API only  

---

## Coding Rules
- Naming: `snake_case` for files/vars, `Capitalized_Snake_Case` for classes  
- Type hints required; follow **PEP8**, **mypy**, **ruff**, **black**  
- Absolute imports from `src.*`, no circular dependencies  
- No hardcoded paths; use `pathlib.Path`  
- Logging: structured via `src/core/logging.py`, no PII or prompts  
- OS/backend logic → only in `backend/src/engines/`  

---

## Exceptions
- All custom exceptions inherit from `AppBaseException` in `src/core/exceptions.py`  
- Include status code + custom error code  
- Global handler returns structured JSON  
- Never use `except:`; catch specific errors  

---

## Development Workflow
1. **Document first** (Google-style docstrings: Args, Returns, Raises)  
2. **Write tests** (unit + integration)  
3. **Use venv**: `backend/venv/bin/python` and `pip`  
4. **Run CI checks**: ruff, black, mypy, pytest — all must pass  

---

## Testing
- Unit: mock services/engines  
- Integration: FastAPI endpoints  
- e2e: generation + RAG on all engines  
- No skipped tests or regressions  

---

## Rules
- Domain-driven flow: `API → Service → Repository → Entity`  
- Async only, no blocking I/O  
- Extend `BaseEngine` for new backends  
- Code must run on all OS with graceful fallback  

---

## Documentation
- Every public function/class has docstring  
- Update `/docs` on new features or API changes  
- Avoid unnecessary explanations or file redactions  

---

## Agent Behavior
- Never create or edit unrequested documents after task completion  
- After finishing, give a **short chat summary only** (no `.md` files)  
- Ask clarifying questions if needed  

---

## Checklist
- [ ] Follows naming & structure  
- [ ] Typed, linted, tested  
- [ ] Works on all OS/engines  
- [ ] Structured logs only  
- [ ] Docs updated if needed  

---

## Final Directive
Always:
1. Understand the architecture before coding  
2. Reuse existing modules  
3. Write modular, typed, testable code  
4. Ensure multi-engine and multi-OS compatibility  
5. Be concise when reporting results to the user
