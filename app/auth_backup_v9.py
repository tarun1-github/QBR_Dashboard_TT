from sqlalchemy import text
import hashlib
import secrets

ITERATIONS = 210000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, ITERATIONS
    )
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    if not stored:
        return False
    try:
        scheme, iterations, salt_hex, digest_hex = stored.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        return secrets.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def get_user(db, username: str):
    return db.execute(
        text("""
            SELECT UserID, Username, DisplayName, PasswordHash, RoleName,
                   MustSetPassword, IsActive, FailedLoginCount, LockedUntil
            FROM qbr.AppUser
            WHERE LOWER(LTRIM(RTRIM(Username))) =
                  LOWER(LTRIM(RTRIM(:username)))
        """),
        {"username": username.strip()},
    ).mappings().first()


def _audit(db, user_id: int, action: str):
    # Audit is best-effort so a mismatch in the audit table
    # never prevents the password itself from being changed.
    try:
        db.execute(
            text("""
                INSERT INTO qbr.PasswordAudit(UserID, ActionName)
                VALUES(:user_id, :action)
            """),
            {"user_id": user_id, "action": action},
        )
        db.commit()
    except Exception:
        db.rollback()


def set_password(db, user_id: int, password: str) -> bool:
    password_hash = hash_password(password)

    db.execute(
        text("""
            UPDATE qbr.AppUser
            SET PasswordHash=:password_hash,
                MustSetPassword=0,
                FailedLoginCount=0,
                LockedUntil=NULL
            WHERE UserID=:user_id
        """),
        {"password_hash": password_hash, "user_id": user_id},
    )
    db.commit()

    _audit(db, user_id, "SET_PASSWORD")
    return True


def change_password(
    db, user_id: int, old_password: str, new_password: str
) -> bool:
    stored = db.execute(
        text("""
            SELECT PasswordHash
            FROM qbr.AppUser
            WHERE UserID=:user_id
        """),
        {"user_id": user_id},
    ).scalar()

    if not verify_password(old_password, stored):
        return False

    db.execute(
        text("""
            UPDATE qbr.AppUser
            SET PasswordHash=:password_hash,
                MustSetPassword=0,
                FailedLoginCount=0,
                LockedUntil=NULL
            WHERE UserID=:user_id
        """),
        {"password_hash": hash_password(new_password), "user_id": user_id},
    )
    db.commit()

    _audit(db, user_id, "CHANGE_PASSWORD")
    return True
