import hashlib
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from . import data_enrichment as de

try:
    # Optional dependency; only present in some environments
    from ...utils import dictionaries  # type: ignore
except Exception:
    dictionaries = None


def detect_reaction(associated_message_type: Any) -> str:
    """
    Translate iMessage associated_message_type to a human readable reaction type.
    Falls back to 'no-reaction' when unknown or reactions dict unavailable.
    """
    if dictionaries and hasattr(dictionaries, "reaction_dict"):
        return dictionaries.reaction_dict.get(associated_message_type, "no-reaction")
    return "no-reaction"


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


def extract_urls_by_type(text: str) -> Dict[str, List[str]]:
    """
    Extract URLs from text and categorize into spotify, youtube, and other.
    """
    if not text:
        return {"spotify": [], "youtube": [], "other": []}

    url_pattern = r'https?://[^\s<>"{}|\^`\[\]]+'
    matches = list(re.finditer(url_pattern, text))

    categorized: Dict[str, List[str]] = {"spotify": [], "youtube": [], "other": []}

    def domain_matches(domain: str, target: str) -> bool:
        domain_clean = domain.replace("www.", "")
        target_clean = target.replace("www.", "")
        return domain_clean == target_clean or domain_clean.endswith("." + target_clean)

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

