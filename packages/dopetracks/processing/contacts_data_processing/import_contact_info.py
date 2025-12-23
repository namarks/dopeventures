"""
Lightweight contact lookup against macOS AddressBook.
Caches results in-memory keyed by normalized phone/email.
"""

import sqlite3
from pathlib import Path
from typing import Dict, Optional

_CONTACT_CACHE: Dict[str, Dict[str, Optional[str]]] = {}
_LOAD_ATTEMPTED = False


def _normalize_phone(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _add_contact_entry(key: str, first: Optional[str], last: Optional[str], org: Optional[str]) -> None:
    if not key:
        return
    full_name_parts = [p for p in [first, last] if p]
    full_name = " ".join(full_name_parts).strip() or org or None
    if not full_name:
        return
    _CONTACT_CACHE[key] = {
        "full_name": full_name,
        "first_name": first,
        "last_name": last,
        "unique_id": None,
    }


def _load_contacts() -> None:
    global _LOAD_ATTEMPTED
    if _LOAD_ATTEMPTED:
        return
    _LOAD_ATTEMPTED = True

    sources_dir = Path.home() / "Library" / "Application Support" / "AddressBook" / "Sources"
    if not sources_dir.exists():
        return

    for source in sources_dir.iterdir():
        db_path = source / "AddressBook-v22.abcddb"
        if not db_path.exists():
            continue
        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            # Phones
            try:
                cur.execute(
                    """
                    SELECT
                        phone.ZFULLNUMBER,
                        person.ZFIRSTNAME,
                        person.ZLASTNAME,
                        person.ZORGANIZATION
                    FROM ZABCDPHONENUMBER phone
                    JOIN ZABCDRECORD person ON phone.ZOWNER = person.Z_PK
                    """
                )
                for row in cur.fetchall():
                    full_number, first, last, org = row
                    if not full_number:
                        continue
                    normalized = _normalize_phone(str(full_number))
                    if normalized:
                        _add_contact_entry(normalized, first, last, org)
                        _add_contact_entry(str(full_number), first, last, org)
            except Exception:
                pass
            # Emails
            try:
                cur.execute(
                    """
                    SELECT
                        email.ZADDRESS,
                        person.ZFIRSTNAME,
                        person.ZLASTNAME,
                        person.ZORGANIZATION
                    FROM ZABCDEMAILADDRESS email
                    JOIN ZABCDRECORD person ON email.ZOWNER = person.Z_PK
                    """
                )
                for row in cur.fetchall():
                    address, first, last, org = row
                    if not address:
                        continue
                    normalized_email = _normalize_email(str(address))
                    if normalized_email:
                        _add_contact_entry(normalized_email, first, last, org)
            except Exception:
                pass
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass


def get_contact_info_by_handle(handle: str) -> Optional[Dict[str, Optional[str]]]:
    if not handle:
        return None
    _load_contacts()

    handle_str = str(handle)
    if "@" in handle_str:
        normalized_email = _normalize_email(handle_str)
        if normalized_email in _CONTACT_CACHE:
            return _CONTACT_CACHE[normalized_email]
        return _CONTACT_CACHE.get(handle_str)

    normalized_phone = _normalize_phone(handle_str)
    if normalized_phone and normalized_phone in _CONTACT_CACHE:
        return _CONTACT_CACHE[normalized_phone]

    return _CONTACT_CACHE.get(handle_str)