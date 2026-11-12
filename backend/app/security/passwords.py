from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()
# Hash factice : on vérifie toujours un hash même si l'email n'existe pas (anti-énumération par timing).
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    try:
        return _hasher.verify(hashed or _DUMMY_HASH, password) and hashed is not None
    except (VerificationError, InvalidHashError):
        return False


def password_policy_errors(password: str) -> list[str]:
    errors = []
    if len(password) < 12:
        errors.append("at least 12 characters")
    if password.lower() == password:
        errors.append("at least one uppercase letter")
    if password.upper() == password:
        errors.append("at least one lowercase letter")
    if not any(c.isdigit() for c in password):
        errors.append("at least one digit")
    return errors
