import hashlib
import re
from collections import OrderedDict
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from . import data_enrichment as de


class MessageBodyCache:
    """Simple LRU cache for parsed attributedBody payloads keyed by message id."""

    def __init__(self, max_size: int = 5000):
        self.max_size = max_size
        self._cache: OrderedDict[int, Dict[str, Any]] = OrderedDict()

    def get_parsed(self, message_id: int, attributed_body: Any) -> Dict[str, Any]:
        if message_id in self._cache:
            self._cache.move_to_end(message_id)
            return self._cache[message_id]

        parsed = parse_attributed_body(attributed_body)
        self._cache[message_id] = parsed
        if len(self._cache) > self.max_size:
            self._cache.popitem(last=False)
        return parsed


def detect_reaction(associated_message_type: Any) -> str:
    """
    Translate iMessage associated_message_type to a human readable reaction type.
    Falls back to 'no-reaction' when unknown or reactions dict unavailable.

    Delegates to data_enrichment.detect_reaction to avoid duplicating the
    reaction-dict lookup logic.
    """
    return de.detect_reaction(associated_message_type)


def parse_attributed_body(data: Any) -> Dict[str, Any]:
    """
    Safe wrapper around data_enrichment.parse_AttributeBody with guard rails.
    Always returns a dict with at least {'text': None, 'components': {}, 'metadata': {}}.
    """
    try:
        parsed = de.parse_AttributeBody(data)
        if isinstance(parsed, dict):
            return {"text": parsed.get("text"), "components": parsed.get("components", {}), "metadata": parsed.get("metadata", {})}
    except Exception:
        pass
    return {"text": None, "components": {}, "metadata": {}}


def finalize_text(text: Optional[str], parsed_body: Optional[Dict[str, Any]]) -> str:
    parsed_text = (parsed_body or {}).get("text") if isinstance(parsed_body, dict) else None
    if text and str(text).strip() != "":
        return str(text)
    if parsed_text:
        return str(parsed_text)
    return ""


def extract_spotify_urls(text: str) -> List[str]:
    """Extract Spotify URLs from text using regex."""
    if not text:
        return []
    pattern = r'https?://(open\.spotify\.com|spotify\.link)/[^\s<>"{}|\\^`\[\]]+'
    return [match.group(0) for match in re.finditer(pattern, text)]


def domain_matches(domain_value: str, pattern: str) -> bool:
    """Check if a domain matches a target pattern, ignoring 'www.' prefix."""
    domain_clean = domain_value.replace('www.', '')
    pattern_clean = pattern.replace('www.', '')
    return domain_clean == pattern_clean or domain_clean.endswith('.' + pattern_clean)


def extract_all_urls(text: str) -> List[Dict[str, str]]:
    """
    Extract all URLs from text and categorize them by type.
    Returns a list of dicts with 'url' and 'type' keys.
    """
    if not text:
        return []

    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    matches = list(re.finditer(url_pattern, text))

    categorized_urls = []
    for match in matches:
        url = match.group(0).rstrip('.,;!?)')

        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            url_type = "other"
            if domain_matches(domain, 'spotify.com') or domain_matches(domain, 'spotify.link'):
                url_type = "spotify"
            elif domain_matches(domain, 'youtube.com') or domain_matches(domain, 'youtu.be'):
                url_type = "youtube"
            elif domain_matches(domain, 'instagram.com') or domain_matches(domain, 'instagr.am'):
                url_type = "instagram"
            elif domain_matches(domain, 'music.apple.com') or domain_matches(domain, 'itunes.apple.com'):
                url_type = "apple_music"
            elif domain_matches(domain, 'tiktok.com'):
                url_type = "tiktok"
            elif domain_matches(domain, 'twitter.com') or domain_matches(domain, 'x.com'):
                url_type = "twitter"
            elif domain_matches(domain, 'facebook.com') or domain_matches(domain, 'fb.com'):
                url_type = "facebook"
            elif domain_matches(domain, 'soundcloud.com'):
                url_type = "soundcloud"
            elif domain_matches(domain, 'bandcamp.com'):
                url_type = "bandcamp"
            elif domain_matches(domain, 'tidal.com'):
                url_type = "tidal"
            elif domain_matches(domain, 'amazon.com') and ('music' in domain or '/music' in parsed.path):
                url_type = "amazon_music"
            elif domain_matches(domain, 'deezer.com'):
                url_type = "deezer"
            elif domain_matches(domain, 'pandora.com'):
                url_type = "pandora"
            elif domain_matches(domain, 'iheart.com'):
                url_type = "iheart"
            elif domain_matches(domain, 'tunein.com'):
                url_type = "tunein"

            categorized_urls.append({
                "url": url,
                "type": url_type
            })
        except Exception:
            categorized_urls.append({
                "url": url,
                "type": "other"
            })

    return categorized_urls


def extract_urls_by_type(text: str) -> Dict[str, List[str]]:
    """
    Extract URLs from text and categorize into spotify, youtube, and other.
    """
    if not text:
        return {"spotify": [], "youtube": [], "other": []}

    url_pattern = r'https?://[^\s<>"{}|\^`\[\]]+'
    matches = list(re.finditer(url_pattern, text))

    categorized: Dict[str, List[str]] = {"spotify": [], "youtube": [], "other": []}

    for match in matches:
        url = match.group(0).rstrip(".,;!?)")
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
        except Exception:
            domain = ""

        if domain_matches(domain, "spotify.com") or domain_matches(domain, "spotify.link"):
            categorized["spotify"].append(url)
        elif domain_matches(domain, "youtube.com") or domain_matches(domain, "youtu.be"):
            categorized["youtube"].append(url)
        else:
            categorized["other"].append(url)

    return categorized


def compute_content_hash(text: str, sender_handle: Optional[str], date_utc: Optional[str]) -> str:
    """
    Deterministic content hash for dedupe/idempotency.
    Uses lowercased text + sender + date as inputs.
    """
    normalized = "|".join(
        [
            (text or "").strip().lower(),
            (sender_handle or "").strip().lower(),
            (date_utc or "").strip().lower(),
        ]
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def parse_message_fields(
    text: Optional[str],
    attributed_body: Any,
    sender_handle: Optional[str],
    date_utc: Optional[str],
) -> Dict[str, Any]:
    """
    Produce unified parsed fields for a message record.
    Returns: final_text, spotify_url, has_spotify, content_hash, parsed_body.
    """
    parsed_body = parse_attributed_body(attributed_body)
    final_text = finalize_text(text, parsed_body)
    urls = extract_urls_by_type(final_text)
    spotify_url = urls["spotify"][0] if urls["spotify"] else None
    content_hash = compute_content_hash(final_text, sender_handle, date_utc) if final_text else None
    return {
        "final_text": final_text,
        "spotify_url": spotify_url,
        "has_spotify": 1 if spotify_url else 0,
        "content_hash": content_hash,
        "parsed_body": parsed_body,
        "urls": urls,
    }

