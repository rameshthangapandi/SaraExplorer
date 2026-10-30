import re

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()  # Argon2id with library defaults (memory-hard)

# Used when the email doesn't exist, so login takes the same time either way.
_DUMMY_HASH = _hasher.hash("timing-equaliser-not-a-real-password")

_COMMON = {
    "password", "password1", "password123", "12345678", "123456789", "1234567890", "qwerty123",
    "iloveyou", "admin123", "welcome1", "india123", "letmein123",
}


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def password_problems(password: str, email: str = "") -> list[str]:
    problems = []
    if len(password) < 10:
        problems.append("at least 10 characters")
    if len(password) > 128:
        problems.append("at most 128 characters")
    if not re.search(r"[a-z]", password) or not re.search(r"[A-Z]", password):
        problems.append("both upper- and lower-case letters")
    if not re.search(r"\d", password):
        problems.append("at least one number")
    if not re.search(r"[^A-Za-z0-9]", password):
        problems.append("at least one symbol")
    local = email.split("@")[0].lower()
    if password.lower() in _COMMON or (len(local) >= 4 and local in password.lower()):
        problems.append("not a common password or your email name")
    return problems
