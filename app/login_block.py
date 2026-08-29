"""QBR login, password setup/reset, and persistent browser session."""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from datetime import datetime, timedelta

import streamlit as st

from app.db import SessionLocal
from app.auth import (
    get_user,
    verify_password,
    set_password,
    reset_password_self_service,
    record_failed_login,
    clear_failed_logins,
)

try:
    import extra_streamlit_components as stx
except ImportError:
    stx = None

COOKIE_NAME = "qbr_auth"
COOKIE_SECRET = os.getenv("QBR_COOKIE_SECRET", "change-this-qbr-cookie-secret")
COOKIE_DAYS = 30


def _create_cookie_manager():
    """Create the CookieManager in normal Streamlit execution, never in a cached function."""
    if stx is None:
        return None
    # Keep the component instance in session state so it is created once per
    # Streamlit session. This function intentionally has NO @st.cache_* decorator.
    if "_qbr_cookie_manager" not in st.session_state:
        st.session_state["_qbr_cookie_manager"] = stx.CookieManager(
            key="qbr_auth_cookie_manager"
        )
    return st.session_state["_qbr_cookie_manager"]


def _token(username: str, issued: int | None = None) -> str:
    issued = int(issued or time.time())
    payload = f"{username}|{issued}"
    sig = hmac.new(
        COOKIE_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}|{sig}"


def _username_from_token(value: str):
    try:
        username, issued_text, signature = value.split("|", 2)
        issued = int(issued_text)
        if not username or time.time() - issued > COOKIE_DAYS * 86400:
            return None
        expected = hmac.new(
            COOKIE_SECRET.encode("utf-8"),
            f"{username}|{issued}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if hmac.compare_digest(signature, expected):
            return username
    except Exception:
        pass
    return None


def _save_cookie(user: dict):
    cm = _create_cookie_manager()
    username = str(user.get("Username", "")).strip() if user else ""
    if cm and username:
        cm.set(
            COOKIE_NAME,
            _token(username),
            key="qbr_auth_set",
            path="/",
            expires_at=datetime.now() + timedelta(days=COOKIE_DAYS),
            same_site="lax",
        )


def _read_cookie():
    cm = _create_cookie_manager()
    if not cm:
        return None
    try:
        return _username_from_token(cm.get(COOKIE_NAME) or "")
    except Exception:
        return None


def _delete_cookie():
    cm = _create_cookie_manager()
    if cm:
        try:
            cm.delete(COOKIE_NAME, key="qbr_auth_delete")
        except Exception:
            pass


def valid_password(password: str) -> bool:
    password = password or ""
    return (
        len(password) >= 8
        and any(c.isupper() for c in password)
        and any(c.islower() for c in password)
        and any(c.isdigit() for c in password)
    )


def _toast(kind: str, title: str, detail: str = ""):
    icon = {"ok": "✓", "bad": "!", "info": "i"}.get(kind, "i")
    st.markdown(
        f'<div class="qbr-toast {kind}"><b class="qbr-toast-icon">{icon}</b>'
        f'<div><b>{title}</b><span>{detail}</span></div></div>',
        unsafe_allow_html=True,
    )


def success_message(title: str, detail: str = ""):
    _toast("ok", title, detail)


def error_message(title: str, detail: str = ""):
    _toast("bad", title, detail)


def info_message(title: str, detail: str = ""):
    _toast("info", title, detail)


def initialise_auth_state():
    defaults = {
        "user": None,
        "auth_mode": "login",
        "pending_alias": "",
        "flash_message": None,
        "show_change_password": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # CookieManager is deliberately initialized here, outside any cached
    # function. Browser refreshes can then restore the signed login cookie.
    if st.session_state.user is None:
        username = _read_cookie()
        if username:
            db = SessionLocal()
            try:
                account = get_user(db, username)
                if account and account.get("IsActive") and not account.get("MustSetPassword"):
                    st.session_state.user = account
                    st.session_state.auth_mode = "dashboard"
            except Exception:
                pass
            finally:
                db.close()


def _set_authenticated_user(user: dict):
    st.session_state.user = user
    st.session_state.auth_mode = "dashboard"
    _save_cookie(user)


def clear_session():
    """Explicit logout. Normal browser refresh does not clear the cookie."""
    _delete_cookie()
    st.session_state.user = None
    st.session_state.auth_mode = "login"
    st.session_state.pending_alias = ""
    st.session_state.flash_message = None
    st.session_state.show_change_password = False


def render_flash():
    message = st.session_state.pop("flash_message", None)
    if message:
        success_message(message[0], message[1] if len(message) > 1 else "")


def _css():
    st.markdown("""<style>
.qbr-login-wrap{max-width:560px;margin:3vh auto 0}.qbr-auth-brand{padding:24px 22px;border-radius:26px;text-align:center;background:linear-gradient(135deg,#082c49,#106d88,#1da98c);color:#fff;box-shadow:10px 11px 0 rgba(8,44,73,.15),0 18px 35px rgba(8,44,73,.20);margin-bottom:18px}.qbr-auth-brand h1{margin:0;font:1000 30px 'Segoe UI',Aptos,sans-serif}.qbr-auth-brand p{margin:7px 0;font-size:12px}.qbr-auth-card{padding:22px 28px 28px;border-radius:28px;background:linear-gradient(145deg,#fff,#eaf6f8);border:1px solid #d2e5e9;box-shadow:14px 15px 35px rgba(11,52,74,.16),-8px -8px 20px #fff}.qbr-auth-title{text-align:center;font:1000 27px 'Segoe UI',Aptos,sans-serif;color:#12344d;margin:0 0 5px}.qbr-auth-sub{text-align:center;color:#5b7785;font-size:12px;margin-bottom:18px}.qbr-auth-label{width:390px;max-width:100%;margin:12px auto 5px;font:1000 13px 'Segoe UI',Aptos,sans-serif}.qbr-auth-label.user{color:#087b9a}.qbr-auth-label.pass{color:#16806f}.qbr-auth-label.new{color:#087b9a}.qbr-auth-label.confirm{color:#16806f}.qbr-auth-label.current{color:#8b6500}div[data-testid="stTextInput"]{width:390px!important;max-width:100%!important;margin:0 auto!important}div[data-testid="stTextInput"] input{height:46px!important;border-radius:999px!important;padding:0 17px!important;background:linear-gradient(145deg,#fff,#f0f8fa)!important;border:2px solid #c7e0e7!important;color:#12344d!important;box-shadow:inset 3px 3px 8px rgba(14,57,76,.07),4px 5px 0 rgba(15,39,66,.09)!important}div[data-testid="stTextInput"] input:focus{border-color:#1595a5!important;box-shadow:0 0 0 4px rgba(21,149,165,.12),4px 5px 0 rgba(15,39,66,.09)!important}.qbr-auth-primary{width:390px;max-width:100%;margin:15px auto 9px}.qbr-auth-primary button{width:100%!important;height:49px!important;border:0!important;border-radius:999px!important;color:#fff!important;font-weight:1000!important;background:linear-gradient(135deg,#0a5270,#128894,#20a58b)!important;box-shadow:6px 7px 0 rgba(15,39,66,.16),0 12px 23px rgba(15,39,66,.14)!important}.qbr-auth-note,.qbr-password-rule{width:390px;max-width:100%;margin:10px auto;padding:11px 14px;border-radius:14px;font-size:12px;box-shadow:3px 4px 0 rgba(15,39,66,.07)}.qbr-auth-note{background:#eaf7fb;border:1px solid #add9e3;color:#28596b}.qbr-password-rule{background:#fff7df;border:1px solid #ead28a;color:#725a00}.qbr-toast{display:flex;gap:11px;align-items:center;padding:12px 15px;border-radius:15px;margin:11px 0;box-shadow:4px 5px 0 rgba(15,39,66,.09);font-size:13px}.qbr-toast span{display:block;font-weight:600;margin-top:3px}.qbr-toast-icon{width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff}.qbr-toast.ok{background:#e7faef;border:1px solid #68c98d;color:#12623a}.qbr-toast.ok .qbr-toast-icon{background:#1d9b5b}.qbr-toast.bad{background:#fff0f0;border:1px solid #df8a8a;color:#982323}.qbr-toast.bad .qbr-toast-icon{background:#d43a3a}.qbr-toast.info{background:#eaf5ff;border:1px solid #7fb8e8;color:#185486}.qbr-toast.info .qbr-toast-icon{background:#237db7}footer{visibility:hidden}
</style>""", unsafe_allow_html=True)


def _brand():
    st.markdown(
        '<div class="qbr-login-wrap"><div class="qbr-auth-brand"><h1>📊 QBR Executive Dashboard</h1><p>HCLTech Customer Operations Command Center</p></div></div>',
        unsafe_allow_html=True,
    )


def _fields(prefix: str, current: bool = False):
    cur = ""
    if current:
        st.markdown('<div class="qbr-auth-label current">🔐 Current Password</div>', unsafe_allow_html=True)
        cur = st.text_input("Current Password", type="password", label_visibility="collapsed", key=f"{prefix}_current")
    st.markdown('<div class="qbr-auth-label new">🔑 New Password</div>', unsafe_allow_html=True)
    p1 = st.text_input("New Password", type="password", label_visibility="collapsed", key=f"{prefix}_new")
    st.markdown('<div class="qbr-auth-label confirm">✅ Confirm New Password</div>', unsafe_allow_html=True)
    p2 = st.text_input("Confirm New Password", type="password", label_visibility="collapsed", key=f"{prefix}_confirm")
    st.markdown('<div class="qbr-password-rule">Password must contain <b>8+ characters</b>, uppercase, lowercase and a number.</div>', unsafe_allow_html=True)
    return cur, p1, p2


def _login():
    st.markdown('<div class="qbr-auth-card"><div class="qbr-auth-title">🔐 Sign in</div><div class="qbr-auth-sub">Secure access to live QBR ticket and alert analytics.</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="qbr-auth-label user">👤 Username</div>', unsafe_allow_html=True)
    username = st.text_input("Username", label_visibility="collapsed", key="login_username")
    st.markdown('<div class="qbr-auth-label pass">🔒 Password</div>', unsafe_allow_html=True)
    password = st.text_input("Password", type="password", label_visibility="collapsed", key="login_password")
    st.markdown('<div class="qbr-auth-primary">', unsafe_allow_html=True)
    clicked = st.button("🔐 LOGIN", use_container_width=True, key="login_button")
    st.markdown('</div>', unsafe_allow_html=True)
    a, b = st.columns(2)
    with a:
        if st.button("Set My Password", use_container_width=True, key="set_my_password_link"):
            if not username.strip():
                error_message("Username required.", "Enter your username first.")
            else:
                st.session_state.pending_alias = username.strip()
                st.session_state.auth_mode = "set"
                st.rerun()
    with b:
        if st.button("Forgot Password", use_container_width=True, key="forgot_password_link"):
            st.session_state.auth_mode = "forgot"
            st.rerun()
    if not clicked:
        return
    alias = username.strip()
    if not alias:
        error_message("Username required.")
        return
    db = SessionLocal()
    try:
        account = get_user(db, alias)
        if not account:
            error_message("Username not found.")
            return
        if not account.get("IsActive"):
            error_message("Account inactive.")
            return
        locked = account.get("LockedUntil")
        if locked and locked > datetime.now():
            error_message("Account temporarily locked.", "Please try again later.")
            return
        if account.get("MustSetPassword") or not account.get("PasswordHash"):
            st.session_state.pending_alias = alias
            st.session_state.auth_mode = "set"
            st.rerun()
        if verify_password(password, account.get("PasswordHash")):
            clear_failed_logins(db, account["UserID"])
            db.commit()
            _set_authenticated_user(account)
            st.session_state.flash_message = ("Login successful.", f"Welcome {account['DisplayName']}.")
            st.rerun()
        record_failed_login(db, account["UserID"])
        db.commit()
        error_message("Incorrect password.")
    except Exception as exc:
        db.rollback()
        error_message("Login failed.", str(exc))
    finally:
        db.close()


def render_login():
    _css()
    _brand()
    _, center, _ = st.columns([1, 2.2, 1])
    with center:
        mode = st.session_state.get("auth_mode", "login")
        if mode == "login":
            _login()
            return
        if mode == "set":
            st.markdown('<div class="qbr-auth-card"><div class="qbr-auth-title">🔐 Set My Password</div><div class="qbr-auth-sub">First-time login — create your own password.</div></div>', unsafe_allow_html=True)
            alias = st.session_state.get("pending_alias", "").strip()
            db = SessionLocal()
            try:
                account = get_user(db, alias)
            except Exception as exc:
                account = None
                error_message("Unable to read account.", str(exc))
            finally:
                db.close()
            if not account:
                error_message("Username not found.", "Please return to login.")
            else:
                st.markdown(f'<div class="qbr-auth-note">👤 Account: <b>{account["DisplayName"]}</b> &nbsp;•&nbsp; Username: <b>{account["Username"]}</b></div>', unsafe_allow_html=True)
                _, p1, p2 = _fields("set")
                st.markdown('<div class="qbr-auth-primary">', unsafe_allow_html=True)
                clicked = st.button("🔐 SET PASSWORD & CONTINUE", use_container_width=True, key="set_password_button")
                st.markdown('</div>', unsafe_allow_html=True)
                if clicked:
                    if not valid_password(p1):
                        error_message("Password policy failed.", "Use 8+ characters with uppercase, lowercase and a number.")
                    elif p1 != p2:
                        error_message("Passwords do not match.")
                    else:
                        db = SessionLocal()
                        try:
                            set_password(db, account["UserID"], p1)
                            db.commit()
                            fresh = get_user(db, alias)
                            if not fresh:
                                raise RuntimeError("Account could not be reloaded after password update.")
                            _set_authenticated_user(fresh)
                            st.session_state.flash_message = ("Password set successfully.", "Welcome to the QBR Executive Dashboard.")
                            st.rerun()
                        except Exception as exc:
                            db.rollback()
                            error_message("Unable to set password.", str(exc))
                        finally:
                            db.close()
            if st.button("← Back to Login", use_container_width=True, key="set_back"):
                clear_session()
                st.rerun()
            return

        st.markdown('<div class="qbr-auth-card"><div class="qbr-auth-title">🔑 Forgot Password</div><div class="qbr-auth-sub">Self-service reset — no supervisor or superuser approval required.</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="qbr-auth-label user">👤 Username</div>', unsafe_allow_html=True)
        alias = st.text_input("Username", label_visibility="collapsed", key="forgot_username")
        st.markdown('<div class="qbr-auth-label current">🪪 Registered Name</div>', unsafe_allow_html=True)
        display = st.text_input("Registered Name", label_visibility="collapsed", key="forgot_display_name")
        _, p1, p2 = _fields("forgot")
        st.markdown('<div class="qbr-auth-primary">', unsafe_allow_html=True)
        clicked = st.button("🔑 RESET PASSWORD", use_container_width=True, key="forgot_reset_button")
        st.markdown('</div>', unsafe_allow_html=True)
        if clicked:
            if not alias.strip() or not display.strip():
                error_message("Missing account details.", "Enter username and registered name.")
            elif not valid_password(p1):
                error_message("Password policy failed.", "Use 8+ characters with uppercase, lowercase and a number.")
            elif p1 != p2:
                error_message("Passwords do not match.")
            else:
                db = SessionLocal()
                try:
                    ok, detail = reset_password_self_service(db, alias.strip(), display.strip(), p1)
                    if ok:
                        db.commit()
                        st.session_state.flash_message = ("Password reset successfully.", "You can now sign in with your new password.")
                        clear_session()
                        st.rerun()
                    db.rollback()
                    error_message("Password reset failed.", detail)
                except Exception as exc:
                    db.rollback()
                    error_message("Unable to reset password.", str(exc))
                finally:
                    db.close()
        if st.button("← Back to Login", use_container_width=True, key="forgot_back"):
            clear_session()
            st.rerun()
