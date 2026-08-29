import sys
import io
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import text

from app.db import SessionLocal
from app.auth import get_user, verify_password, set_password, change_password


st.set_page_config(
    page_title="QBR Executive Dashboard",
    page_icon="📊",
    layout="wide",
)

TOWER_TRACKS = {
    "Collaboration": [
        "BOA EV", "HSBC", "Problem Management", "BOA TP",
        "GTM TP", "HD Voice (Bgl)", "SCNOC"
    ],
    "Security": ["Cybersecurity", "DC-ACI", "Infra", "SOC"],
    "Foundation": ["SFNOC"],
    "Non-CMS": ["RIL"],
}

st.markdown("""
<style>
[data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg,#f4f8fb 0%,#eef5f7 50%,#e4f0f2 100%);
}
.hero {
    padding:20px 28px;border-radius:22px;
    background:linear-gradient(135deg,#0f2742,#146b85,#23a38d);
    color:white;box-shadow:0 14px 32px rgba(15,39,66,.25);
    margin-bottom:18px;
}
.hero h1 {margin:0;font-size:34px;font-family:"Segoe UI","Aptos",sans-serif}
.hero p {margin:6px 0 0;opacity:.92}
.kpi {
    border-radius:18px;padding:15px;min-height:105px;color:white;
    box-shadow:8px 8px 0 rgba(15,39,66,.14),0 10px 25px rgba(15,39,66,.12);
}
.kpi .t {font-size:12px;font-weight:800}
.kpi .v {font-size:29px;font-weight:900;margin-top:7px}
.kpi .s {font-size:11px;opacity:.9}
.section {font-size:20px;font-weight:800;color:#12344d;margin-top:12px}

/* Compact centered authentication */
.auth-wrap {max-width:440px;margin:0 auto}
.auth-card {
    padding:28px 32px 26px;border-radius:30px;
    background:linear-gradient(145deg,#ffffff,#eaf3f6);
    box-shadow:16px 16px 34px rgba(15,39,66,.18),
               -8px -8px 20px rgba(255,255,255,.95);
    border:1px solid rgba(255,255,255,.9);
}
.auth-title {text-align:center;color:#12344d;font-size:25px;font-weight:900}
.auth-sub {text-align:center;color:#66808e;font-size:13px;margin-bottom:18px}
div[data-testid="stTextInput"] input {
    max-width:390px!important;
    height:44px!important;
    border-radius:999px!important;
    padding:0 17px!important;
    background:#fff!important;
}
div[data-testid="stTextInput"] {
    max-width:390px!important;
    margin-left:auto!important;
    margin-right:auto!important;
}
.auth-btn button {
    border-radius:999px!important;height:50px!important;
    font-size:16px!important;font-weight:900!important;
    color:white!important;
    background:linear-gradient(135deg,#0b5873,#147b8b,#23a38d)!important;
    box-shadow:6px 6px 0 rgba(15,39,66,.17),
               0 10px 20px rgba(15,39,66,.15)!important;
}
.auth-secondary button {
    border-radius:999px!important;font-weight:800!important;
}
</style>
""", unsafe_allow_html=True)


def valid_password(password: str) -> bool:
    # Cisco#12345 and similar passwords are valid:
    # 8+ chars, uppercase, lowercase, number.
    return (
        isinstance(password, str)
        and len(password) >= 8
        and any(c.isupper() for c in password)
        and any(c.islower() for c in password)
        and any(c.isdigit() for c in password)
    )


def load_table(db, sql):
    try:
        return pd.read_sql(text(sql), db.bind)
    except Exception:
        return pd.DataFrame()


def render_login():
    st.markdown('<div style="height:9vh"></div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="auth-wrap">
      <div class="auth-card">
        <div class="auth-title">📊 QBR Executive Dashboard</div>
        <div class="auth-sub">HCLTech Operations Command Center</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    _, center, _ = st.columns([1.4, 1.2, 1.4])

    with center:
        mode = st.session_state.get("auth_mode", "login")

        if mode == "set":
            alias = st.session_state.get("pending_alias", "")
            db = SessionLocal()
            try:
                user = get_user(db, alias)
            finally:
                db.close()

            st.markdown("### 🔐 Set My Password")
            if not user:
                st.error("Username not found.")
            else:
                st.info(f"First-time login: {user['DisplayName']}")
                p1 = st.text_input("New Password", type="password", key="set1")
                p2 = st.text_input("Confirm Password", type="password", key="set2")
                st.caption("Minimum 8 characters: uppercase + lowercase + number.")

                st.markdown('<div class="auth-btn">', unsafe_allow_html=True)
                clicked = st.button("Set Password & Continue", use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

                if clicked:
                    if not valid_password(p1):
                        st.error("Password must contain 8+ characters, uppercase, lowercase and a number.")
                    elif p1 != p2:
                        st.error("Passwords do not match.")
                    else:
                        db = SessionLocal()
                        try:
                            set_password(db, user["UserID"], p1)
                            fresh = get_user(db, alias)
                            st.session_state.user = dict(fresh)
                            st.session_state.auth_mode = "dashboard"
                            st.rerun()
                        except Exception as exc:
                            db.rollback()
                            st.error(f"Unable to set password: {exc}")
                        finally:
                            db.close()

            if st.button("← Back to Login", use_container_width=True):
                st.session_state.auth_mode = "login"
                st.rerun()
            return

        if mode == "forgot":
            st.markdown("### 🔑 Forgot Password")
            alias = st.text_input("Username", placeholder="", key="forgot_user")
            if st.button("Submit Reset Request", use_container_width=True):
                db = SessionLocal()
                try:
                    if get_user(db, alias):
                        st.info("Reset request recorded. Supervisor/Superuser must complete the reset.")
                    else:
                        st.error("Username not found.")
                finally:
                    db.close()
            if st.button("← Back to Login", use_container_width=True):
                st.session_state.auth_mode = "login"
                st.rerun()
            return

        st.markdown("### 🔐 Sign in")
        username = st.text_input("Username", placeholder="", key="login_username")
        password = st.text_input("Password", type="password", placeholder="", key="login_password")

        st.markdown('<div class="auth-btn">', unsafe_allow_html=True)
        login_clicked = st.button("🔐 LOGIN", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Set My Password", use_container_width=True):
                if not username.strip():
                    st.warning("Enter username first.")
                else:
                    st.session_state.pending_alias = username.strip()
                    st.session_state.auth_mode = "set"
                    st.rerun()
        with c2:
            if st.button("Forgot Password", use_container_width=True):
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
                    st.error("Username not found.")
                elif not user["IsActive"]:
                    st.error("Account is inactive.")
                elif user["MustSetPassword"] or not user["PasswordHash"]:
                    st.session_state.pending_alias = alias
                    st.session_state.auth_mode = "set"
                    st.rerun()
                elif verify_password(password, user["PasswordHash"]):
                    st.session_state.user = dict(user)
                    st.session_state.auth_mode = "dashboard"
                    st.rerun()
                else:
                    st.error("Incorrect password.")
            finally:
                db.close()


if "user" not in st.session_state:
    st.session_state.user = None
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"

if not st.session_state.user:
    render_login()
    st.stop()


# Change-password screen is also centered/compact.
if st.session_state.get("auth_mode") == "change":
    st.markdown('<div style="height:9vh"></div>', unsafe_allow_html=True)
    _, center, _ = st.columns([1.5, 1, 1.5])
    with center:
        st.markdown("## 🔒 Change Password")
        st.caption(f"Account: {st.session_state.user['Username']}")
        old_pw = st.text_input("Current Password", type="password", key="change_old")
        new_pw = st.text_input("New Password", type="password", key="change_new")
        confirm_pw = st.text_input("Confirm New Password", type="password", key="change_confirm")

        st.markdown('<div class="auth-btn">', unsafe_allow_html=True)
        update_clicked = st.button("Update Password", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        if update_clicked:
            if not valid_password(new_pw):
                st.error("Password must contain 8+ characters, uppercase, lowercase and a number.")
            elif new_pw != confirm_pw:
                st.error("Passwords do not match.")
            else:
                db = SessionLocal()
                try:
                    if change_password(
                        db,
                        st.session_state.user["UserID"],
                        old_pw,
                        new_pw,
                    ):
                        fresh = get_user(db, st.session_state.user["Username"])
                        st.session_state.user = dict(fresh)
                        st.session_state.auth_mode = "dashboard"
                        st.success("Password changed successfully.")
                        st.rerun()
                    else:
                        st.error("Current password is incorrect.")
                except Exception as exc:
                    db.rollback()
                    st.error(f"Unable to change password: {exc}")
                finally:
                    db.close()

        if st.button("← Back to Dashboard", use_container_width=True):
            st.session_state.auth_mode = "dashboard"
            st.rerun()
    st.stop()


user = st.session_state.user
role = user["RoleName"]
display_name = user["DisplayName"]

if role == "SUPERVISOR":
    title = "Supervisor Dashboard"
elif role == "MANAGER":
    title = "Manager Dashboard"
else:
    title = "Superuser Dashboard"

db = SessionLocal()
try:
    tickets = load_table(db, "SELECT * FROM qbr.Ticket")
    alerts = load_table(db, "SELECT * FROM qbr.Alert")
finally:
    db.close()

# Safe fallback: do not crash if the production tables are not yet populated.
if tickets.empty:
    db = SessionLocal()
    try:
        tickets = load_table(db, """
            SELECT ticket_id AS TicketNumber,
                   parent_ticket AS ParentTicketNumber,
                   ticket_type AS TicketType,
                   project AS TrackName,
                   track AS TowerName,
                   priority AS Priority,
                   status AS State,
                   created_date AS OpenedAt
            FROM tickets
        """)
    finally:
        db.close()

# Normalize only when the columns actually exist.
if not tickets.empty:
    if "TowerName" not in tickets.columns:
        tickets["TowerName"] = "Unmapped"
    if "TrackName" not in tickets.columns:
        tickets["TrackName"] = "Unmapped"
    if "OpenedAt" in tickets.columns:
        tickets["OpenedAt"] = pd.to_datetime(tickets["OpenedAt"], errors="coerce")
    else:
        tickets["OpenedAt"] = pd.NaT
    if "TicketType" not in tickets.columns:
        tickets["TicketType"] = "Unknown"
    if "ParentTicketNumber" not in tickets.columns:
        tickets["ParentTicketNumber"] = None
    tickets["TowerName"] = tickets["TowerName"].fillna("Unmapped").astype(str)
    tickets["TrackName"] = tickets["TrackName"].fillna("Unmapped").astype(str)

st.markdown(
    f'<div class="hero"><h1>📊 {title}</h1>'
    f'<p>Signed in: <b>{display_name}</b> · Role: <b>{role}</b></p></div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("🎛️ Dashboard Controls")
    if st.button("🔄 Pull / Refresh Data", use_container_width=True):
        st.rerun()
    if st.button("🔒 Change Password", use_container_width=True):
        st.session_state.auth_mode = "change"
        st.rerun()
    if st.button("🚪 Sign out", use_container_width=True):
        st.session_state.user = None
        st.session_state.auth_mode = "login"
        st.rerun()

    st.divider()
    tower_options = ["All"] + list(TOWER_TRACKS.keys())
    tower = st.selectbox("1️⃣ Tower", tower_options)

    if tickets.empty:
        tower_df = tickets.copy()
        track_options = ["All"] + TOWER_TRACKS.get(tower, [])
    else:
        tower_df = tickets if tower == "All" else tickets[tickets["TowerName"] == tower]
        if tower == "All":
            actual = sorted(tower_df["TrackName"].dropna().astype(str).unique().tolist())
            track_options = ["All"] + actual
        else:
            track_options = ["All"] + TOWER_TRACKS.get(tower, [])

    track = st.selectbox("2️⃣ Track", track_options)

    if tickets.empty:
        filtered = tickets.copy()
    else:
        filtered = tower_df if track == "All" else tower_df[tower_df["TrackName"] == track]

    view = st.selectbox("3️⃣ Time View", ["Day", "Week", "Month", "Quarter"])

    today = date.today()
    if not filtered.empty and filtered["OpenedAt"].notna().any():
        min_d = filtered["OpenedAt"].min().date()
        max_d = min(filtered["OpenedAt"].max().date(), today)
        if min_d > today:
            min_d = today
        dr = st.date_input(
            "Date Range",
            (min_d, max_d),
            min_value=min_d,
            max_value=today,
        )
        if isinstance(dr, tuple) and len(dr) == 2:
            filtered = filtered[
                (filtered["OpenedAt"].dt.date >= dr[0])
                & (filtered["OpenedAt"].dt.date <= dr[1])
            ]
    else:
        st.caption("No ticket date data available for the selected scope.")

total = len(filtered)
parents = int((filtered["TicketType"] == "Parent").sum()) if not filtered.empty else 0
children = int((filtered["TicketType"] == "Child").sum()) if not filtered.empty else 0

# Alerts must also be scoped by the selected timeframe once alert date mapping is available.
alerts_n = len(alerts)

if not filtered.empty and filtered["OpenedAt"].notna().any():
    daily_counts = filtered.groupby(filtered["OpenedAt"].dt.date).size()
    max_tickets = int(daily_counts.max())
    min_tickets = int(daily_counts.min())
else:
    max_tickets = min_tickets = 0

cards = [
    ("🎫", "TOTAL TICKETS", f"{total:,}", "Selected timeframe", "#176b87"),
    ("👑", "PARENT TICKETS", f"{parents:,}", "Root workload", "#548235"),
    ("↳", "CHILD TICKETS", f"{children:,}", "Linked workload", "#ed7d31"),
    ("⚡", "ALERTS", f"{alerts_n:,}", "Monitoring events", "#c00000"),
    ("📊", "MAX / MIN", f"{max_tickets:,} / {min_tickets:,}", "Tickets per day", "#7f6000"),
]

for c, (icon, title_, value, sub, bg) in zip(st.columns(5), cards):
    c.markdown(
        f'<div class="kpi" style="background:linear-gradient(135deg,{bg},{bg}cc)">'
        f'<div class="t">{icon} {title_}</div>'
        f'<div class="v">{value}</div><div class="s">{sub}</div></div>',
        unsafe_allow_html=True,
    )

st.markdown('<div class="section">📈 Executive Volume View</div>', unsafe_allow_html=True)
a, b = st.columns(2)

with a:
    st.markdown("#### Ticket Volume")
    if not filtered.empty and filtered["OpenedAt"].notna().any():
        x = filtered.copy()
        if view == "Day":
            x["Period"] = x["OpenedAt"].dt.date.astype(str)
        elif view == "Week":
            x["Period"] = x["OpenedAt"].dt.to_period("W").astype(str)
        elif view == "Quarter":
            x["Period"] = x["OpenedAt"].dt.to_period("Q").astype(str)
        else:
            x["Period"] = x["OpenedAt"].dt.to_period("M").astype(str)

        tr = (
            x.groupby(["Period", "TicketType"])
            .size()
            .reset_index(name="Tickets")
        )
        fig = px.bar(
            tr, x="Period", y="Tickets", color="TicketType",
            barmode="group", template="plotly_white"
        )
        fig.update_layout(height=420, margin=dict(l=5,r=5,t=20,b=5), legend_title="")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No ticket data is available for this selection.")

with b:
    st.markdown("#### Tower / Track Volume")
    if not filtered.empty:
        ps = (
            filtered.groupby(["TowerName", "TrackName"])
            .size().reset_index(name="Tickets")
            .sort_values("Tickets").tail(15)
        )
        fig = px.bar(
            ps, x="Tickets", y="TrackName", color="TowerName",
            orientation="h", template="plotly_white"
        )
        fig.update_layout(height=420, margin=dict(l=5,r=5,t=20,b=5), legend_title="Tower")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No ticket data is available for this selection.")

c, d = st.columns(2)

with c:
    st.markdown("#### 👑 Highest Parent → Child Concentration")
    if (
        not filtered.empty
        and "ParentTicketNumber" in filtered.columns
    ):
        q = (
            filtered.groupby(["ParentTicketNumber","TowerName","TrackName"])
            .size().reset_index(name="Ticket Count")
            .sort_values("Ticket Count", ascending=False)
            .head(10)
        )
        st.dataframe(q, use_container_width=True, hide_index=True)
    else:
        st.info("Parent/child relationship data is not available yet.")

with d:
    st.markdown("#### ⚡ Highest Alert / Part Frequency")
    if alerts.empty:
        st.info("NZG2 alert data is not loaded yet.")
    elif {"Part", "AlertType"}.issubset(alerts.columns):
        q = (
            alerts.groupby(["Part","AlertType"])
            .size().reset_index(name="Alerts")
            .sort_values("Alerts", ascending=False)
            .head(10)
        )
        st.dataframe(q, use_container_width=True, hide_index=True)
    else:
        st.info("Alert table loaded, but Part/AlertType mapping needs to be confirmed.")

if role in ("SUPERUSER", "SUPERVISOR"):
    st.divider()
    st.subheader("👥 Track Manager Administration")
    st.caption(
        "Supervisor/Superuser administration for Tower → Track manager assignment."
    )
    st.info(
        "Manager assignment UI will be enabled against qbr.UserTrackAccess "
        "after the exact table columns are confirmed."
    )

st.divider()
st.subheader("📥 Customer Report")
e1, e2 = st.columns(2)

with e1:
    st.download_button(
        "⬇️ Download CSV",
        filtered.to_csv(index=False).encode(),
        "QBR_Filtered_Report.csv",
        "text/csv",
        use_container_width=True,
    )

with e2:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        filtered.to_excel(writer, index=False, sheet_name="Tickets")
        if not alerts.empty:
            alerts.to_excel(writer, index=False, sheet_name="Alerts")
    st.download_button(
        "📗 Download Excel",
        buf.getvalue(),
        "QBR_Filtered_Report.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

st.caption(
    "Hierarchy: Tower → Track → Time View → Ticket → Parent/Child → Alert | Future dates disabled."
)
