from typing import List, Optional


def normalize_phone(value: str) -> str:
    """Extract only digits from a phone number string."""
    return "".join(ch for ch in value if ch.isdigit())


def normalize_email(value: str) -> str:
    """Normalize an email address: strip whitespace and lowercase."""
    return value.strip().lower()


def normalize_handle(handle: Optional[str]) -> Optional[str]:
    """
    Normalize a single handle (phone/email) to a canonical string.
    - Emails lowercased
    - Phones digits-only, strip leading 1 if 11+ digits
    """
    if not handle:
        return None
    raw = str(handle).strip()
    if "@" in raw:
        return normalize_email(raw)
    digits = normalize_phone(raw)
    if digits.startswith("1") and len(digits) > 10:
        digits = digits[1:]
    return digits or raw


def normalize_handle_variants(handle: Optional[str]) -> List[str]:
    """
    Return ordered, deduped variants for lookup:
    - raw
    - lowercased email
    - digits-only phone
    - +1 + 10-digit phone (if applicable)
    - last 10 digits (if longer)
    """
    if not handle:
        return []
    raw = str(handle).strip()
    variants = [raw]

    if "@" in raw:
        variants.append(raw.lower())
    else:
        digits = "".join(ch for ch in raw if ch.isdigit())
        if digits:
            variants.append(digits)
            if len(digits) == 10:
                variants.append("+1" + digits)
            if len(digits) > 10:
                variants.append(digits[-10:])

    seen = set()
    out = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out

