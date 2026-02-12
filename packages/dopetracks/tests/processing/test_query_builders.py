"""
Tests for dopetracks.processing.imessage_data_processing.query_builders.

Covers:
- build_placeholders()
- messages_with_body_query()
- chat_stats_query() — including order_by allowlist validation
"""
import pytest

from dopetracks.processing.imessage_data_processing.query_builders import (
    build_placeholders,
    messages_with_body_query,
    chat_stats_query,
    _ALLOWED_ORDER_BY,
)


# ---------------------------------------------------------------------------
# build_placeholders
# ---------------------------------------------------------------------------


class TestBuildPlaceholders:
    """Tests for build_placeholders()."""

    def test_zero_count_returns_null(self):
        assert build_placeholders(0) == "NULL"

    def test_negative_count_returns_null(self):
        assert build_placeholders(-5) == "NULL"

    def test_single_placeholder(self):
        assert build_placeholders(1) == "?"

    def test_multiple_placeholders(self):
        result = build_placeholders(3)
        assert result == "?,?,?"

    def test_large_count(self):
        result = build_placeholders(100)
        assert result.count("?") == 100
        assert result.count(",") == 99


# ---------------------------------------------------------------------------
# messages_with_body_query
# ---------------------------------------------------------------------------


class TestMessagesWithBodyQuery:
    """Tests for messages_with_body_query()."""

    def test_query_contains_placeholders(self):
        query = messages_with_body_query("?,?,?")
        assert "?,?,?" in query

    def test_query_selects_expected_columns(self):
        query = messages_with_body_query("?")
        assert "message_id" in query
        assert "text" in query
        assert "attributedBody" in query
        assert "date_utc" in query
        assert "sender_contact" in query
        assert "chat_id" in query

    def test_query_filters_null_bodies(self):
        """Query should require either text or attributedBody to be non-null."""
        query = messages_with_body_query("?")
        assert "text IS NOT NULL" in query
        assert "attributedBody IS NOT NULL" in query

    def test_query_filters_reactions(self):
        """Query should exclude reaction messages (associated_message_type != 0)."""
        query = messages_with_body_query("?")
        assert "associated_message_type" in query

    def test_query_orders_by_date_desc(self):
        query = messages_with_body_query("?")
        assert "ORDER BY message.date DESC" in query

    def test_query_has_date_range_params(self):
        """Query should filter by date BETWEEN ? AND ?."""
        query = messages_with_body_query("?")
        assert "BETWEEN ? AND ?" in query


# ---------------------------------------------------------------------------
# chat_stats_query — order_by allowlist
# ---------------------------------------------------------------------------


class TestChatStatsQueryOrderBy:
    """Tests for chat_stats_query() order_by allowlist validation."""

    def test_default_order_by(self):
        query = chat_stats_query("?")
        assert "ORDER BY last_message_date DESC" in query

    def test_allowed_order_by_values(self):
        """Every value in _ALLOWED_ORDER_BY should be accepted."""
        for order in _ALLOWED_ORDER_BY:
            query = chat_stats_query("?", order_by=order)
            assert f"ORDER BY {order}" in query

    def test_disallowed_order_by_falls_back_to_default(self):
        """An invalid order_by should fall back to the default."""
        # Attempt SQL injection
        query = chat_stats_query("?", order_by="1; DROP TABLE chat;--")
        assert "DROP TABLE" not in query
        assert "ORDER BY last_message_date DESC" in query

    def test_arbitrary_sql_rejected(self):
        query = chat_stats_query("?", order_by="ROWID; DELETE FROM message")
        assert "DELETE" not in query
        assert "ORDER BY last_message_date DESC" in query

    def test_empty_string_order_by_falls_back(self):
        query = chat_stats_query("?", order_by="")
        assert "ORDER BY last_message_date DESC" in query

    def test_case_sensitivity(self):
        """Allowlist is case-sensitive; uppercase variant should be rejected."""
        query = chat_stats_query("?", order_by="LAST_MESSAGE_DATE DESC")
        assert "ORDER BY last_message_date DESC" in query


class TestChatStatsQueryStructure:
    """Tests for chat_stats_query() SQL structure."""

    def test_query_contains_placeholders(self):
        query = chat_stats_query("?,?,?")
        assert "?,?,?" in query

    def test_limit_clause_present_when_specified(self):
        query = chat_stats_query("?", limit=10)
        assert "LIMIT 10" in query

    def test_no_limit_when_none(self):
        query = chat_stats_query("?", limit=None)
        assert "LIMIT" not in query

    def test_limit_coerced_to_int(self):
        """Even if limit is passed as float, it should be coerced to int."""
        query = chat_stats_query("?", limit=10.5)
        assert "LIMIT 10" in query

    def test_query_groups_by_chat(self):
        query = chat_stats_query("?")
        assert "GROUP BY" in query

    def test_query_selects_aggregate_columns(self):
        query = chat_stats_query("?")
        assert "message_count" in query
        assert "member_count" in query
        assert "last_message_date" in query

    def test_query_has_having_clause(self):
        """Should exclude chats with zero messages."""
        query = chat_stats_query("?")
        assert "HAVING message_count > 0" in query
