"""URL extraction helpers for message text."""
from __future__ import annotations

import logging
import re
from typing import Dict, List

logger = logging.getLogger(__name__)


def extract_spotify_urls(text: str) -> List[str]:
    """Extract Spotify URLs from text using regex."""
    if not text:
        return []
    # Match both open.spotify.com and spotify.link URLs
    pattern = r"https?://(open\.spotify\.com|spotify\.link)/[^\s<>\"{}|\\^`\[\]]+"
    full_urls = []
    for match in re.finditer(pattern, text):
        full_urls.append(match.group(0))
    return full_urls


def extract_all_urls(text: str) -> List[Dict[str, str]]:
    """
    Extract all URLs from text and categorize them by type.
    Returns a list of dicts with 'url' and 'type' keys.
    """
    if not text:
        return []

    from urllib.parse import urlparse

    # More comprehensive URL pattern that handles:
    # - Standard URLs
    # - URLs with query parameters (?key=value)
    # - URLs with fragments (#section)
    # - URLs ending with punctuation (which we'll strip)
    # This pattern matches URLs until whitespace or common punctuation that typically ends a sentence
    url_pattern = r"https?://[^\s<>\"{}|\\^`\[\]]+"
    matches = list(re.finditer(url_pattern, text))

    categorized_urls = []
    for match in matches:
        url = match.group(0)
        # Strip trailing punctuation that might have been captured (but keep it if it's part of the URL)
        # Only strip if it's clearly sentence-ending punctuation
        url = url.rstrip(".,;!?)")

        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Helper function to check if domain matches (handles subdomains and avoids false positives)
            def domain_matches(domain_to_check, pattern):
                """Check if domain matches pattern, handling subdomains correctly."""
                # Remove 'www.' prefix if present
                domain_clean = domain_to_check.replace("www.", "")
                pattern_clean = pattern.replace("www.", "")

                # Check exact match or subdomain match (e.g., 'api.spotify.com' matches 'spotify.com')
                return (
                    domain_clean == pattern_clean
                    or domain_clean.endswith("." + pattern_clean)
                )

            # Categorize by domain (using precise matching to avoid false positives like 'dopdx.com' matching 'x.com')
            url_type = "other"
            if domain_matches(domain, "spotify.com") or domain_matches(domain, "spotify.link"):
                url_type = "spotify"
            elif domain_matches(domain, "youtube.com") or domain_matches(domain, "youtu.be"):
                url_type = "youtube"
            elif domain_matches(domain, "instagram.com") or domain_matches(domain, "instagr.am"):
                url_type = "instagram"
            elif domain_matches(domain, "music.apple.com") or domain_matches(domain, "itunes.apple.com"):
                url_type = "apple_music"
            elif domain_matches(domain, "tiktok.com"):
                url_type = "tiktok"
            elif domain_matches(domain, "twitter.com") or domain_matches(domain, "x.com"):
                url_type = "twitter"
            elif domain_matches(domain, "facebook.com") or domain_matches(domain, "fb.com"):
                url_type = "facebook"
            elif domain_matches(domain, "soundcloud.com"):
                url_type = "soundcloud"
            elif domain_matches(domain, "bandcamp.com"):
                url_type = "bandcamp"
            elif domain_matches(domain, "tidal.com"):
                url_type = "tidal"
            elif domain_matches(domain, "amazon.com") and (
                "music" in domain or "/music" in parsed.path
            ):
                url_type = "amazon_music"
            elif domain_matches(domain, "deezer.com"):
                url_type = "deezer"
            elif domain_matches(domain, "pandora.com"):
                url_type = "pandora"
            elif domain_matches(domain, "iheart.com"):
                url_type = "iheart"
            elif domain_matches(domain, "tunein.com"):
                url_type = "tunein"

            categorized_urls.append({"url": url, "type": url_type})
        except Exception as exc:
            # If URL parsing fails, still add it as "other" type
            logger.warning(f"Failed to parse URL: {url} - {exc}")
            categorized_urls.append({"url": url, "type": "other"})

    return categorized_urls
