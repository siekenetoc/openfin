import base64
import os

import pytest
from django.test import override_settings

from apps.core.encryption import decrypt, decrypt_json, encrypt, encrypt_json


def _key() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


@pytest.mark.parametrize("value", ["12345", "super-secret-api-key", "ümlaut-ß-€"])
def test_encrypt_decrypt_roundtrip(value):
    with override_settings(FIELD_ENCRYPTION_KEY=_key()):
        encrypted = encrypt(value)
        assert encrypted != value
        assert decrypt(encrypted) == value


def test_encrypted_json_roundtrip():
    with override_settings(FIELD_ENCRYPTION_KEY=_key()):
        payload = {"client_id": "abc", "nested": [1, 2, 3], "flag": True}
        encrypted = encrypt_json(payload)
        assert decrypt_json(encrypted) == payload


def test_invalid_token_returns_legacy_plaintext():
    with override_settings(FIELD_ENCRYPTION_KEY=_key()):
        assert decrypt("not-a-valid-token") == "not-a-valid-token"


def test_missing_key_raises():
    with override_settings(FIELD_ENCRYPTION_KEY=""):
        from django.core.exceptions import ImproperlyConfigured

        with pytest.raises(ImproperlyConfigured):
            encrypt("value")
