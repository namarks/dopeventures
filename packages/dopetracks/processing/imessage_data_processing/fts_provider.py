"""Optional FTS indexer integration."""
from __future__ import annotations

import importlib
import importlib.util
from typing import Optional

import pandas as pd

FTS_MODULE = "dopetracks.processing.imessage_data_processing.fts_indexer"
_FTS_MODULE = None
_FTS_LOADED = False


def _load_fts_module():
    global _FTS_MODULE
    global _FTS_LOADED
    if _FTS_LOADED:
        return _FTS_MODULE
    _FTS_LOADED = True
    spec = importlib.util.find_spec(FTS_MODULE)
    if spec is None:
        _FTS_MODULE = None
        return None
    _FTS_MODULE = importlib.import_module(FTS_MODULE)
    return _FTS_MODULE


def is_available() -> bool:
    return _load_fts_module() is not None


def get_fts_db_path(source_db_path: str) -> Optional[str]:
    module = _load_fts_module()
    if module is None:
        return None
    return module.get_fts_db_path(source_db_path)


def is_fts_available(fts_db_path: str) -> bool:
    module = _load_fts_module()
    if module is None:
        return False
    return module.is_fts_available(fts_db_path)


def search_fts(
    fts_db_path: str,
    search_term: str,
    chat_ids: list[int],
    start_date: Optional[str] = None,
    end_date: Optional[int] = None,
    limit: int = 10000,
) -> pd.DataFrame:
    module = _load_fts_module()
    if module is None:
        return pd.DataFrame()
    return module.search_fts(
        fts_db_path=fts_db_path,
        search_term=search_term,
        chat_ids=chat_ids,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )


def populate_fts_database(
    fts_db_path: str,
    source_db_path: str,
    batch_size: int = 1000,
    force_rebuild: bool = False,
):
    module = _load_fts_module()
    if module is None:
        return {
            "total_processed": 0,
            "total_indexed": 0,
            "errors": 0,
            "duration": 0,
        }
    return module.populate_fts_database(
        fts_db_path=fts_db_path,
        source_db_path=source_db_path,
        batch_size=batch_size,
        force_rebuild=force_rebuild,
    )
