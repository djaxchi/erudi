"""Database initialization and seeding for application startup.

This module provides a clean, type-safe API for database initialization:
- Table creation via SQLAlchemy ORM
- Model seeding from HuggingFace Hub
- Job cleanup and recovery
- Hardware profiling
- Startup state initialization

Architecture:
    ┌─────────────────────────────────────────────────────────┐
    │ Database_Seeder (Facade)                                │
    │  ├─> create_tables()                                    │
    │  ├─> populate_startup_data()                            │
    │  └─> delete_all_data() [DEV ONLY]                       │
    └─────────────────────────────────────────────────────────┘
                            ↓
    ┌─────────────────────────────────────────────────────────┐
    │ Specialized Seeders                                     │
    │  ├─> Model_Seeder: Base + derived models               │
    │  ├─> Job_Cleanup_Service: Jobs + orphaned models       │
    │  ├─> Hardware_Initializer: System profiling            │
    │  └─> Startup_Initializer: First-run flags              │
    └─────────────────────────────────────────────────────────┘

Example:
    Automatic startup (production)::

        from src.database.seed import Database_Seeder

        seeder = Database_Seeder()
        await seeder.create_tables()
        await seeder.populate_startup_data()

    Manual reset (development only)::

        seeder = Database_Seeder()
        await seeder.delete_all_data()  # Requires confirmation

Design Principles:
    - Single Responsibility: Each class handles one seeding concern
    - Type Safety: Full type hints, Pydantic for validation
    - Error Handling: Custom exceptions with structured logging
    - Testability: Dependency injection for all external services
    - Idempotency: Safe to run multiple times
    - Separation of Concerns: Business logic separated from I/O

Note:
    This module uses a facade pattern to provide a simple API while
    maintaining clean separation of concerns internally.
"""

import os
import shutil
import json
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.core.logging import logger
from src.core.config import get_hf_api
from src.core import config
from src.database import core
from src.database.core import Base, SessionLocal
from src.core.exceptions import (
    DatabaseException,
    HuggingFaceAPIException,
    FileSystemException,
)

from src.utils.hf_model_metadata import (
    get_disk_size_after_quant,
    get_model_size_estimate,
    format_model_info_metadata,
    extract_parameter_pattern,
    humanize_model_name,
    ParameterScale,
)
from src.domains.hardware.repository import Hardware_Repository
from src.domains.hardware.services import Hardware_Service
from src.engines.tool_capability import tool_capability_from_hf_repo

from src.entities.Conversation import Conversation
from src.entities.Llm import Llm
from src.entities.Message import Message
from src.entities.DownloadJob import DownloadJobModel
from src.entities.HardwareProfile import HardwareProfile
from src.entities.KnowledgeDocument import KnowledgeDocument
from src.entities.KnowledgeBase import KnowledgeBase
from src.entities.KBJob import KBJobModel
from src.entities.StartupVariables import StartupVariables


# ============ Connectivity & Offline Mode Helpers ============

def is_online() -> bool:
    """Check if internet connection is available via HuggingFace API.
    
    Attempts a lightweight API call to verify connectivity. Used to determine
    whether to seed models from HuggingFace or use offline fallback.
    
    Returns:
        bool: True if online and can reach HuggingFace, False otherwise.
    
    Note:
        Uses a 5-second timeout to avoid blocking startup for too long.
        Caches result is not needed (only called once during startup).
    
    Example:
        >>> if is_online():
        ...     seed_from_huggingface()
        ... else:
        ...     seed_from_local_cache()
    """
    try:
        api = get_hf_api()
        # Lightweight check: Try to get model count (doesn't download anything)
        api.list_models(limit=1).__iter__().__next__()
        return True
    except Exception as e:
        logger.warning(f"Internet connectivity check failed: {e}")
        return False


def load_base_models_fallback() -> List[Dict[str, Any]]:
    """Load base models from embedded JSON fallback file.
    
    Used when offline or HuggingFace API is unavailable. Provides minimal
    model metadata to allow app functionality without internet.
    
    Returns:
        List[Dict]: List of base model configurations from JSON file.
    
    Raises:
        FileSystemException: If fallback JSON file is missing or corrupted.
    
    Note:
        JSON file located at: src/database/base_models_fallback.json
        Contains 7 curated base models with essential metadata.
    
    Example:
        >>> models = load_base_models_fallback()
        >>> print(models[0]['name'])  # "Gemma-1B"
    """
    fallback_path = config.ROOT_DIR / "src" / "database" / "base_models_fallback.json"
    
    try:
        with open(fallback_path, 'r') as f:
            models = json.load(f)
        
        logger.info(f"Loaded {len(models)} base models from offline fallback")
        return models
    
    except FileNotFoundError:
        raise FileSystemException(
            f"Base models fallback file not found: {fallback_path}",
            trace="FileNotFoundError"
        )
    except json.JSONDecodeError as e:
        raise FileSystemException(
            f"Failed to parse base models fallback JSON: {e}",
            trace=str(e)
        )


# ============ Configuration Data Classes ============

@dataclass(frozen=True)
class Model_Config:
    """Configuration for a base model to seed."""
    
    name: str
    link: str
    model_type: str
    
    def __post_init__(self) -> None:
        """Validate model configuration."""
        if not self.name or not self.link or not self.model_type:
            raise ValueError(f"Invalid model config: {self}")


@dataclass(frozen=True)
class Search_Config:
    """Configuration for derived model search."""
    
    search_term: str
    model_type: str
    default_param_size: float
    
    def __post_init__(self) -> None:
        """Validate search configuration."""
        if not self.search_term or not self.model_type:
            raise ValueError(f"Invalid search config: {self}")
        if self.default_param_size <= 0:
            raise ValueError(f"Invalid param size: {self.default_param_size}")


@dataclass(frozen=True)
class Quality_Filters:
    """Quality thresholds for model filtering."""
    
    min_downloads: int = 50
    min_likes: int = 5
    interesting_tags: Tuple[str, ...] = (
        "instruction-tuned", "chat", "conversational", "assistant",
        "code", "math", "reasoning", "multilingual", "translation",
        "summarization", "question-answering", "creative-writing",
        "roleplay", "medical", "legal", "science", "education",
        "storytelling", "dialogue", "text-generation"
    )
    quality_keywords: Tuple[str, ...] = (
        "instruct", "chat", "assistant", "tuned", "fine-tuned",
        "trained", "optimized", "enhanced", "improved"
    )
    skip_ids: Tuple[str, ...] = (
        "mistral-7b-instruct-v0.3", "mistral-7b-v0.3",
        "gemma-3-1b-it", "gemma-2-2b-it", "gemma-3-4b-it",
        "ministral-8b-instruct-2410", "gemma-3-12b-it",
        "mistral-nemo-instruct-2407",
        "gemma-4-e2b-it", "gemma-4-e4b-it",
    )
    skip_terms: Tuple[str, ...] = (
        "gguf", "gptq", "bnb", "4bit", "8bit", "f16", "awq",
        "q4", "q5", "q6", "q8", "fp8", "fp16", "fp4", "sqft",
        "quantized", "quant", "quantization", "lora", "knut",
        "sft", "int4", "int8", "int16", "int32", "int64",
        "peft", "test", "untrained", "checkpoint", "tmp", "temp",
        "debug", "draft", "experiment", "eval", "benchmark",
        "pt", "onnx", "abliterated",
    )


# ============ Model Seeding Service ============

class Model_Seeder:
    """Handles seeding of base and derived models from HuggingFace.
    
    Supports both online and offline modes:
    - Online: Fetches fresh metadata from HuggingFace API
    - Offline: Uses embedded JSON fallback with minimal metadata
    """
    
    def __init__(
        self,
        db: Session,
        hf_api=None,
        quality_filters: Optional[Quality_Filters] = None,
        offline_mode: bool = False
    ):
        """Initialize model seeder.
        
        Args:
            db: Active database session.
            hf_api: HuggingFace API client (None if offline).
            quality_filters: Quality filtering configuration.
            offline_mode: If True, skip API calls and use fallback data.
        """
        self.db = db
        self.hf_api = hf_api
        self.filters = quality_filters or Quality_Filters()
        self.offline_mode = offline_mode
    
    def seed_base_models(self, models: List[Model_Config]) -> int:
        """Seed curated base models with quantized variants.
        
        Args:
            models: List of base model configurations.
        
        Returns:
            Number of models successfully added.
        
        Raises:
            Exception: If database commit fails.
        """
        added_count = 0
        
        for model_config in models:
            # Dedup by the resolved (stable) link, not the display name — display
            # names are derived from the slug and may change without re-seeding.
            quant_link = config.LLM_Engine.MODEL_MAPPING.get(model_config.link)
            actual_link = quant_link or model_config.link
            if self._link_exists(actual_link):
                logger.debug(f"Skipping existing model: {actual_link}")
                continue

            try:
                llm = self._create_base_llm(model_config)
                self.db.add(llm)
                self.db.flush()  # Flush to catch DB errors early
                added_count += 1
                logger.info(f"Added base model: {model_config.name}")
            except DatabaseException:
                raise
            except HuggingFaceAPIException as e:
                logger.error(f"HF API error for {model_config.name}: {e}")
                self.db.rollback()
                # Try fallback with default metadata
                try:
                    llm = self._create_base_llm_fallback(model_config)
                    self.db.add(llm)
                    self.db.flush()
                    added_count += 1
                    logger.warning(f"Added {model_config.name} with fallback metadata")
                except DatabaseException as db_error:
                    raise DatabaseException(
                        f"Failed to add model {model_config.name} even with fallback",
                        trace=str(db_error)
                    )
        
        self.db.commit()
        return added_count
    
    def seed_base_models_offline(self) -> int:
        """Seed base models from embedded JSON fallback (offline mode).
        
        Used when internet is unavailable or HuggingFace API fails. Loads
        models from static JSON file with minimal but sufficient metadata.
        
        Returns:
            Number of models successfully added from fallback.
        
        Raises:
            FileSystemException: If fallback JSON is missing or corrupted.
            DatabaseException: If database operations fail.
        
        Note:
            This method ONLY seeds base models. Derived models are skipped
            in offline mode as they require fresh HuggingFace searches.
        
        Example:
            >>> seeder = Model_Seeder(db, offline_mode=True)
            >>> count = seeder.seed_base_models_offline()
            >>> print(f"Seeded {count} base models in offline mode")
        """
        logger.warning("Seeding in OFFLINE mode using fallback data")
        
        fallback_models = load_base_models_fallback()
        added_count = 0
        
        for model_data in fallback_models:
            # Dedup by resolved (stable) link, not the slug-derived display name.
            quant_link = config.LLM_Engine.MODEL_MAPPING.get(model_data['link'])
            actual_link = quant_link or model_data['link']
            if self._link_exists(actual_link):
                logger.debug(f"Skipping existing model: {actual_link}")
                continue
            
            try:
                # Create model config from JSON data
                model_config = Model_Config(
                    name=model_data['name'],
                    link=model_data['link'],
                    model_type=model_data['type']
                )
                
                # Create LLM entity with fallback metadata
                llm = self._create_base_llm_from_json(model_data)
                self.db.add(llm)
                self.db.flush()
                added_count += 1
                logger.info(f"Added base model (offline): {model_data['name']}")
                
            except Exception as e:
                logger.error(f"Failed to add offline model {model_data['name']}: {e}")
                continue
        
        self.db.commit()
        logger.info(f"Offline seeding complete: {added_count} base models added")
        return added_count
    
    def _create_base_llm_from_json(self, model_data: Dict[str, Any]) -> Llm:
        """Create LLM entity from JSON fallback data.
        
        Args:
            model_data: Dictionary from fallback JSON with keys:
                name, link, type, param_size, model_metadata
        
        Returns:
            Llm: Entity ready to be added to database.
        """
        # Determine quantization
        quant_link = config.LLM_Engine.MODEL_MAPPING.get(model_data['link'])
        is_quantized = quant_link is not None
        actual_link = quant_link if is_quantized else model_data['link']
        
        # Use embedded metadata and param_size from JSON
        return Llm(
            name=humanize_model_name(model_data['link']),
            local=0,
            link=actual_link,
            type=model_data['type'],
            quantized=is_quantized,
            model_metadata=model_data['model_metadata'],
            param_size=model_data['param_size']
        )
    
    def seed_derived_models(
        self,
        searches: List[Search_Config],
        top_per_search: int = 30,
        max_checked: int = 200
    ) -> int:
        """Seed derived models from HuggingFace search results.
        
        Args:
            searches: List of search configurations.
            top_per_search: Maximum models to add per search.
            max_checked: Maximum models to check per search.
        
        Returns:
            Total number of models successfully added.
        """
        total_added = 0
        
        for search_config in searches:
            added = self._seed_from_search(
                search_config,
                top_per_search,
                max_checked
            )
            total_added += added
            self.db.commit()
        
        return total_added
    
    def _model_exists(self, name: str) -> bool:
        """Check if model already exists by name."""
        return self.db.query(Llm).filter(Llm.name == name).first() is not None
    
    def _link_exists(self, link: str) -> bool:
        """Check if model already exists by link."""
        return self.db.query(Llm).filter(Llm.link == link).first() is not None
    
    def _create_base_llm(self, model_config: Model_Config) -> Llm:
        """Create base LLM entity with full metadata."""
        # Determine quantization
        quant_link = config.LLM_Engine.MODEL_MAPPING.get(model_config.link)
        is_quantized = quant_link is not None
        actual_link = quant_link if is_quantized else model_config.link
        
        # Fetch metadata
        model_info = self.hf_api.model_info(model_config.link)
        
        # Calculate size
        if is_quantized:
            size_estimate = get_disk_size_after_quant(quant_link)
        else:
            size_estimate = get_model_size_estimate(
                model_config.name,
                model_config.link
            )
        
        # Extract parameters
        param_size = self._extract_param_size(
            model_config.name,
            model_config.link
        )
        
        # Format metadata
        metadata = format_model_info_metadata(
            model_info,
            size_estimate,
            is_quantized
        )
        
        return Llm(
            name=humanize_model_name(model_config.link),
            local=0,
            link=actual_link,
            type=model_config.model_type,
            quantized=is_quantized,
            model_metadata=metadata,
            param_size=param_size,
            # Pre-download tool-calling detection from the HF chat template (#86):
            # lets the catalog recommend agentic models before they are downloaded.
            supports_tools=tool_capability_from_hf_repo(actual_link),
        )
    
    def _create_base_llm_fallback(self, model_config: Model_Config) -> Llm:
        """Create base LLM with fallback metadata (no HF API call)."""
        quant_link = config.LLM_Engine.MODEL_MAPPING.get(model_config.link)
        is_quantized = quant_link is not None
        actual_link = quant_link if is_quantized else model_config.link
        
        if is_quantized:
            size_estimate = get_disk_size_after_quant(quant_link)
        else:
            size_estimate = get_model_size_estimate(
                model_config.name,
                model_config.link
            )
        
        param_size = self._extract_param_size(
            model_config.name,
            model_config.link
        )
        
        fallback_metadata = (
            f"Size: {size_estimate.to_string()}\n"
            f"Model ID: {model_config.link}\n"
            f"Quantized: {is_quantized}\n"
            f"Author: Unknown\n"
            f"Library: Unknown"
        )
        
        return Llm(
            name=humanize_model_name(model_config.link),
            local=0,
            link=actual_link,
            type=model_config.model_type,
            quantized=is_quantized,
            model_metadata=fallback_metadata,
            param_size=param_size,
            supports_tools=tool_capability_from_hf_repo(actual_link),
        )
    
    def _extract_param_size(self, name: str, link: str) -> float:
        """Extract parameter size from model name/link."""
        param_count = extract_parameter_pattern(f"{name} {link}")
        
        if param_count:
            if param_count.scale == ParameterScale.BILLION:
                return param_count.count
            elif param_count.scale == ParameterScale.MILLION:
                return param_count.count / 1000.0
        
        # Fallback to 7B if extraction fails
        return 7.0
    
    def _seed_from_search(
        self,
        search_config: Search_Config,
        top_per_search: int,
        max_checked: int
    ) -> int:
        """Seed models from a single HuggingFace search."""
        logger.info(
            f"Searching HF for '{search_config.search_term}' "
            f"(top {top_per_search})..."
        )
        
        added_count = 0
        checked_count = 0
        
        results = self.hf_api.list_models(
            search=search_config.search_term,
            sort="downloads",
        )
        
        for model_info in results:
            if added_count >= top_per_search:
                break
            if checked_count >= max_checked:
                break
            
            checked_count += 1
            
            # Apply filters
            if not self._passes_quality_filters(model_info):
                continue
            
            if self._link_exists(model_info.modelId):
                continue
            
            # Create derived model
            try:
                llm = self._create_derived_llm(model_info, search_config)
                self.db.add(llm)
                self.db.flush()
                added_count += 1
                logger.info(
                    f"  Added {model_info.modelId.split('/')[-1]} "
                    f"({added_count}/{top_per_search}) - "
                    f"{model_info.downloads} downloads, {model_info.likes} likes"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to add {model_info.modelId}: {e}",
                    exc_info=True
                )
                continue
        
        logger.info(
            f"Completed search for '{search_config.search_term}': "
            f"added {added_count}/{checked_count} checked"
        )
        
        return added_count
    
    def _passes_quality_filters(self, model_info) -> bool:
        """Check if model passes quality filters."""
        # Download/like thresholds
        if (model_info.downloads < self.filters.min_downloads or
            model_info.likes < self.filters.min_likes):
            return False
        
        # Skip IDs and terms
        model_id_lower = model_info.modelId.lower()
        model_name_lower = model_id_lower.split("/")[-1]
        
        if model_name_lower in self.filters.skip_ids:
            return False
        
        if any(term in model_id_lower for term in self.filters.skip_terms):
            return False
        
        # Interesting tags
        if model_info.tags:
            if any(tag in self.filters.interesting_tags for tag in model_info.tags):
                return True
        
        # Quality keywords
        if any(kw in model_id_lower for kw in self.filters.quality_keywords):
            return True
        
        return False
    
    def _create_derived_llm(self, model_info, search_config: Search_Config) -> Llm:
        """Create derived LLM entity from search result."""
        model_name = model_info.modelId.split("/")[-1]
        
        # Estimate size
        size_estimate = get_model_size_estimate(model_name, model_info.modelId)
        
        # Extract parameters
        param_count = extract_parameter_pattern(model_info.modelId)
        if param_count:
            if param_count.scale == ParameterScale.BILLION:
                param_size = param_count.count
            elif param_count.scale == ParameterScale.MILLION:
                param_size = param_count.count / 1000.0
            else:
                param_size = search_config.default_param_size
        else:
            param_size = search_config.default_param_size
        
        # Format metadata
        metadata = format_model_info_metadata(
            model_info,
            size_estimate,
            quantized=False
        )
        
        return Llm(
            name=humanize_model_name(model_info.modelId),
            local=0,
            link=model_info.modelId,
            type=search_config.model_type,
            quantized=False,
            model_metadata=metadata,
            param_size=param_size
        )


# ============ Job Cleanup Service ============

class Job_Cleanup_Service:
    """Handles cleanup of interrupted jobs and orphaned resources.
    
    Responsibilities:
    - Mark interrupted jobs (download, KB) as failed
    - Remove incomplete model files and temp directories
    - Cleanup orphaned model directories without database entries
    """
    
    def __init__(self, db: Session):
        """Initialize job cleanup service.
        
        Args:
            db: Active database session.
        """
        self.db = db
    
    def cleanup_all_unfinished_jobs(self) -> Dict[str, int]:
        """Mark all interrupted jobs as failed and cleanup resources.
        
        Returns:
            Dictionary with counts: {"download": N, "kb": N, "orphaned": N}
        """
        counts = {
            "download": self._cleanup_download_jobs(),
            "kb": self._cleanup_kb_jobs(),
            "orphaned": self._cleanup_orphaned_models()
        }

        total = sum(counts.values())
        if total > 0:
            logger.info(
                f"Cleaned up {total} unfinished jobs: "
                f"download={counts['download']}, "
                f"kb={counts['kb']}, "
                f"orphaned={counts['orphaned']}"
            )
        
        return counts
    
    def _cleanup_download_jobs(self) -> int:
        """Cleanup interrupted download jobs."""
        unfinished = self.db.query(DownloadJobModel).filter(
            DownloadJobModel.status.in_(["running", "pending"])
        ).all()
        
        count = 0
        for job in unfinished:
            try:
                # Delete incomplete model files
                llm = self.db.query(Llm).filter(Llm.id == job.local_model_id).first()
                if llm and os.path.exists(llm.link):
                    shutil.rmtree(llm.link, ignore_errors=True)
                    self.db.delete(llm)
                
                # Delete temp files
                if job.temp_local_model_link and os.path.exists(job.temp_local_model_link):
                    shutil.rmtree(job.temp_local_model_link, ignore_errors=True)
                
                # Mark as failed. The temp Llm delete above nulls
                # local_model_id server-side (FK SET NULL); updated_at is
                # stamped by onupdate=func.now().
                job.status = "failed"
                job.error_message = (
                    "Download interrupted due to application shutdown"
                )
                job.temp_local_model_link = ""

                count += 1
            except FileSystemException as e:
                logger.error(f"Filesystem error cleaning download job {job.id}: {e}")
                continue
            except DatabaseException as e:
                logger.error(f"Database error cleaning download job {job.id}: {e}")
                continue
        
        if count > 0:
            self.db.commit()
        
        return count
    
    def _cleanup_kb_jobs(self) -> int:
        """Cleanup interrupted knowledge base jobs.

        Creation jobs are rolled back: the specialized LLM and the KB are
        deleted (KnowledgeDocument rows follow through ON DELETE CASCADE, the
        job's refs are nulled server-side by the FKs). Update jobs
        (new_model_id == base_model_id) leave the existing KB and assistant
        untouched — the corpus indexed before the interruption is still valid.
        """
        unfinished = self.db.query(KBJobModel).filter(
            KBJobModel.status.in_(["running", "pending"])
        ).all()

        count = 0
        for job in unfinished:
            try:
                is_update = job.new_model_id == job.base_model_id

                if not is_update:
                    new_llm = self.db.query(Llm).filter(Llm.id == job.new_model_id).first()
                    if new_llm:
                        self.db.delete(new_llm)

                    kb = self.db.query(KnowledgeBase).filter(
                        KnowledgeBase.id == job.kb_id
                    ).first()
                    if kb:
                        self.db.delete(kb)

                job.status = "failed"
                job.error_message = (
                    "KB update interrupted due to application shutdown"
                    if is_update
                    else "KB creation interrupted due to application shutdown"
                )

                count += 1
            except Exception as e:
                logger.error(f"Error cleaning KB job {job.id}: {e}")
                continue

        if count > 0:
            self.db.commit()

        return count
    
    def _cleanup_orphaned_models(self) -> int:
        """Cleanup orphaned model files without corresponding database entries.
        
        This handles cases where:
        - The app is reinstalled but Application Support data persists
        - Temp directories from interrupted downloads remain
        
        Returns:
            Total count of orphaned models and temp directories removed.
        
        Raises:
            FileSystemException: If critical filesystem operations fail.
        """
        models_dir = config.LLM_DIR
        
        # Return early if models directory doesn't exist
        if not models_dir.exists():
            logger.debug("Models directory doesn't exist, nothing to clean up")
            return 0
        
        # Get all valid model IDs from database
        try:
            local_models = self.db.query(Llm).filter(Llm.local == 1).all()
            valid_model_ids = {str(model.id) for model in local_models}
        except DatabaseException as e:
            logger.error(f"Database error fetching local models: {e}")
            return 0
        
        # Scan and cleanup orphaned directories
        cleaned_count = 0
        temp_cleaned_count = 0
        
        try:
            for item in models_dir.iterdir():
                if not item.is_dir():
                    continue
                
                dir_name = item.name
                
                # Cleanup temp directories (they start with "temp_")
                if dir_name.startswith("temp_"):
                    logger.info(f"Removing temporary model directory: {dir_name}")
                    try:
                        shutil.rmtree(item, ignore_errors=True)
                        temp_cleaned_count += 1
                    except Exception as e:
                        logger.error(f"Failed to remove temp model {dir_name}: {e}")
                    continue
                
                # Cleanup orphaned model directories
                if dir_name not in valid_model_ids:
                    logger.info(f"Removing orphaned model directory: {dir_name}")
                    try:
                        shutil.rmtree(item, ignore_errors=True)
                        cleaned_count += 1
                    except Exception as e:
                        logger.error(f"Failed to remove orphaned model {dir_name}: {e}")
            
            total_cleaned = cleaned_count + temp_cleaned_count
            if total_cleaned > 0:
                logger.info(
                    f"Cleaned up {cleaned_count} orphaned model(s) and "
                    f"{temp_cleaned_count} temp directory(ies)"
                )
            else:
                logger.debug("No orphaned models or temp directories found")
            
            return total_cleaned
            
        except FileSystemException as e:
            logger.error(f"Filesystem error during orphaned model cleanup: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during orphaned model cleanup: {e}")
            return cleaned_count + temp_cleaned_count


# ============ Hardware Initialization Service ============

class Hardware_Initializer:
    """Handles system hardware profiling and persistence."""
    
    def __init__(self, db: Session):
        """Initialize hardware initializer.
        
        Args:
            db: Active database session.
        """
        self.db = db
        self.service = Hardware_Service(Hardware_Repository(db))
    
    def initialize_if_needed(self) -> bool:
        """Initialize hardware info if not already present.
        
        Uses service layer to get or create hardware profile.
        
        Returns:
            True if initialization was performed, False if already existed.
        """
        try:
            existing = self.db.query(HardwareProfile).first()
            if existing:
                logger.debug("Hardware info already initialized, skipping")
                return False
            
            # Use service to get or create profile
            profile = self.service.get_or_create_profile()
            self.db.commit()
            
            logger.info(f"Hardware info initialized: backend={profile.backend_type}")
            return True
            
        except Exception as e:
            logger.exception(f"Hardware initialization failed: {e}")
            self.db.rollback()
            # Create fallback profile on error
            self._create_fallback_profile()
            return True
    
    def _create_fallback_profile(self) -> None:
        """Create fallback hardware profile on initialization failure."""
        try:
            fallback_data = {
                "backend_type": "cpu",
                "cpu_model": "Unknown CPU",
                "total_memory_gb": 8.0,
                "available_memory_gb": 4.0,
                "disk_total_gb": 100.0,
                "disk_available_gb": 50.0,
                "global_inference_score": 20.0,
                "global_inference_label": "Poor",
                "global_finetuning_score": 15.0,
                "global_finetuning_label": "Poor",
                "cpu_score": 30.0,
                "memory_score": 25.0,
                "system_platform": "Unknown"
            }
            
            profile = HardwareProfile(**fallback_data)
            self.db.add(profile)
            self.db.commit()
            logger.warning("Fallback hardware profile created")
            
        except Exception as e:
            logger.exception(f"Failed to create fallback profile: {e}")
            self.db.rollback()


# ============ Startup Variables Initialization ============

class Startup_Initializer:
    """Handles initialization of startup state variables."""
    
    def __init__(self, db: Session):
        """Initialize startup initializer.
        
        Args:
            db: Active database session.
        """
        self.db = db
    
    def initialize_if_needed(self) -> bool:
        """Initialize startup variables if not already present.
        
        Returns:
            True if initialization was performed, False if already existed.
        """
        existing = self.db.query(StartupVariables).first()
        if existing:
            logger.debug("Startup variables already initialized, skipping")
            return False
        
        variables = StartupVariables(
            welcome_popup_has_already_displayed=False
        )
        self.db.add(variables)
        self.db.commit()
        logger.info("Startup variables initialized successfully")
        return True


# ============ Main Database Seeder (Facade) ============

class Database_Seeder:
    """Facade for all database seeding operations.
    
    Provides a simple, high-level API for database initialization
    while maintaining clean separation of concerns internally.
    
    Example:
        ::

            seeder = Database_Seeder()
            await seeder.create_tables()
            await seeder.populate_startup_data()
    """
    
    # Default base models
    DEFAULT_BASE_MODELS = [
        Model_Config("Gemma-270M", "google/gemma-3-270m-it", "gemma"),
        Model_Config("Gemma-1B", "google/gemma-3-1b-it", "gemma"),
        Model_Config("Gemma-2B", "google/gemma-2-2b-it", "gemma"),
        Model_Config("Gemma-4B", "google/gemma-3-4b-it", "gemma"),
        Model_Config("Gemma-4-E2B", "google/gemma-4-E2B-it", "gemma"),
        Model_Config("Gemma-4-E4B", "google/gemma-4-E4B-it", "gemma"),
        Model_Config("Gemma-4-26B", "google/gemma-4-26b-a4b-it", "gemma"),
        Model_Config("Gemma-4-31B", "google/gemma-4-31b-it", "gemma"),
        Model_Config("Mistral-7B", "mistralai/Mistral-7B-Instruct-v0.3", "mistral"),
        Model_Config("Ministral-8B", "mistralai/Ministral-8B-Instruct-2410", "mistral"),
        Model_Config("Gemma-12B", "google/gemma-3-12b-it", "gemma"),
        Model_Config("Mistral-Nemo-12B", "mistralai/Mistral-Nemo-Instruct-2407", "mistral"),
    ]

    # Default derived model searches
    DEFAULT_SEARCH_CONFIGS = [
        Search_Config("Mistral-7B v0.3", "mistral", 7.0),
        Search_Config("Gemma 1B", "gemma", 1.0),
        Search_Config("Gemma 2B", "gemma", 2.0),
        Search_Config("Gemma 4B", "gemma", 4.0),
        Search_Config("gemma-4-e2b", "gemma", 2.0),
        Search_Config("gemma-4-e4b", "gemma", 4.0),
        Search_Config("gemma-4-26b-a4b", "gemma", 4.0),
        Search_Config("gemma-4-31b", "gemma", 31.0),
        Search_Config("Ministral-8B", "mistral", 8.0),
        Search_Config("Gemma 12B", "gemma", 12.0),
        Search_Config("Mistral-Nemo-12B", "mistral", 12.0),
    ]
    
    async def create_tables(self) -> None:
        """Create all database tables from SQLAlchemy models.

        Idempotent operation - safe to call multiple times. Requires
        init_database() to have run first. Anti-B1: reads the LIVE engine via
        attribute access — an imported-by-value `db_engine` would stay frozen
        at None forever.
        """
        if core.db_engine is None:
            raise RuntimeError(
                "Database not initialized: call init_database() before create_tables()"
            )
        try:
            # Create MISSING tables from the models. Schema EVOLUTION of an
            # existing (persisted) database is handled by Alembic at startup
            # (src.database.migrations.run_migrations), not here — this primitive
            # is the from-scratch creation used by tests and first boot.
            Base.metadata.create_all(bind=core.db_engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}", exc_info=True)
            raise
    
    async def populate_startup_data(
        self,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Populate database with startup data.
        
        Args:
            db: Optional database session. If None, creates new session.
        
        Returns:
            Dictionary with operation results and counts.
        
        Raises:
            Exception: If any critical seeding step fails.
        """
        should_close = db is None
        if db is None:
            db = SessionLocal()
        
        try:
            results = {
                "base_models_added": 0,
                "derived_models_added": 0,
                "jobs_cleaned": {},
                "hardware_initialized": False,
                "startup_vars_initialized": False,
                "offline_mode": False,
                "models_seeded": False
            }
            
            # Initialize startup variables first
            logger.info("Initializing startup variables...")
            startup_init = Startup_Initializer(db)
            results["startup_vars_initialized"] = startup_init.initialize_if_needed()
            
            # Get or create startup variables singleton
            startup_vars = db.query(StartupVariables).first()
            if not startup_vars:
                startup_vars = StartupVariables()
                db.add(startup_vars)
                db.commit()
                db.refresh(startup_vars)
            
            # Determine if we need to seed models
            needs_seeding = False
            if not startup_vars.models_seeded:
                needs_seeding = True
                logger.info("First-time seeding required (models_seeded=False)")
            elif startup_vars.last_seeded_at is None:
                needs_seeding = True
                logger.info("Seeding required (last_seeded_at is None)")
            else:
                # Local-time referential, consistent with the server-stamped
                # (func.now()) timestamps everywhere else in the schema.
                days_since_last_seed = (datetime.now() - startup_vars.last_seeded_at).days
                if days_since_last_seed >= 3:
                    needs_seeding = True
                    logger.info(f"Reseed required (last seeded {days_since_last_seed} days ago)")
                else:
                    logger.info(f"Skipping seed (last seeded {days_since_last_seed} days ago, threshold=3)")
            
            # Seed models if needed
            if needs_seeding:
                logger.info("Starting model seeding...")
                online_status = is_online()
                
                if online_status:
                    logger.info("Online mode: seeding from Hugging Face API")
                    model_seeder = Model_Seeder(db, get_hf_api(), offline_mode=False)
                    results["base_models_added"] = model_seeder.seed_base_models(
                        self.DEFAULT_BASE_MODELS
                    )
                    results["derived_models_added"] = model_seeder.seed_derived_models(
                        self.DEFAULT_SEARCH_CONFIGS,
                        top_per_search=30,
                        max_checked=200
                    )
                    results["offline_mode"] = False
                else:
                    logger.warning("Offline mode: seeding from fallback JSON (base models only)")
                    model_seeder = Model_Seeder(db, offline_mode=True)
                    results["base_models_added"] = model_seeder.seed_base_models_offline()
                    results["derived_models_added"] = 0  # Skip derived in offline mode
                    results["offline_mode"] = True
                
                # Update startup variables after successful seeding
                startup_vars.models_seeded = True
                startup_vars.last_seeded_at = datetime.now()
                startup_vars.offline_mode = results["offline_mode"]
                db.commit()
                results["models_seeded"] = True
            else:
                logger.info("Skipping model seeding (already seeded recently)")
                results["offline_mode"] = startup_vars.offline_mode
                results["models_seeded"] = False
            
            # Cleanup jobs (always run)
            logger.info("Cleaning up unfinished jobs...")
            job_cleanup = Job_Cleanup_Service(db)
            results["jobs_cleaned"] = job_cleanup.cleanup_all_unfinished_jobs()
            
            # Initialize hardware
            logger.info("Initializing hardware info...")
            hw_init = Hardware_Initializer(db)
            results["hardware_initialized"] = hw_init.initialize_if_needed()
            
            logger.info(
                f"Startup population completed: "
                f"base={results['base_models_added']}, "
                f"derived={results['derived_models_added']}, "
                f"jobs_cleaned={sum(results['jobs_cleaned'].values())}, "
                f"offline_mode={results['offline_mode']}, "
                f"models_seeded={results['models_seeded']}"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error during startup population: {e}", exc_info=True)
            db.rollback()
            raise
        finally:
            if should_close:
                db.close()
    
    async def delete_all_data(self) -> None:
        """Delete all data from database and file storage.
        
        **DESTRUCTIVE OPERATION - DEVELOPMENT ONLY**
        
        Requires interactive confirmation before proceeding.
        
        Warning:
            Never expose this in production. No undo available.
        """
        logger.warning("Preparing to delete all data from the database")
        response = input("Are you sure you want to delete ALL data? (yes/no): ")
        
        if response.lower() not in ("yes", "y"):
            logger.info("Database deletion cancelled")
            return
        
        db = SessionLocal()
        try:
            logger.warning("Deleting all data...")
            
            # Delete file storage
            self._delete_storage_directories()
            
            # Delete database records
            db.query(StartupVariables).delete()
            db.query(KBJobModel).delete()
            db.query(KnowledgeDocument).delete()
            db.query(KnowledgeBase).delete()
            db.query(HardwareProfile).delete()
            db.query(DownloadJobModel).delete()
            db.query(Message).delete()
            db.query(Conversation).delete()
            db.query(Llm).delete()
            
            db.commit()
            logger.warning("All data deleted successfully")
            
        except Exception as e:
            logger.error(f"Error deleting data: {e}", exc_info=True)
            db.rollback()
            raise
        finally:
            db.close()
    
    def _delete_storage_directories(self) -> None:
        """Delete and recreate storage directories."""
        directories = [str(config.LLM_DIR)]

        for directory in directories:
            if os.path.exists(directory):
                shutil.rmtree(directory)
            os.makedirs(directory, exist_ok=True)
            logger.debug(f"Recreated directory: {directory}")


# ============ Legacy API Compatibility ============

async def create_tables() -> None:
    """Legacy API: Create database tables.
    
    Deprecated: Use Database_Seeder().create_tables() instead.
    """
    seeder = Database_Seeder()
    await seeder.create_tables()


async def startup_populate_database() -> None:
    """Legacy API: Populate startup data.
    
    Deprecated: Use Database_Seeder().populate_startup_data() instead.
    """
    seeder = Database_Seeder()
    await seeder.populate_startup_data()


async def delete_all_data() -> None:
    """Legacy API: Delete all data.
    
    Deprecated: Use Database_Seeder().delete_all_data() instead.
    """
    seeder = Database_Seeder()
    await seeder.delete_all_data()
