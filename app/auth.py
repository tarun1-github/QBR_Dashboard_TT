"""
QBR authentication layer for SQL Server / CPDB.

Expected qbr.AppUser columns:
UserID, Username, DisplayName, PasswordHash, RoleName,
MustSetPassword, IsActive, FailedLoginCount, LockedUntil

No supervisor approval is required for self-service password reset.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Optional, Any

from sqlalchemy import text


PBKDF2_ITERATIONS = 310_000


def _row_to_dict(row) -> Optional[dict]:
    if row is None:
        return None
    try:
        return dict(row._mapping)
    except AttributeError:
        return dict(row)


def _normalise_user(user: Optional[dict]) -> Optional[dict]:
    if not user:
        return None

    # SQLAlchemy RowMapping objects are immutable.  Always copy to a real
    # dict before adding compatibility/session keys.
    user = dict(user)

    # Keep both database-style and session-friendly keys so older dashboard
    # code cannot break because of RoleName vs role / DisplayName vs name.
    role = str(user.get("RoleName") or "").upper()
    username = str(user.get("Username") or "")
    display = str(user.get("DisplayName") or "")

    user["role"] = role
    user["name"] = display
    user["username"] = username
    return user


def get_user(db, username: str) -> Optional[dict]:
    username = (username or "").strip()
    if not username:
        return None

    result = db.execute(
        text("""
            SELECT
                UserID,
                Username,
                DisplayName,
                PasswordHash,
                RoleName,
                MustSetPassword,
                IsActive,
                FailedLoginCount,
                LockedUntil
            FROM qbr.AppUser
            WHERE LOWER(Username) = LOWER(:username)
        """),
        {"username": username},
    )
    return _normalise_user(result.mappings().first())


def _hash_pbkdf2(password: str, salt: bytes, iterations: int = PBKDF2_ITERATIONS) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return (
        f"pbkdf2_sha256${iterations}$"
        f"{base64.urlsafe_b64encode(salt).decode().rstrip('=')}$"
        f"{base64.urlsafe_b64encode(digest).decode().rstrip('=')}"
    )


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    return _hash_pbkdf2(password, salt)


def _verify_pbkdf2(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt_b64, digest_b64 = stored.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False

        iterations_i = int(iterations)
        salt = base64.urlsafe_b64decode(salt_b64 + "=" * (-len(salt_b64) % 4))
        expected = base64.urlsafe_b64decode(
            digest_b64 + "=" * (-len(digest_b64) % 4)
        )
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations_i,
        )
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def verify_password(password: str, password_hash: Any) -> bool:
    if not password or not password_hash:
        return False

    stored = str(password_hash)

    # Our native QBR format.
    if stored.startswith("pbkdf2_sha256$"):
        return _verify_pbkdf2(password, stored)

    # Backward compatibility if an older deployment used Werkzeug.
    try:
        from werkzeug.security import check_password_hash
        if stored.startswith(("scrypt:", "pbkdf2:")):
            return bool(check_password_hash(stored, password))
    except Exception:
        pass

    # Backward compatibility if bcrypt was used previously.
    try:
        import bcrypt
        if stored.startswith(("$2a$", "$2b$", "$2y$")):
            return bool(bcrypt.checkpw(
                password.encode("utf-8"),
                stored.encode("utf-8"),
            ))
    except Exception:
        pass

    return False


def _execute_password_update(db, user_id: int, new_password: str) -> None:
    new_hash = hash_password(new_password)

    db.execute(
        text("""
            UPDATE qbr.AppUser
            SET
                PasswordHash = :password_hash,
                MustSetPassword = 0,
                FailedLoginCount = 0,
                LockedUntil = NULL
            WHERE UserID = :user_id
        """),
        {
            "password_hash": new_hash,
            "user_id": user_id,
        },
    )


def set_password(db, user_id: int, new_password: str) -> bool:
    """
    First-login password setup.
    The account is immediately converted to a normal login account.
    """
    _execute_password_update(db, user_id, new_password)
    db.commit()
    return True


def change_password(
    db,
    user_id: int,
    current_password: str,
    new_password: str,
) -> bool:
    """
    Normal authenticated password change.
    Returns False only when the current password is incorrect.
    """
    result = db.execute(
        text("""
            SELECT PasswordHash
            FROM qbr.AppUser
            WHERE UserID = :user_id
        """),
        {"user_id": user_id},
    )
    row = result.mappings().first()

    if not row:
        return False

    if not verify_password(current_password, row["PasswordHash"]):
        return False

    _execute_password_update(db, user_id, new_password)
    db.commit()
    return True


def reset_password_self_service(
    db,
    username: str,
    display_name: str,
    new_password: str,
) -> tuple[bool, str]:
    """
    Self-service password reset.

    Identity check:
      Username + registered DisplayName

    No supervisor/superuser request is created.
    """
    username = (username or "").strip()
    display_name = (display_name or "").strip()

    if not username or not display_name:
        return False, "Username and registered name are required."

    result = db.execute(
        text("""
            SELECT UserID, DisplayName, IsActive
            FROM qbr.AppUser
            WHERE LOWER(Username) = LOWER(:username)
              AND LOWER(LTRIM(RTRIM(DisplayName))) =
                  LOWER(LTRIM(RTRIM(:display_name)))
        """),
        {
            "username": username,
            "display_name": display_name,
        },
    )
    row = result.mappings().first()

    if not row:
        return False, "Username and registered name do not match."

    if not row["IsActive"]:
        return False, "This account is inactive."

    _execute_password_update(db, row["UserID"], new_password)
    db.commit()

    return True, "Password reset successfully."


def record_failed_login(db, user_id: int, max_attempts: int = 5) -> None:
    result = db.execute(
        text("""
            SELECT FailedLoginCount
            FROM qbr.AppUser
            WHERE UserID = :user_id
        """),
        {"user_id": user_id},
    )
    row = result.mappings().first()

    if not row:
        return

    count = int(row["FailedLoginCount"] or 0) + 1

    if count >= max_attempts:
        db.execute(
            text("""
                UPDATE qbr.AppUser
                SET FailedLoginCount = :count,
                    LockedUntil = :locked_until
                WHERE UserID = :user_id
            """),
            {
                "count": count,
                "locked_until": datetime.now() + timedelta(minutes=15),
                "user_id": user_id,
            },
        )
    else:
        db.execute(
            text("""
                UPDATE qbr.AppUser
                SET FailedLoginCount = :count
                WHERE UserID = :user_id
            """),
            {"count": count, "user_id": user_id},
        )

    db.commit()


def clear_failed_logins(db, user_id: int) -> None:
    db.execute(
        text("""
            UPDATE qbr.AppUser
            SET FailedLoginCount = 0,
                LockedUntil = NULL
            WHERE UserID = :user_id
        """),
        {"user_id": user_id},
    )
    db.commit()
