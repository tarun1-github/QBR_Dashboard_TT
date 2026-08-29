"""
QBR Executive Dashboard authentication UI.

This module owns the login / first-login / change-password / forgot-password
screens. It intentionally does not require supervisor approval for a
self-service password reset.
"""

import streamlit as st

from app.db import SessionLocal
from app.auth import (
    get_user,
    verify_password,
    set_password,
    change_password,
    reset_password_self_service,
    record_failed_login,
    clear_failed_logins,
)


def valid_password(password: str) -> bool:
    password = password or ""
    return (
        len(password) >= 8
        and any(c.isupper() for c in password)
        and any(c.islower() for c in password)
        and any(c.isdigit() for c in password)
    )


def success_message(title: str, detail: str = ""):
    st.markdown(
        f"""
        <div class="qbr-toast success">
            <div class="qbr-toast-icon">✓</div>
            <div><b>{title}</b>
            {f"<span>{detail}</span>" if detail else ""}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def error_message(title: str, detail: str = ""):
    st.markdown(
        f"""
        <div class="qbr-toast error">
            <div class="qbr-toast-icon">!</div>
            <div><b>{title}</b>
            {f"<span>{detail}</span>" if detail else ""}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def info_message(title: str, detail: str = ""):
    st.markdown(
        f"""
        <div class="qbr-toast info">
            <div class="qbr-toast-icon">i</div>
            <div><b>{title}</b>
            {f"<span>{detail}</span>" if detail else ""}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def initialise_auth_state():
    defaults = {
        "user": None,
        "auth_mode": "login",
        "pending_alias": "",
        "flash_message": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_flash():
    message = st.session_state.pop("flash_message", None)
    if message:
        success_message(
            message[0],
            message[1] if len(message) > 1 else "",
        )


def _set_authenticated_user(user: dict):
    # Store the canonical DB fields plus compatibility keys.
    st.session_state.user = user
    st.session_state.auth_mode = "dashboard"


def _go_login():
    st.session_state.auth_mode = "login"
    st.session_state.pending_alias = ""
    st.rerun()


def _auth_css():
    st.markdown(
        """
        <style>
        .qbr-login-spacer { height: 7vh; }

        .qbr-auth-card {
            max-width: 470px;
            margin: 0 auto;
            padding: 28px 34px 30px;
            border-radius: 28px;
            background: linear-gradient(145deg,#ffffff,#eaf4f7);
            border: 1px solid rgba(255,255,255,.95);
            box-shadow:
                16px 16px 34px rgba(15,39,66,.18),
                -8px -8px 20px rgba(255,255,255,.95);
        }

        .qbr-auth-title {
            text-align:center;
            font-family:"Segoe UI","Aptos",sans-serif;
            font-size:30px;
            font-weight:900;
            color:#12344d;
            margin-bottom:4px;
        }

        .qbr-auth-subtitle {
            text-align:center;
            color:#557789;
            font-size:13px;
            margin-bottom:22px;
        }

        .qbr-auth-label {
            width:390px;
            max-width:100%;
            margin:11px auto 5px;
            font-family:"Segoe UI","Aptos",sans-serif;
            font-size:13px;
            font-weight:900;
        }

        .qbr-auth-label.user { color:#087b9a; }
        .qbr-auth-label.pass { color:#16806f; }
        .qbr-auth-label.current { color:#8b6500; }
        .qbr-auth-label.new { color:#087b9a; }
        .qbr-auth-label.confirm { color:#16806f; }

        div[data-testid="stTextInput"] {
            width:390px !important;
            max-width:100% !important;
            margin:0 auto !important;
        }

        div[data-testid="stTextInput"] input {
            height:45px !important;
            border-radius:999px !important;
            padding:0 17px !important;
            background:#fff !important;
            border:2px solid #cfe1e7 !important;
            box-shadow:inset 2px 2px 6px rgba(15,39,66,.06) !important;
        }

        div[data-testid="stTextInput"] input:focus {
            border-color:#1596a3 !important;
            box-shadow:0 0 0 3px rgba(21,150,163,.13) !important;
        }

        .qbr-auth-primary {
            width:390px;
            max-width:100%;
            margin:15px auto 7px;
        }

        .qbr-auth-primary button {
            width:100% !important;
            height:50px !important;
            border:0 !important;
            border-radius:999px !important;
            color:white !important;
            font-weight:900 !important;
            font-size:15px !important;
            background:linear-gradient(135deg,#0b5873,#147b8b,#23a38d) !important;
            box-shadow:6px 6px 0 rgba(15,39,66,.17),
                       0 10px 20px rgba(15,39,66,.15) !important;
        }

        .qbr-auth-secondary button {
            border-radius:999px !important;
            font-weight:800 !important;
        }

        .qbr-auth-note {
            width:390px;
            max-width:100%;
            margin:10px auto;
            padding:11px 14px;
            border-radius:14px;
            background:#edf7fb;
            border:1px solid #b8dce8;
            color:#28596b;
            font-size:12px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _header():
    st.markdown('<div class="qbr-login-spacer"></div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="qbr-auth-card">
            <div class="qbr-auth-title">📊 QBR Executive Dashboard</div>
            <div class="qbr-auth-subtitle">
                HCLTech Customer Operations Command Center
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_login():
    _auth_css()
    _header()

    _, center, _ = st.columns([1.15, 1.7, 1.15])

    with center:
        mode = st.session_state.get("auth_mode", "login")

        # ------------------------------------------------------------
        # FIRST LOGIN / SET PASSWORD
        # ------------------------------------------------------------
        if mode == "set":
            alias = st.session_state.get("pending_alias", "").strip()

            st.markdown("### 🔐 Set My Password")
            st.markdown(
                '<div class="qbr-auth-note">'
                'First-time login detected. Create your own password.'
                '</div>',
                unsafe_allow_html=True,
            )

            db = SessionLocal()
            try:
                user = get_user(db, alias)
            except Exception as exc:
                user = None
                error_message("Unable to read account.", str(exc))
            finally:
                db.close()

            if not user:
                error_message("Username not found.", "Please return to login.")
            else:
                st.info(f"Account: {user['DisplayName']}")

                st.markdown(
                    '<div class="qbr-auth-label new">🔑 New Password</div>',
                    unsafe_allow_html=True,
                )
                p1 = st.text_input(
                    "New Password",
                    type="password",
                    label_visibility="collapsed",
                    key="set_password_1",
                )

                st.markdown(
                    '<div class="qbr-auth-label confirm">✓ Confirm Password</div>',
                    unsafe_allow_html=True,
                )
                p2 = st.text_input(
                    "Confirm Password",
                    type="password",
                    label_visibility="collapsed",
                    key="set_password_2",
                )

                st.caption("Minimum 8 characters: uppercase + lowercase + number.")

                st.markdown('<div class="qbr-auth-primary">', unsafe_allow_html=True)
                clicked = st.button(
                    "🔐 SET PASSWORD & CONTINUE",
                    use_container_width=True,
                    key="set_password_button",
                )
                st.markdown("</div>", unsafe_allow_html=True)

                if clicked:
                    if not valid_password(p1):
                        error_message(
                            "Password does not meet the policy.",
                            "Use 8+ characters with uppercase, lowercase and a number.",
                        )
                    elif p1 != p2:
                        error_message("Passwords do not match.")
                    else:
                        db = SessionLocal()
                        try:
                            set_password(db, user["UserID"], p1)
                            fresh = get_user(db, alias)
                            if not fresh:
                                raise RuntimeError("Password was saved but the account could not be reloaded.")

                            _set_authenticated_user(fresh)
                            st.session_state.flash_message = (
                                "Password set successfully.",
                                "Welcome to the QBR Executive Dashboard.",
                            )
                            st.rerun()
                        except Exception as exc:
                            db.rollback()
                            error_message("Unable to set password.", str(exc))
                        finally:
                            db.close()

            if st.button("← Back to Login", use_container_width=True, key="set_back"):
                _go_login()

            return

        # ------------------------------------------------------------
        # FORGOT PASSWORD - SELF SERVICE
        # ------------------------------------------------------------
        if mode == "forgot":
            st.markdown("### 🔑 Reset Password")
            st.markdown(
                '<div class="qbr-auth-note">'
                'Self-service reset. No supervisor or superuser approval is required.'
                '</div>',
                unsafe_allow_html=True,
            )

            st.markdown(
                '<div class="qbr-auth-label user">👤 Username</div>',
                unsafe_allow_html=True,
            )
            alias = st.text_input(
                "Username",
                placeholder="",
                label_visibility="collapsed",
                key="forgot_username",
            )

            st.markdown(
                '<div class="qbr-auth-label current">🪪 Registered Name</div>',
                unsafe_allow_html=True,
            )
            display = st.text_input(
                "Registered Name",
                placeholder="",
                label_visibility="collapsed",
                key="forgot_display_name",
            )

            st.markdown(
                '<div class="qbr-auth-label new">🔑 New Password</div>',
                unsafe_allow_html=True,
            )
            p1 = st.text_input(
                "New Password",
                type="password",
                label_visibility="collapsed",
                key="forgot_password_1",
            )

            st.markdown(
                '<div class="qbr-auth-label confirm">✓ Confirm Password</div>',
                unsafe_allow_html=True,
            )
            p2 = st.text_input(
                "Confirm Password",
                type="password",
                label_visibility="collapsed",
                key="forgot_password_2",
            )

            st.markdown('<div class="qbr-auth-primary">', unsafe_allow_html=True)
            reset_clicked = st.button(
                "🔑 RESET PASSWORD",
                use_container_width=True,
                key="forgot_reset_button",
            )
            st.markdown("</div>", unsafe_allow_html=True)

            if reset_clicked:
                if not alias.strip() or not display.strip():
                    error_message(
                        "Missing account details.",
                        "Enter username and registered name.",
                    )
                elif not valid_password(p1):
                    error_message(
                        "Password does not meet the policy.",
                        "Use 8+ characters with uppercase, lowercase and a number.",
                    )
                elif p1 != p2:
                    error_message("Passwords do not match.")
                else:
                    db = SessionLocal()
                    try:
                        ok, msg = reset_password_self_service(
                            db,
                            alias,
                            display,
                            p1,
                        )
                        if ok:
                            st.session_state.flash_message = (
                                "Password reset successfully.",
                                "You can now sign in with your new password.",
                            )
                            _go_login()
                        else:
                            error_message("Password reset failed.", msg)
                    except Exception as exc:
                        db.rollback()
                        error_message("Unable to reset password.", str(exc))
                    finally:
                        db.close()

            if st.button("← Back to Login", use_container_width=True, key="forgot_back"):
                _go_login()

            return

        # ------------------------------------------------------------
        # NORMAL LOGIN
        # ------------------------------------------------------------
        st.markdown("### 🔐 Sign in")

        st.markdown(
            '<div class="qbr-auth-label user">👤 Username</div>',
            unsafe_allow_html=True,
        )
        username = st.text_input(
            "Username",
            placeholder="",
            label_visibility="collapsed",
            key="login_username",
        )

        st.markdown(
            '<div class="qbr-auth-label pass">🔒 Password</div>',
            unsafe_allow_html=True,
        )
        password = st.text_input(
            "Password",
            type="password",
            placeholder="",
            label_visibility="collapsed",
            key="login_password",
        )

        st.markdown('<div class="qbr-auth-primary">', unsafe_allow_html=True)
        login_clicked = st.button(
            "🔐 LOGIN",
            use_container_width=True,
            key="login_button",
        )
        st.markdown("</div>", unsafe_allow_html=True)

        c1, c2 = st.columns(2)

        with c1:
            if st.button(
                "Set My Password",
                use_container_width=True,
                key="set_my_password_link",
            ):
                if not username.strip():
                    st.warning("Enter username first.")
                else:
                    st.session_state.pending_alias = username.strip()
                    st.session_state.auth_mode = "set"
                    st.rerun()

        with c2:
            if st.button(
                "Forgot Password",
                use_container_width=True,
                key="forgot_password_link",
            ):
                st.session_state.auth_mode = "forgot"
                st.rerun()

        if login_clicked:
            alias = username.strip()

            if not alias:
                st.warning("Please enter username.")
                return

            db = SessionLocal()
            try:
                user = get_user(db, alias)

                if not user:
                    error_message("Username not found.")
                    return

                if not user["IsActive"]:
                    error_message("Account inactive.")
                    return

                locked_until = user.get("LockedUntil")
                if locked_until:
                    try:
                        if locked_until > __import__("datetime").datetime.now():
                            error_message(
                                "Account temporarily locked.",
                                "Please try again later.",
                            )
                            return
                    except Exception:
                        pass

                if user["MustSetPassword"] or not user["PasswordHash"]:
                    st.session_state.pending_alias = alias
                    st.session_state.auth_mode = "set"
                    st.rerun()

                if verify_password(password, user["PasswordHash"]):
                    clear_failed_logins(db, user["UserID"])
                    _set_authenticated_user(user)
                    st.session_state.flash_message = (
                        "Login successful.",
                        f"Welcome {user['DisplayName']}.",
                    )
                    st.rerun()

                record_failed_login(db, user["UserID"])
                error_message("Incorrect password.")

            except Exception as exc:
                db.rollback()
                error_message("Login failed.", str(exc))
            finally:
                db.close()
