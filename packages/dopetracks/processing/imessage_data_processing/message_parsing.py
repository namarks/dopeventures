"""Helpers for parsing Messages text content."""
from __future__ import annotations

from typing import Any

import pandas as pd

from . import parsing_utils as pu

_MESSAGE_TEXT_CACHE: dict[int, str] = {}
_MAX_CACHE = 5000


def _parse_body_cached(body: Any, msg_id: int) -> str:
    if msg_id in _MESSAGE_TEXT_CACHE:
        return _MESSAGE_TEXT_CACHE[msg_id]
    parsed = pu.parse_attributed_body(body)
    if len(_MESSAGE_TEXT_CACHE) > _MAX_CACHE:
        _MESSAGE_TEXT_CACHE.pop(next(iter(_MESSAGE_TEXT_CACHE)))
    _MESSAGE_TEXT_CACHE[msg_id] = parsed
    return parsed


def add_parsed_text_columns(
    df: pd.DataFrame,
    *,
    use_cache: bool = False,
    message_id_column: str = "message_id",
) -> pd.DataFrame:
    """Add parsed_body and final_text columns to a dataframe of messages."""
    if use_cache and message_id_column in df.columns:
        df["parsed_body"] = [
            _parse_body_cached(body, msg_id)
            for body, msg_id in zip(df["attributedBody"], df[message_id_column])
        ]
    else:
        df["parsed_body"] = df["attributedBody"].apply(pu.parse_attributed_body)

    df["final_text"] = df.apply(
        lambda row: pu.finalize_text(row["text"], row["parsed_body"]),
        axis=1,
    )
    return df
