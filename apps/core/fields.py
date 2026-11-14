from __future__ import annotations

import json
from typing import Any

from django.db import models

from .encryption import decrypt, decrypt_json, encrypt


class EncryptedTextField(models.TextField):
    """TextField, das transparent mit Fernet verschlüsselt gespeichert wird."""

    description = "Verschlüsselter Text (Fernet/AES)"

    def from_db_value(self, value: Any, expression, connection) -> Any:  # noqa: ANN001
        return decrypt(value)

    def to_python(self, value: Any) -> Any:
        return value

    def get_prep_value(self, value: Any) -> Any:
        return encrypt(value)


class EncryptedCharField(models.CharField):
    """CharField-Variante für kurze Secrets (API-Keys, PINs)."""

    description = "Verschlüsseltes CharField (Fernet/AES)"

    def from_db_value(self, value: Any, expression, connection) -> Any:  # noqa: ANN001
        return decrypt(value)

    def to_python(self, value: Any) -> Any:
        return value

    def get_prep_value(self, value: Any) -> Any:
        return encrypt(value)


class EncryptedJSONField(models.TextField):
    """Speichert beliebiges JSON verschlüsselt; liefert Python-Objekte zurück."""

    description = "Verschlüsseltes JSON (Fernet/AES)"

    def from_db_value(self, value: Any, expression, connection) -> Any:  # noqa: ANN001
        return decrypt_json(value, default=None)

    def to_python(self, value: Any) -> Any:
        if isinstance(value, (dict, list)) or value is None:
            return value
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value

    def get_prep_value(self, value: Any) -> Any:
        if value is None:
            return None
        return encrypt(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
