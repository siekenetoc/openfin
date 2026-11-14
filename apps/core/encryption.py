"""Fernet-basierte Verschlüsselung für sensible Zugangsdaten (Encryption at Rest)."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger("openfin.encryption")


def _normalize_key(key: str | bytes) -> bytes:
    if isinstance(key, bytes):
        key = key.decode()
    key = key.strip()
    if not key:
        raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY ist nicht gesetzt.")
    # Erlauben sowohl rohe 32-Byte-Keys (base64) als auch bereits kodierte Fernet-Keys.
    try:
        raw = base64.urlsafe_b64decode(key.encode())
    except Exception as exc:  # noqa: BLE001
        raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY ist kein gültiger URL-safe Base64-Key.") from exc
    if len(raw) != 32:
        raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY muss 32 Byte (URL-safe Base64) lang sein.")
    return key.encode()


def get_fernet() -> Fernet:
    return Fernet(_normalize_key(settings.FIELD_ENCRYPTION_KEY))


def encrypt(value: Any) -> str | None:
    if value is None or value == "":
        return value
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return get_fernet().encrypt(str(value).encode("utf-8")).decode("ascii")


def decrypt(value: Any) -> str | None:
    if value is None or value == "":
        return value
    if not isinstance(value, str):
        return value
    try:
        return get_fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        logger.warning("Entschlüsselung fehlgeschlagen – Wert wird als Klartext-Legacy behandelt.")
        return value


def decrypt_json(value: Any, default: Any = None) -> Any:
    raw = decrypt(value)
    if raw in (None, ""):
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


def encrypt_json(value: Any) -> str | None:
    return encrypt(value)
