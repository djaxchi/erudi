"""Business logic for stateless arena LLM queries with KB-aware prompting.

The arena is "conversation minus state": a single-model, no-history streaming
query. Since the LangChain refactor it shares the conversation ``AgentRunner``
but runs it statelessly (``thread_id=None``, no checkpointer, no summarization).

Pipeline:
1. Validate the question and fetch the LLM.
2. Pick a prompting strategy (param_size-based) and, if the model has a KB
   attached, retrieve top-k chunks (hybrid pgvector search via ``kb_utils``).
3. Build a real system prompt (size-adaptive + custom + KB context) and stream
   the answer as raw token text via the shared agent runner.

The A/B "duel" is orchestrated entirely on the frontend (N parallel calls to
this endpoint); the runner's engine guard serializes them on the single-model
engine, so model swaps don't thrash the subprocess.
"""

from typing import AsyncGenerator, Dict, Any

from fastapi.concurrency import run_in_threadpool

from src.core.logging import logger
from src.utils.prompt_utils import get_prompting_strategy
from src.utils.kb_utils import KbExcerpt, retrieve_kb_excerpts
from src.agents.prompts import build_agent_system_prompt, build_kb_system_prompt
from src.agents.runner import AgentRunner, GenParams
from src.domains.arena.repository import ArenaRepository
from src.domains.arena.schemas import ArenaQueryPayload
from src.entities.Llm import Llm
from src.core.exceptions import (
    KnowledgeBaseNotFoundException,
    KnowledgeBaseCorruptedException,
    InvalidInputException,
)


class ArenaService:
    """Service layer for arena stateless query processing."""

    def __init__(self, db):
        """Initialize arena service with database session.

        Args:
            db: SQLAlchemy database session for repository access.
        """
        logger.debug("Initializing ArenaService")
        self.arena_repo = ArenaRepository(db)
        self.runner = AgentRunner(checkpointer=None)  # stateless: no history persisted
        self.db = db

    def _get_llm(self, llm_id: int) -> Llm:
        """Retrieve LLM entity by ID via repository (raises 404 if missing)."""
        return self.arena_repo.get_llm_by_id(llm_id)

    def _retrieve_kb_excerpts(
        self,
        llm: Llm,
        query: str,
        strategy: Dict[str, Any],
    ) -> list[KbExcerpt]:
        """Adaptive KB excerpts if the LLM has a KB attached and strategy allows.

        Adaptive selection through the hybrid pgvector search (``kb_utils``
        façade). Returns an empty list when KB is unavailable/disabled.
        """
        if not llm.is_attached_to_kb or not strategy.get("use_kb_context", False):
            return []

        try:
            return retrieve_kb_excerpts(
                query, llm, token_budget=strategy["kb_token_budget"]
            )
        except (KnowledgeBaseNotFoundException, KnowledgeBaseCorruptedException):
            raise
        except Exception as e:
            logger.exception("Failed to retrieve Knowledge Base context")
            raise KnowledgeBaseCorruptedException(
                llm.kb_id,
                f"Knowledge Base retrieval error: {e}",
                trace=str(e),
            )

    async def query_llm_stream(
        self,
        llm_id: int,
        payload: ArenaQueryPayload,
    ) -> AsyncGenerator[str, None]:
        """Query an LLM in stateless arena mode and stream response tokens (raw text).

        Raises:
            InvalidInputException: empty question.
            ModelNotFoundException: ``llm_id`` not found (via ``_get_llm``; the
                endpoint also validates eagerly before opening the stream).
            KnowledgeBase*Exception: KB retrieval failure.

        Generation/model-load failures are NOT raised here — the runner yields the
        ``[ERROR_MESSAGE_SYSTEM]`` sentinel inline (unified with conversation).
        """
        if not payload.question or not payload.question.strip():
            raise InvalidInputException("question")

        logger.info(f"Querying LLM {llm_id} from DB")
        llm = self._get_llm(llm_id)

        param_size = llm.param_size if getattr(llm, "param_size", None) else 2
        strategy = get_prompting_strategy(param_size)

        # Hybrid retrieval is sync (embed + SQL) — run it off the event loop.
        # With excerpts, the dedicated KB prompt REPLACES the tier prompt
        # (strict grounding; the tier prompts fight RAG — issue #81).
        excerpts = await run_in_threadpool(
            self._retrieve_kb_excerpts, llm, payload.question, strategy
        )
        if excerpts:
            system_prompt = build_kb_system_prompt(
                llm,
                excerpts=excerpts,
                question=payload.question,
                custom_prompt=payload.custom_prompt,
            )
        else:
            system_prompt = build_agent_system_prompt(
                llm, custom_prompt=payload.custom_prompt
            )

        params = GenParams(
            temperature=payload.temperature,
            top_p=payload.top_p,
            max_tokens=payload.max_new_tokens,
        )

        async for token in self.runner.astream_text(
            llm=llm,
            user_message=payload.question,
            system_prompt=system_prompt,
            params=params,
            thread_id=None,
            summarize=False,
        ):
            yield token
