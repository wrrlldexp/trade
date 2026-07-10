"""Шифрование API-ключей через Fernet."""

from functools import lru_cache

from cryptography.fernet import Fernet

from app.config import get_settings

settings = get_settings()


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    # L-8: если ключ невалидный — упадёт при первом импорте, а не позже
    return Fernet(settings.ENCRYPTION_KEY.encode())


def encrypt(plaintext: str) -> bytes:
    return _get_fernet().encrypt(plaintext.encode())


def decrypt(ciphertext: bytes) -> str:
    return _get_fernet().decrypt(ciphertext).decode()
