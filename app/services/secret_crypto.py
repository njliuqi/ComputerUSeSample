import base64
import hashlib
import hmac
import os

from app.core.config import get_settings


PREFIX = "enc:v1:"


class SecretCryptoError(ValueError):
    pass


def encrypt_secret(value: str) -> str:
    if not value:
        return value
    nonce = os.urandom(16)
    plaintext = value.encode("utf-8")
    ciphertext = _xor_with_keystream(plaintext, nonce)
    tag = _mac(nonce, ciphertext)
    return f"{PREFIX}{_b64(nonce)}:{_b64(ciphertext)}:{_b64(tag)}"


def decrypt_secret(value: str) -> str:
    if not value or not value.startswith(PREFIX):
        return value

    parts = value.removeprefix(PREFIX).split(":")
    if len(parts) != 3:
        raise SecretCryptoError("Invalid encrypted secret")

    nonce = _unb64(parts[0])
    ciphertext = _unb64(parts[1])
    tag = _unb64(parts[2])
    expected_tag = _mac(nonce, ciphertext)
    if not hmac.compare_digest(tag, expected_tag):
        raise SecretCryptoError("Encrypted secret authentication failed")
    return _xor_with_keystream(ciphertext, nonce).decode("utf-8")


def is_encrypted_secret(value: str) -> bool:
    return value.startswith(PREFIX)


def _key(purpose: bytes) -> bytes:
    secret = get_settings().api_key_encryption_secret.get_secret_value().encode("utf-8")
    return hmac.new(secret, purpose, hashlib.sha256).digest()


def _mac(nonce: bytes, ciphertext: bytes) -> bytes:
    return hmac.new(_key(b"mac"), nonce + ciphertext, hashlib.sha256).digest()


def _xor_with_keystream(value: bytes, nonce: bytes) -> bytes:
    key = _key(b"stream")
    output = bytearray()
    counter = 0
    while len(output) < len(value):
        block = hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()
        output.extend(block)
        counter += 1
    return bytes(item ^ stream for item, stream in zip(value, output))


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode((value + "=" * (-len(value) % 4)).encode("ascii"))
