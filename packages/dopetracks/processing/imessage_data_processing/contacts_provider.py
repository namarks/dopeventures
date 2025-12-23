"""Optional Contacts integration helpers."""
from __future__ import annotations

import importlib
import importlib.util
from typing import Any, Optional

CONTACTS_MODULE = "dopetracks.processing.contacts_data_processing.import_contact_info"
_CONTACTS_MODULE = None
_CONTACTS_LOADED = False


def _load_contacts_module():
    global _CONTACTS_MODULE
    global _CONTACTS_LOADED
    if _CONTACTS_LOADED:
        return _CONTACTS_MODULE
    _CONTACTS_LOADED = True
    spec = importlib.util.find_spec(CONTACTS_MODULE)
    if spec is None:
        _CONTACTS_MODULE = None
        return None
    _CONTACTS_MODULE = importlib.import_module(CONTACTS_MODULE)
    return _CONTACTS_MODULE


def is_available() -> bool:
    return _load_contacts_module() is not None


def get_contact_info_by_handle(handle_id: str) -> Optional[dict[str, Any]]:
    module = _load_contacts_module()
    if module is None:
        return None
    return module.get_contact_info_by_handle(handle_id)


def get_contacts_db_path() -> Optional[str]:
    module = _load_contacts_module()
    if module is None:
        return None
    return module.get_contacts_db_path()


def clean_phone_number(phone: str) -> Optional[str]:
    module = _load_contacts_module()
    if module is None:
        return None
    return module.clean_phone_number(phone)
