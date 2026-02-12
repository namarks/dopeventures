"""
Tests for dopetracks.processing.imessage_data_processing.handle_utils.

Covers:
- normalize_handle() — phone and email normalization
- normalize_handle_variants() — variant generation for lookups
"""
import pytest

from dopetracks.processing.imessage_data_processing.handle_utils import (
    normalize_handle,
    normalize_handle_variants,
)


# ---------------------------------------------------------------------------
# normalize_handle
# ---------------------------------------------------------------------------


class TestNormalizeHandle:
    """Tests for normalize_handle()."""

    def test_none_returns_none(self):
        assert normalize_handle(None) is None

    def test_empty_string_returns_none(self):
        assert normalize_handle("") is None

    def test_email_lowercased(self):
        assert normalize_handle("User@Example.COM") == "user@example.com"

    def test_phone_digits_only(self):
        assert normalize_handle("+1 (555) 123-4567") == "5551234567"

    def test_phone_strips_leading_one(self):
        """11-digit US phone starting with 1 should drop the leading 1."""
        assert normalize_handle("+15551234567") == "5551234567"

    def test_ten_digit_phone_unchanged(self):
        assert normalize_handle("5551234567") == "5551234567"

    def test_short_phone_kept(self):
        """Phones with fewer than 10 digits are kept as-is (digits only)."""
        assert normalize_handle("12345") == "12345"

    def test_whitespace_stripped(self):
        assert normalize_handle("  user@test.com  ") == "user@test.com"

    def test_international_number(self):
        """International numbers with country codes > 1 digit."""
        result = normalize_handle("+44 7911 123456")
        # 12 digits starting with 44 → strip leading 4? No: only strips leading 1.
        assert result == "447911123456"

    def test_non_string_input(self):
        """Should handle non-string gracefully via str() conversion."""
        result = normalize_handle(5551234567)
        assert result == "5551234567"


# ---------------------------------------------------------------------------
# normalize_handle_variants
# ---------------------------------------------------------------------------


class TestNormalizeHandleVariants:
    """Tests for normalize_handle_variants()."""

    def test_none_returns_empty_list(self):
        assert normalize_handle_variants(None) == []

    def test_empty_string_returns_empty_list(self):
        assert normalize_handle_variants("") == []

    def test_email_returns_raw_and_lowered(self):
        variants = normalize_handle_variants("User@Example.COM")
        assert "User@Example.COM" in variants
        assert "user@example.com" in variants

    def test_email_already_lowercase_no_duplicate(self):
        variants = normalize_handle_variants("user@test.com")
        # Should not have duplicates
        assert len(variants) == len(set(variants))

    def test_phone_10_digits(self):
        variants = normalize_handle_variants("5551234567")
        assert "5551234567" in variants
        assert "+15551234567" in variants

    def test_phone_with_plus_one(self):
        variants = normalize_handle_variants("+15551234567")
        assert "+15551234567" in variants  # raw
        assert "15551234567" in variants  # digits-only
        assert "5551234567" in variants  # last 10

    def test_international_number_variants(self):
        variants = normalize_handle_variants("+447911123456")
        assert "+447911123456" in variants  # raw
        assert "447911123456" in variants  # digits
        assert "7911123456" in variants  # last 10

    def test_all_variants_unique(self):
        """No duplicates in the output."""
        variants = normalize_handle_variants("+15551234567")
        assert len(variants) == len(set(variants))

    def test_preserves_order(self):
        """Raw value should always come first."""
        variants = normalize_handle_variants("+15551234567")
        assert variants[0] == "+15551234567"
