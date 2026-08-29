"""QBR authentication UI.

Password reset is self-service.  Browser refresh does not log the user out;
only the explicit Sign out action clears the persistent authentication cookie.
"""
from __future__ import annotations

import json
import os
from datetime import datetime

import streamlit as st

from app.db import SessionLocal
from app.auth import get_user, verify_password, set_password, reset_password_self_service, record_failed_login, clear_failed_logins

try:
    from streamlit_cookies_manager import EncryptedCookieManager
except ImportError:  # pragma: no cover - handled with a clear message at runtime
    EncryptedCookieManager = None

COOKIE_NAME = "qbr_session"
COOKIE_PREFIX = "qbr-dashboard/"
COOKIE_SECRET = os.getenv("QBR_COOKIE_SECRET", "qbr-local-cookie-secret-change-me")


def _cookie_manager():
    if EncryptedCookieManager is None:
        return None
    cookies = EncryptedCookieManager(prefix=COOKIE_PREFIX, password=COOKIE_SECRET)
    if not cookies.ready():
        st.info("Preparing secure login session…")
        st.stop()
    return cookies


def valid_password(password: str) -> bool:
    password = password or ""
    return len(password) >= 8 and any(c.isupper() for c in password) and any(c.islower() for c in password) and any(c.isdigit() for c in password)


def success_message(title: str, detail: str = ""):
    st.markdown(f'<div class="qbr-toast success"><div class="qbr-toast-icon">✓</div><div><b>{title}</b><span>{detail}</span></div></div>', unsafe_allow_html=True)


def error_message(title: str, detail: str = ""):
    st.markdown(f'<div class="qbr-toast error"><div class="qbr-toast-icon">!</div><div><b>{title}</b><span>{detail}</span></div></div>', unsafe_allow_html=True)


def info_message(title: str, detail: str = ""):
    st.markdown(f'<div class="qbr-toast info"><div class="qbr-toast-icon">i</div><div><b>{title}</b><span>{detail}</span></div></div>', unsafe_allow_html=True)


def _save_session_to_cookie(user: dict):
    cookies = _cookie_manager()
    if cookies is None:
        return
    payload = {"username": str(user.get("Username", "")), "created": datetime.now().isoformat()}
    cookies[COOKIE_NAME] = json.dumps(payload, separators=(",", ":"))
    cookies.save()


def _read_session_cookie():
    cookies = _cookie_manager()
    if cookies is None:
        return None
    raw = cookies.get(COOKIE_NAME)
    if not raw:
        return None
    try:
        data = json.loads(raw)
        username = str(data.get("username", "")).strip()
        if not username:
            return None
        return username
    except Exception:
        return None


def _clear_cookie():
    cookies = _cookie_manager()
    if cookies is not None:
        try:
            del cookies[COOKIE_NAME]
            cookies.save()
        except Exception:
            pass
    try:
        st.query_params.clear()
    except Exception:
        pass


def initialise_auth_state():
    defaults = {"user": None, "auth_mode": "login", "pending_alias": "", "flash_message": None, "show_change_password": False}
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if st.session_state.user is None:
        _try_auto_login()


def _try_auto_login():
    username = _read_session_cookie()
    if not username:
        # Compatibility with an older development URL containing ?session=...
        try:
            session_param = st.query_params.get("session")
            if session_param:
                import base64
                data = json.loads(base64.b64decode(session_param).decode())
                username = str(data.get("username", "")).strip()
        except Exception:
            username = None
    if not username:
        return
    db = SessionLocal()
    try:
        user = get_user(db, username)
        if user and user.get("IsActive"):
            st.session_state.user = user
            st.session_state.auth_mode = "dashboard"
    finally:
        db.close()


def render_flash():
    message = st.session_state.pop("flash_message", None)
    if message:
        success_message(message[0], message[1] if len(message) > 1 else "")


def _set_authenticated_user(user: dict):
    st.session_state.user = user
    st.session_state.auth_mode = "dashboard"
    _save_session_to_cookie(user)


def _go_login():
    st.session_state.user = None
    st.session_state.auth_mode = "login"
    st.session_state.pending_alias = ""
    _clear_cookie()
    st.rerun()


def _auth_css():
    st.markdown("""
    <style>
    .qbr-login-wrap{max-width:600px;margin:4vh auto 0;}
    .qbr-auth-card{padding:32px 38px 35px;border-radius:30px;background:linear-gradient(145deg,#ffffff,#e7f5f8);border:1px solid #d5e7eb;box-shadow:18px 18px 40px rgba(11,52,74,.18),-10px -10px 24px rgba(255,255,255,.95);}
    .qbr-auth-brand{padding:22px 20px;border-radius:24px;text-align:center;background:linear-gradient(135deg,#0a3150,#116f88,#20a78d);color:#fff;box-shadow:8px 9px 0 rgba(8,44,73,.16),0 15px 30px rgba(8,44,73,.20);margin-bottom:22px;}
    .qbr-auth-brand h1{margin:0;font:1000 31px 'Segoe UI',Aptos,sans-serif}.qbr-auth-brand p{margin:7px 0 0;font-size:12px;opacity:.95}
    .qbr-auth-title{text-align:center;font:1000 28px 'Segoe UI',Aptos,sans-serif;color:#12344d;margin:8px 0 4px}.qbr-auth-sub{text-align:center;color:#587789;font-size:13px;margin-bottom:20px}
    .qbr-auth-label{width:420px;max-width:100%;margin:13px auto 6px;font:1000 13px 'Segoe UI',Aptos,sans-serif}.qbr-auth-label.user{color:#087b9a}.qbr-auth-label.pass{color:#16806f}.qbr-auth-label.new{color:#087b9a}.qbr-auth-label.confirm{color:#16806f}.qbr-auth-label.current{color:#8b6500}
    div[data-testid="stTextInput"]{width:420px!important;max-width:100%!important;margin:0 auto!important}
    div[data-testid="stTextInput"] input{height:48px!important;border-radius:999px!important;padding:0 18px!important;background:linear-gradient(145deg,#ffffff,#f1f8fa)!important;border:2px solid #c6dfe7!important;color:#12344d!important;font-size:14px!important;box-shadow:inset 3px 3px 8px rgba(14,57,76,.08),4px 5px 0 rgba(15,39,66,.10)!important;}
    div[data-testid="stTextInput"] input:focus{border-color:#1195a3!important;box-shadow:0 0 0 4px rgba(17,149,163,.14),4px 5px 0 rgba(15,39,66,.10)!important;}
    .qbr-auth-primary{width:420px;max-width:100%;margin:17px auto 9px}.qbr-auth-primary button{width:100%!important;height:52px!important;border:0!important;border-radius:999px!important;color:white!important;font-weight:1000!important;font-size:15px!important;background:linear-gradient(135deg,#0a5270,#128894,#20a58b)!important;box-shadow:7px 8px 0 rgba(15,39,66,.17),0 13px 24px rgba(15,39,66,.16)!important;}
    .qbr-auth-secondary button{border-radius:999px!important;font-weight:900!important;background:linear-gradient(145deg,#fff,#e7f3f6)!important;box-shadow:4px 5px 0 rgba(15,39,66,.12)!important;}
    .qbr-auth-note{width:420px;max-width:100%;margin:11px auto;padding:12px 15px;border-radius:15px;background:linear-gradient(145deg,#effaff,#e0f4f8);border:1px solid #afd8e3;color:#28596b;font-size:12px;box-shadow:4px 5px 0 rgba(15,39,66,.08)}
    .qbr-password-rule{width:420px;max-width:100%;margin:10px auto;padding:10px 13px;border-radius:14px;background:#fff7df;border:1px solid #ead28a;color:#725a00;font-size:12px;box-shadow:3px 4px 0 rgba(15,39,66,.08)}
    .qbr-toast{display:flex;gap:12px;align-items:center;padding:13px 16px;border-radius:16px;margin:12px 0;box-shadow:5px 6px 0 rgba(15,39,66,.10);font-size:13px}.qbr-toast span{display:block;font-weight:600;margin-top:3px}.qbr-toast-icon{width:29px;height:29px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:1000;color:#fff;box-shadow:2px 3px 0 rgba(0,0,0,.15)}.qbr-toast.success{background:#e7faef;border:1px solid #68c98d;color:#12623a}.qbr-toast.success .qbr-toast-icon{background:#1d9b5b}.qbr-toast.error{background:#fff0f0;border:1px solid #df8a8a;color:#982323}.qbr-toast.error .qbr-toast-icon{background:#d43a3a}.qbr-toast.info{background:#eaf5ff;border:1px solid #7fb8e8;color:#185486}.qbr-toast.info .qbr-toast-icon{background:#237db7}
    footer{visibility:hidden}
    </style>
    """, unsafe_allow_html=True)


def _brand():
    st.markdown('<div class="qbr-login-wrap"><div class="qbr-auth-brand"><h1>📊 QBR Executive Dashboard</h1><p>HCLTech Customer Operations Command Center</p></div></div>',unsafe_allow_html=True)


def _password_fields(prefix="auth", include_current=False):
    if include_current:
        st.markdown('<div class="qbr-auth-label current">🔐 Current Password</div>',unsafe_allow_html=True)
        current=st.text_input("Current Password",type="password",label_visibility="collapsed",key=f"{prefix}_current")
    else: current=""
    st.markdown('<div class="qbr-auth-label new">🔑 New Password</div>',unsafe_allow_html=True)
    p1=st.text_input("New Password",type="password",label_visibility="collapsed",key=f"{prefix}_new")
    st.markdown('<div class="qbr-auth-label confirm">✅ Confirm New Password</div>',unsafe_allow_html=True)
    p2=st.text_input("Confirm New Password",type="password",label_visibility="collapsed",key=f"{prefix}_confirm")
    st.markdown('<div class="qbr-password-rule">Password must contain <b>8+ characters</b>, uppercase, lowercase and a number.</div>',unsafe_allow_html=True)
    return current,p1,p2


def render_login():
    _auth_css(); _brand()
    _,center,_=st.columns([1,2.2,1])
    with center:
        mode=st.session_state.get("auth_mode","login")
        if mode=="set":
            st.markdown('<div class="qbr-auth-card"><div class="qbr-auth-title">🔐 Set My Password</div><div class="qbr-auth-sub">First-time login — create your own password.</div></div>',unsafe_allow_html=True)
            alias=st.session_state.get("pending_alias","").strip()
            db=SessionLocal()
            try: account=get_user(db,alias)
            except Exception as exc: account=None; error_message("Unable to read account.",str(exc))
            finally: db.close()
            if not account:
                error_message("Username not found.","Please return to login.")
            else:
                st.markdown(f'<div class="qbr-auth-note">👤 Account: <b>{account["DisplayName"]}</b> &nbsp;•&nbsp; Username: <b>{account["Username"]}</b></div>',unsafe_allow_html=True)
                _,p1,p2=_password_fields("set")
                st.markdown('<div class="qbr-auth-primary">',unsafe_allow_html=True)
                clicked=st.button("🔐 SET PASSWORD & CONTINUE",use_container_width=True,key="set_password_button")
                st.markdown('</div>',unsafe_allow_html=True)
                if clicked:
                    if not valid_password(p1): error_message("Password policy failed.","Use 8+ characters with uppercase, lowercase and a number.")
                    elif p1!=p2: error_message("Passwords do not match.")
                    else:
                        db=SessionLocal()
                        try:
                            set_password(db,account["UserID"],p1); fresh=get_user(db,alias)
                            if not fresh: raise RuntimeError("Account could not be reloaded after password update.")
                            _set_authenticated_user(fresh); st.session_state.flash_message=("Password set successfully.","Welcome to the QBR Executive Dashboard."); st.rerun()
                        except Exception as exc: db.rollback(); error_message("Unable to set password.",str(exc))
                        finally: db.close()
            if st.button("← Back to Login",use_container_width=True,key="set_back"): _go_login()
            return

        if mode=="forgot":
            st.markdown('<div class="qbr-auth-card"><div class="qbr-auth-title">🔑 Forgot Password</div><div class="qbr-auth-sub">Self-service reset — no supervisor or superuser approval required.</div></div>',unsafe_allow_html=True)
            st.markdown('<div class="qbr-auth-label user">👤 Username</div>',unsafe_allow_html=True)
            alias=st.text_input("Username",label_visibility="collapsed",key="forgot_username")
            st.markdown('<div class="qbr-auth-label current">🪪 Registered Name</div>',unsafe_allow_html=True)
            display=st.text_input("Registered Name",label_visibility="collapsed",key="forgot_display_name")
            _,p1,p2=_password_fields("forgot")
            st.markdown('<div class="qbr-auth-primary">',unsafe_allow_html=True); clicked=st.button("🔑 RESET PASSWORD",use_container_width=True,key="forgot_reset_button"); st.markdown('</div>',unsafe_allow_html=True)
            if clicked:
                if not alias.strip() or not display.strip(): error_message("Missing account details.","Enter username and registered name.")
                elif not valid_password(p1): error_message("Password policy failed.","Use 8+ characters with uppercase, lowercase and a number.")
                elif p1!=p2: error_message("Passwords do not match.")
                else:
                    db=SessionLocal()
                    try:
                        ok,detail=reset_password_self_service(db,alias.strip(),display.strip(),p1)
                        if ok: st.session_state.flash_message=("Password reset successfully.","You can now sign in with your new password."); _go_login()
                        else: error_message("Password reset failed.",detail)
                    except Exception as exc: db.rollback(); error_message("Unable to reset password.",str(exc))
                    finally: db.close()
            if st.button("← Back to Login",use_container_width=True,key="forgot_back"): _go_login()
            return

        st.markdown('<div class="qbr-auth-card"><div class="qbr-auth-title">🔐 Sign in</div><div class="qbr-auth-sub">Secure access to live QBR ticket and alert analytics.</div></div>',unsafe_allow_html=True)
        st.markdown('<div class="qbr-auth-label user">👤 Username</div>',unsafe_allow_html=True)
        username=st.text_input("Username",label_visibility="collapsed",key="login_username")
        st.markdown('<div class="qbr-auth-label pass">🔒 Password</div>',unsafe_allow_html=True)
        password=st.text_input("Password",type="password",label_visibility="collapsed",key="login_password")
        st.markdown('<div class="qbr-auth-primary">',unsafe_allow_html=True); login_clicked=st.button("🔐 LOGIN",use_container_width=True,key="login_button"); st.markdown('</div>',unsafe_allow_html=True)
        c1,c2=st.columns(2)
        with c1:
            if st.button("Set My Password",use_container_width=True,key="set_my_password_link"):
                if not username.strip(): error_message("Username required.","Enter your username first.")
                else: st.session_state.pending_alias=username.strip(); st.session_state.auth_mode="set"; st.rerun()
        with c2:
            if st.button("Forgot Password",use_container_width=True,key="forgot_password_link"): st.session_state.auth_mode="forgot"; st.rerun()
        if login_clicked:
            alias=username.strip()
            if not alias: error_message("Username required.","Please enter username."); return
            db=SessionLocal()
            try:
                account=get_user(db,alias)
                if not account: error_message("Username not found."); return
                if not account.get("IsActive"): error_message("Account inactive."); return
                locked_until=account.get("LockedUntil")
                if locked_until and locked_until>datetime.now(): error_message("Account temporarily locked.","Please try again later."); return
                if account.get("MustSetPassword") or not account.get("PasswordHash"):
                    st.session_state.pending_alias=alias; st.session_state.auth_mode="set"; st.rerun()
                if verify_password(password,account.get("PasswordHash")):
                    clear_failed_logins(db,account["UserID"]); _set_authenticated_user(account); st.session_state.flash_message=("Login successful.",f"Welcome {account['DisplayName']}."); st.rerun()
                record_failed_login(db,account["UserID"]); error_message("Incorrect password.")
            except Exception as exc: db.rollback(); error_message("Login failed.",str(exc))
            finally: db.close()


def clear_session():
    """Explicit logout: clear session state and the persistent browser cookie."""
    for key in ("user","pending_alias","flash_message","show_change_password"):
        st.session_state[key]=None if key=="user" else (False if key=="show_change_password" else "")
    st.session_state.auth_mode="login"
    _clear_cookie()
