from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


class SecretCipher:
    def __init__(self, master_key: str):
        cleaned = master_key.strip()
        if not cleaned:
            raise ValueError("APP_SECRET_KEY cannot be empty.")
        digest = hashlib.sha256(cleaned.encode("utf-8")).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, plaintext: str) -> str:
        cleaned = plaintext.strip()
        if not cleaned:
            raise ValueError("api_key cannot be empty.")
        return self._fernet.encrypt(cleaned.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        cleaned = ciphertext.strip()
        if not cleaned:
            raise ValueError("ciphertext cannot be empty.")
        try:
            return self._fernet.decrypt(cleaned.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Unable to decrypt stored API key with APP_SECRET_KEY.") from exc
