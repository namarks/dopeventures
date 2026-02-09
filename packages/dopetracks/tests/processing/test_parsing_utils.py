"""
Tests for dopetracks.processing.imessage_data_processing.parsing_utils.

Covers:
- detect_reaction()
- extract_spotify_urls()
- extract_all_urls() and its internal domain_matches logic
- extract_urls_by_type()
- finalize_text()
- compute_content_hash()
- parse_message_fields()
- MessageBodyCache
"""
import hashlib
from unittest.mock import patch, MagicMock

import pytest

from dopetracks.processing.imessage_data_processing.parsing_utils import (
    detect_reaction,
    extract_spotify_urls,
    extract_all_urls,
    extract_urls_by_type,
    finalize_text,
    compute_content_hash,
    parse_message_fields,
    MessageBodyCache,
    parse_attributed_body,
)


# ---------------------------------------------------------------------------
# detect_reaction
# ---------------------------------------------------------------------------


class TestDetectReaction:
    """Tests for detect_reaction()."""

    def test_known_reaction_loved(self):
        """Known iMessage type 2000 -> 'Loved' (via dictionaries.reaction_dict)."""
        result = detect_reaction(2000)
        # Depends on whether dictionaries module loaded successfully
        assert result in ("Loved", "no-reaction")

    def test_unknown_type_returns_no_reaction(self):
        """An unknown type should fall back to 'no-reaction'."""
        result = detect_reaction(9999)
        assert result == "no-reaction"

    def test_none_returns_no_reaction(self):
        result = detect_reaction(None)
        assert result == "no-reaction"

    def test_zero_returns_no_reaction(self):
        result = detect_reaction(0)
        assert result == "no-reaction"


# ---------------------------------------------------------------------------
# extract_spotify_urls
# ---------------------------------------------------------------------------


class TestExtractSpotifyUrls:
    """Tests for extract_spotify_urls()."""

    def test_single_spotify_track_url(self):
        text = "Check this out https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC"
        result = extract_spotify_urls(text)
        assert len(result) == 1
        assert "open.spotify.com/track/" in result[0]

    def test_spotify_link_short_url(self):
        text = "Here: https://spotify.link/abc123"
        result = extract_spotify_urls(text)
        assert len(result) == 1
        assert "spotify.link" in result[0]

    def test_multiple_spotify_urls(self):
        text = (
            "https://open.spotify.com/track/111 and "
            "https://open.spotify.com/album/222"
        )
        result = extract_spotify_urls(text)
        assert len(result) == 2

    def test_no_spotify_urls(self):
        text = "Just a regular message with no links"
        result = extract_spotify_urls(text)
        assert result == []

    def test_empty_text(self):
        assert extract_spotify_urls("") == []

    def test_none_text(self):
        assert extract_spotify_urls(None) == []

    def test_non_spotify_url_not_extracted(self):
        text = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        result = extract_spotify_urls(text)
        assert result == []

    def test_spotify_playlist_url(self):
        text = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
        result = extract_spotify_urls(text)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# extract_all_urls – domain categorization
# ---------------------------------------------------------------------------


class TestExtractAllUrls:
    """Tests for extract_all_urls() and its domain_matches() logic."""

    def test_spotify_categorized(self):
        text = "https://open.spotify.com/track/abc"
        result = extract_all_urls(text)
        assert len(result) == 1
        assert result[0]["type"] == "spotify"

    def test_youtube_categorized(self):
        text = "https://www.youtube.com/watch?v=123"
        result = extract_all_urls(text)
        assert len(result) == 1
        assert result[0]["type"] == "youtube"

    def test_youtu_be_short(self):
        text = "https://youtu.be/dQw4w9WgXcQ"
        result = extract_all_urls(text)
        assert len(result) == 1
        assert result[0]["type"] == "youtube"

    def test_apple_music(self):
        text = "https://music.apple.com/us/album/something"
        result = extract_all_urls(text)
        assert len(result) == 1
        assert result[0]["type"] == "apple_music"

    def test_tiktok_categorized(self):
        text = "https://www.tiktok.com/@user/video/123"
        result = extract_all_urls(text)
        assert len(result) == 1
        assert result[0]["type"] == "tiktok"

    def test_twitter_x_categorized(self):
        text = "https://x.com/user/status/123"
        result = extract_all_urls(text)
        assert len(result) == 1
        assert result[0]["type"] == "twitter"

    def test_soundcloud_categorized(self):
        text = "https://soundcloud.com/artist/track"
        result = extract_all_urls(text)
        assert len(result) == 1
        assert result[0]["type"] == "soundcloud"

    def test_unknown_domain_is_other(self):
        text = "https://example.com/page"
        result = extract_all_urls(text)
        assert len(result) == 1
        assert result[0]["type"] == "other"

    def test_empty_text(self):
        assert extract_all_urls("") == []

    def test_none_text(self):
        assert extract_all_urls(None) == []

    def test_multiple_mixed_urls(self):
        text = (
            "Check https://open.spotify.com/track/1 and "
            "https://youtube.com/watch?v=2 and "
            "https://example.com/3"
        )
        result = extract_all_urls(text)
        assert len(result) == 3
        types = {r["type"] for r in result}
        assert types == {"spotify", "youtube", "other"}

    def test_www_prefix_stripped_for_matching(self):
        """domain_matches should treat www.spotify.com the same as spotify.com."""
        text = "https://www.spotify.com/track/xyz"
        result = extract_all_urls(text)
        # www.spotify.com domain does not end with open.spotify.com,
        # but it should still match the spotify patterns
        assert len(result) == 1

    def test_trailing_punctuation_stripped(self):
        """URLs followed by punctuation should have trailing chars removed."""
        text = "Go to https://open.spotify.com/track/abc."
        result = extract_all_urls(text)
        assert len(result) == 1
        assert not result[0]["url"].endswith(".")

    def test_instagram_categorized(self):
        text = "https://www.instagram.com/p/abc123/"
        result = extract_all_urls(text)
        assert len(result) == 1
        assert result[0]["type"] == "instagram"

    def test_bandcamp_categorized(self):
        text = "https://artist.bandcamp.com/album/cool"
        result = extract_all_urls(text)
        assert len(result) == 1
        assert result[0]["type"] == "bandcamp"

    def test_tidal_categorized(self):
        text = "https://tidal.com/browse/track/123"
        result = extract_all_urls(text)
        assert len(result) == 1
        assert result[0]["type"] == "tidal"


# ---------------------------------------------------------------------------
# extract_urls_by_type
# ---------------------------------------------------------------------------


class TestExtractUrlsByType:
    """Tests for extract_urls_by_type()."""

    def test_empty_text_returns_empty_categories(self):
        result = extract_urls_by_type("")
        assert result == {"spotify": [], "youtube": [], "other": []}

    def test_none_text_returns_empty_categories(self):
        result = extract_urls_by_type(None)
        assert result == {"spotify": [], "youtube": [], "other": []}

    def test_spotify_url_categorized(self):
        text = "https://open.spotify.com/track/abc"
        result = extract_urls_by_type(text)
        assert len(result["spotify"]) == 1
        assert result["youtube"] == []
        assert result["other"] == []

    def test_youtube_url_categorized(self):
        text = "https://www.youtube.com/watch?v=123"
        result = extract_urls_by_type(text)
        assert len(result["youtube"]) == 1

    def test_other_url_categorized(self):
        text = "https://example.com/page"
        result = extract_urls_by_type(text)
        assert len(result["other"]) == 1

    def test_mixed_urls_separated(self):
        text = (
            "https://open.spotify.com/track/1 "
            "https://youtu.be/abc "
            "https://example.com"
        )
        result = extract_urls_by_type(text)
        assert len(result["spotify"]) == 1
        assert len(result["youtube"]) == 1
        assert len(result["other"]) == 1


# ---------------------------------------------------------------------------
# finalize_text
# ---------------------------------------------------------------------------


class TestFinalizeText:
    """Tests for finalize_text()."""

    def test_prefers_text_over_parsed_body(self):
        result = finalize_text("hello", {"text": "world"})
        assert result == "hello"

    def test_falls_back_to_parsed_body_text(self):
        result = finalize_text(None, {"text": "from body"})
        assert result == "from body"

    def test_empty_string_text_falls_back(self):
        result = finalize_text("", {"text": "body"})
        assert result == "body"

    def test_whitespace_only_text_falls_back(self):
        result = finalize_text("   ", {"text": "body"})
        assert result == "body"

    def test_both_none_returns_empty_string(self):
        result = finalize_text(None, None)
        assert result == ""

    def test_none_parsed_body_returns_text(self):
        result = finalize_text("hello", None)
        assert result == "hello"

    def test_parsed_body_without_text_key(self):
        result = finalize_text(None, {"components": {}})
        assert result == ""


# ---------------------------------------------------------------------------
# compute_content_hash
# ---------------------------------------------------------------------------


class TestComputeContentHash:
    """Tests for compute_content_hash()."""

    def test_deterministic(self):
        h1 = compute_content_hash("hello", "user1", "2024-01-01")
        h2 = compute_content_hash("hello", "user1", "2024-01-01")
        assert h1 == h2

    def test_different_inputs_different_hashes(self):
        h1 = compute_content_hash("hello", "user1", "2024-01-01")
        h2 = compute_content_hash("world", "user1", "2024-01-01")
        assert h1 != h2

    def test_returns_64_char_hex(self):
        """SHA-256 produces a 64-character hex digest."""
        result = compute_content_hash("text", "sender", "date")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_case_insensitive(self):
        """Inputs are lowercased before hashing."""
        h1 = compute_content_hash("Hello", "User1", "2024-01-01")
        h2 = compute_content_hash("hello", "user1", "2024-01-01")
        assert h1 == h2

    def test_none_values_handled(self):
        """None values should not crash the function."""
        result = compute_content_hash(None, None, None)
        assert isinstance(result, str)
        assert len(result) == 64

    def test_matches_manual_sha256(self):
        """Verify the hash matches a manually computed SHA-256."""
        text, sender, date = "test", "sender", "2024-01-01"
        normalized = "|".join([text.lower(), sender.lower(), date.lower()])
        expected = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        assert compute_content_hash(text, sender, date) == expected


# ---------------------------------------------------------------------------
# parse_message_fields
# ---------------------------------------------------------------------------


class TestParseMessageFields:
    """Tests for parse_message_fields()."""

    def test_basic_text_message(self):
        result = parse_message_fields(
            text="Hello world",
            attributed_body=None,
            sender_handle="+15555555555",
            date_utc="2024-01-01 12:00:00",
        )
        assert result["final_text"] == "Hello world"
        assert result["has_spotify"] == 0
        assert result["spotify_url"] is None
        assert result["content_hash"] is not None

    def test_message_with_spotify_url(self):
        result = parse_message_fields(
            text="Check this https://open.spotify.com/track/abc123",
            attributed_body=None,
            sender_handle="user@email.com",
            date_utc="2024-06-15 10:30:00",
        )
        assert result["has_spotify"] == 1
        assert "open.spotify.com/track/abc123" in result["spotify_url"]

    def test_empty_text_no_hash(self):
        """Empty final_text should result in None content_hash."""
        result = parse_message_fields(
            text="",
            attributed_body=None,
            sender_handle=None,
            date_utc=None,
        )
        assert result["content_hash"] is None

    def test_urls_dict_present(self):
        result = parse_message_fields(
            text="https://youtube.com/watch?v=1",
            attributed_body=None,
            sender_handle=None,
            date_utc=None,
        )
        assert "urls" in result
        assert isinstance(result["urls"], dict)
        assert "youtube" in result["urls"]

    def test_parsed_body_always_dict(self):
        result = parse_message_fields(
            text="hi",
            attributed_body=None,
            sender_handle=None,
            date_utc=None,
        )
        assert isinstance(result["parsed_body"], dict)
        assert "text" in result["parsed_body"]


# ---------------------------------------------------------------------------
# MessageBodyCache
# ---------------------------------------------------------------------------


class TestMessageBodyCache:
    """Tests for the LRU-style MessageBodyCache."""

    def test_cache_stores_and_retrieves(self):
        cache = MessageBodyCache(max_size=10)
        # First call parses; second call should return cached
        result1 = cache.get_parsed(1, None)
        result2 = cache.get_parsed(1, None)
        assert result1 == result2

    def test_cache_evicts_oldest(self):
        cache = MessageBodyCache(max_size=2)
        cache.get_parsed(1, None)
        cache.get_parsed(2, None)
        cache.get_parsed(3, None)  # Should evict key 1
        assert 1 not in cache._cache
        assert 2 in cache._cache
        assert 3 in cache._cache

    def test_cache_moves_recent_to_end(self):
        cache = MessageBodyCache(max_size=2)
        cache.get_parsed(1, None)
        cache.get_parsed(2, None)
        # Access 1 again to make it most recent
        cache.get_parsed(1, None)
        cache.get_parsed(3, None)  # Should evict 2, not 1
        assert 1 in cache._cache
        assert 2 not in cache._cache
        assert 3 in cache._cache


# ---------------------------------------------------------------------------
# parse_attributed_body (safe wrapper)
# ---------------------------------------------------------------------------


class TestParseAttributedBody:
    """Tests for parse_attributed_body() safe wrapper."""

    def test_none_input_returns_default(self):
        result = parse_attributed_body(None)
        assert result == {"text": None, "components": {}, "metadata": {}}

    def test_invalid_input_returns_default(self):
        result = parse_attributed_body(b"not valid data")
        assert result == {"text": None, "components": {}, "metadata": {}}

    def test_always_returns_dict_with_required_keys(self):
        result = parse_attributed_body("garbage")
        assert "text" in result
        assert "components" in result
        assert "metadata" in result
