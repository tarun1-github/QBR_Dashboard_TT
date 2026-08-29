"""
QBR Executive Dashboard - Main Application
===========================================
DB-driven executive dashboard for ticket and alert analytics.
"""

import sys
from pathlib import Path
from datetime import date, datetime, timedelta

# Project path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import text

from app.db import SessionLocal
from app.login_block import (
    render_login,
    render_flash,
    initialise_auth_state,
)
from app.dashboard_data import (
    get_tower_track_hierarchy,
    get_executive_kpis,
    get_tower_track_volume,
    get_daily_trend,
    get_weekly_trend,
    get_monthly_trend,
    get_quarterly_trend,
    get_alert_frequency,
    get_parent_child_relation,
    get_volume_stats,
    get_tower_track_alerts,
)

# Page config
st.set_page_config(
    page_title="QBR Executive Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# Authentication
# ============================================================
initialise_auth_state()

if not st.session_state.user:
    render_flash()
    render_login()
    st.stop()

render_flash()

# Auto-clear flash message after first display
if "flash_message" in st.session_state and st.session_state.flash_message:
    st.session_state.flash_message = None

# ============================================================
# Styling (HCLTech Theme)
# ============================================================
st.markdown(
    """
<style>
/* ---------- Application ---------- */
[data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg,#f5f9fc 0%,#edf5f7 52%,#e4f0f2 100%);
}

[data-testid="stHeader"] {
    background: rgba(255,255,255,0.75);
}

.main .block-container {
    padding-top: 1.1rem;
    padding-bottom: 2rem;
}

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#102f4a 0%,#075b76 50%,#087a78 100%) !important;
    box-shadow: 8px 0 24px rgba(15,39,66,.20);
}

section[data-testid="stSidebar"] > div {
    padding-top: 1.1rem;
}

.qbr-control-title {
    color:#fff !important;
    padding:10px 13px;
    border-radius:14px;
    margin:7px 0 10px;
    background:linear-gradient(135deg,#0b4564,#168a9a,#159c89);
    box-shadow:5px 6px 0 rgba(0,0,0,.18), inset 0 1px 2px rgba(255,255,255,.18);
    font-weight:900;
    letter-spacing:.3px;
}

.qbr-side-label {
    color:#fff !important;
    font-size:12px;
    font-weight:900;
    margin:10px 0 5px;
    letter-spacing:.5px;
}

/* Sidebar buttons */
section[data-testid="stSidebar"] div.stButton > button {
    background:linear-gradient(145deg,#ffffff,#e9f3f5) !important;
    color:#12344d !important;
    border:1px solid #c9dfe6 !important;
    border-radius:18px !important;
    min-height:44px !important;
    font-weight:800 !important;
    box-shadow:5px 6px 0 rgba(0,0,0,.17), 0 10px 18px rgba(0,0,0,.12) !important;
}

section[data-testid="stSidebar"] div.stButton > button:hover {
    background:linear-gradient(145deg,#dff7f4,#ffffff) !important;
    transform:translateY(-1px);
}

/* Sidebar inputs */
section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
    background:#fff !important;
    color:#12344d !important;
    border-radius:15px !important;
    border:1px solid #c9dfe6 !important;
}

section[data-testid="stSidebar"] [data-testid="stDateInput"] input {
    background:#fff !important;
    color:#12344d !important;
    border-radius:15px !important;
    border:1px solid #c9dfe6 !important;
    font-weight:700 !important;
}

/* ---------- Hero ---------- */
.qbr-hero {
    padding:22px 28px;
    border-radius:24px;
    background:linear-gradient(135deg,#0e2d49,#146b86,#22a48e);
    color:#fff;
    box-shadow:0 15px 32px rgba(15,39,66,.24), 7px 7px 0 rgba(15,39,66,.12);
    margin-bottom:18px;
}

.qbr-hero h1 {
    margin:0;
    font-size:34px;
    font-family:"Segoe UI","Aptos",sans-serif;
    font-weight:900;
}

.qbr-hero p {
    margin:6px 0 0;
    font-size:14px;
    opacity:.94;
}

/* ---------- KPI Cards (3D Style) ---------- */
.qbr-kpi {
    border-radius:22px;
    padding:18px 20px;
    min-height:120px;
    color:#fff;
    box-shadow:0 12px 24px rgba(15,39,66,.20), 
               0 6px 12px rgba(15,39,66,.15),
               inset 0 1px 0 rgba(255,255,255,.25);
    border:1px solid rgba(255,255,255,.30);
    transition: all 0.3s ease;
    background-size: 200% 200%;
    animation: gradientShift 6s ease infinite;
}

@keyframes gradientShift {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

.qbr-kpi:hover {
    transform: translateY(-6px) scale(1.02);
    box-shadow:0 18px 36px rgba(15,39,66,.25),
               0 8px 16px rgba(15,39,66,.20);
}

.qbr-kpi .t {
    font-size:11px;
    font-weight:800;
    letter-spacing:.6px;
    text-transform:uppercase;
}

.qbr-kpi .v {
    font-size:32px;
    font-weight:900;
    margin-top:8px;
    text-shadow:0 2px 4px rgba(0,0,0,.15);
    font-family:"Segoe UI","Aptos",sans-serif;
}

.qbr-kpi .s {
    font-size:10px;
    opacity:.95;
    font-weight:600;
}

/* ---------- 3D Buttons ---------- */
.stButton > button,
.stDownloadButton > button {
    border-radius:16px !important;
    font-weight:800 !important;
    font-size:14px !important;
    box-shadow:0 6px 0 rgba(15,39,66,.20),
               0 8px 16px rgba(15,39,66,.15) !important;
    transition: all 0.15s ease !important;
    border:1px solid rgba(255,255,255,.30) !important;
}

.stButton > button:hover,
.stDownloadButton > button:hover {
    transform:translateY(-3px) !important;
    box-shadow:0 9px 0 rgba(15,39,66,.20),
               0 12px 24px rgba(15,39,66,.20) !important;
}

.stButton > button:active,
.stDownloadButton > button:active {
    transform:translateY(3px) !important;
    box-shadow:0 3px 0 rgba(15,39,66,.20),
               0 4px 8px rgba(15,39,66,.15) !important;
}

/* ---------- Section Headings ---------- */
.qbr-section {
    font-size:24px;
    font-weight:900;
    color:#12344d;
    margin:18px 0 8px;
    padding:8px 16px;
    border-radius:14px;
    background:linear-gradient(135deg,#e8f4f6,#ffffff);
    border:1px solid #d5e5e9;
    box-shadow:3px 4px 0 rgba(15,39,66,.08);
    font-family:"Segoe UI","Aptos",sans-serif;
}

/* ---------- Charts ---------- */
.js-plotly-plot {
    border-radius:18px;
    overflow:hidden;
    box-shadow:0 8px 24px rgba(15,39,66,.12);
}

/* ---------- Metrics ---------- */
[data-testid="stMetric"] {
    background:linear-gradient(145deg,#ffffff,#e8f4f6);
    border-radius:16px;
    padding:12px 16px;
    box-shadow:0 6px 18px rgba(15,39,66,.10);
    border:1px solid #d5e5e9;
}

[data-testid="stMetric"] label {
    font-weight:800 !important;
    color:#12344d !important;
}

[data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-size:24px !important;
    font-weight:900 !important;
    color:#0e2d49 !important;
}

/* ---------- Toast Messages ---------- */
.qbr-toast {
    display:flex;
    align-items:center;
    gap:12px;
    margin:10px auto 16px;
    padding:12px 16px;
    border-radius:15px;
    max-width:900px;
    box-shadow:6px 7px 0 rgba(15,39,66,.12), 0 10px 22px rgba(15,39,66,.08);
}

.qbr-toast-icon {
    width:31px;
    height:31px;
    min-width:31px;
    border-radius:50%;
    display:flex;
    align-items:center;
    justify-content:center;
    color:#fff;
    font-weight:900;
}

.qbr-toast.success {
    background:linear-gradient(135deg,#e8faef,#c9f1dc);
    border:1px solid #76c993;
    color:#12623a;
}
.qbr-toast.success .qbr-toast-icon {
    background:linear-gradient(145deg,#11834a,#20a464);
}

.qbr-toast.error {
    background:linear-gradient(135deg,#fff1f1,#ffdddd);
    border:1px solid #e58b8b;
    color:#9d2020;
}
.qbr-toast.error .qbr-toast-icon {
    background:linear-gradient(145deg,#c51f1f,#ee4b4b);
}

.qbr-toast.info {
    background:linear-gradient(135deg,#eaf5ff,#d8ecff);
    border:1px solid #7eb5e8;
    color:#185486;
}
.qbr-toast.info .qbr-toast-icon {
    background:linear-gradient(145deg,#176b9b,#2b91c4);
}

/* ---------- Buttons ---------- */
.stButton > button,
.stDownloadButton > button {
    border-radius:14px !important;
    font-weight:800 !important;
    box-shadow:4px 5px 0 rgba(15,39,66,.14) !important;
}

/* ---------- Tables ---------- */
div[data-testid="stDataFrame"] {
    border-radius:14px;
    overflow:hidden;
}

footer { visibility:hidden; }
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# Helper Functions
# ============================================================
def success_message(title: str, detail: str = ""):
    st.markdown(
        f"""
        <div class="qbr-toast success">
            <div class="qbr-toast-icon">✓</div>
            <div><b>{title}</b>{f"<span>{detail}</span>" if detail else ""}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def error_message(title: str, detail: str = ""):
    st.markdown(
        f"""
        <div class="qbr-toast error">
            <div class="qbr-toast-icon">!</div>
            <div><b>{title}</b>{f"<span>{detail}</span>" if detail else ""}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def info_message(title: str, detail: str = ""):
    st.markdown(
        f"""
        <div class="qbr-toast info">
            <div class="qbr-toast-icon">i</div>
            <div><b>{title}</b>{f"<span>{detail}</span>" if detail else ""}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def selected_user():
    return st.session_state.get("user") or {}


def role_of_user():
    u = selected_user()
    return str(u.get("RoleName") or u.get("role") or "").upper()


def username_of_user():
    u = selected_user()
    return str(u.get("Username") or u.get("username") or "")


def display_name_of_user():
    u = selected_user()
    return str(u.get("DisplayName") or u.get("name") or "")


# ============================================================
# Get DB-Driven Configuration
# ============================================================
TOWER_TRACKS = get_tower_track_hierarchy()

# ============================================================
# User and Title
# ============================================================
role = role_of_user()
display_name = display_name_of_user()

if role == "SUPERVISOR":
    dashboard_title = "Supervisor Dashboard"
elif role == "MANAGER":
    dashboard_title = "Manager Dashboard"
else:
    dashboard_title = "Superuser Dashboard"

st.markdown(
    f"""
    <div class="qbr-hero">
        <h1>📊 QBR Executive Dashboard</h1>
        <p>{dashboard_title} &nbsp;•&nbsp;
        Signed in: <b>{display_name}</b> &nbsp;•&nbsp;
        Role: <b>{role}</b></p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# Sidebar Navigation
# ============================================================
with st.sidebar:
    st.markdown(
        '<div class="qbr-control-title">🎛️ QBR DASHBOARD CONTROLS</div>',
        unsafe_allow_html=True,
    )

    if st.button("🔄 Pull / Refresh Data", use_container_width=True):
        st.session_state.flash_message = (
            "Data refreshed successfully.",
            "Latest available CPDB data has been reloaded.",
        )
        st.rerun()

    if st.button("🔐 Change Password", use_container_width=True):
        st.session_state.auth_mode = "change"
        st.rerun()

    if st.button("🚪 Sign out", use_container_width=True):
        st.session_state.user = None
        st.session_state.auth_mode = "login"
        st.rerun()

    st.divider()

    # Tower Selection
    st.markdown(
        '<div class="qbr-control-title">1️⃣ TOWER</div>',
        unsafe_allow_html=True,
    )

    tower_options = ["All"] + list(TOWER_TRACKS.keys())
    tower = st.selectbox(
        "Tower",
        tower_options,
        label_visibility="collapsed",
        key="nav_tower",
    )

    # Track Selection
    st.markdown(
        '<div class="qbr-control-title">2️⃣ TRACK</div>',
        unsafe_allow_html=True,
    )

    if tower == "All":
        track_options = []
        for track_list in TOWER_TRACKS.values():
            track_options.extend(track_list)
        track_options = sorted(set(track_options))
    else:
        track_options = TOWER_TRACKS.get(tower, [])

    track = st.selectbox(
        "Track",
        ["All"] + track_options,
        label_visibility="collapsed",
        key="nav_track",
    )

    # Time View Selection
    st.markdown(
        '<div class="qbr-control-title">3️⃣ TIME VIEW</div>',
        unsafe_allow_html=True,
    )

    view = st.selectbox(
        "Time View",
        ["Day", "Week", "Month", "Quarter"],
        index=2,
        label_visibility="collapsed",
        key="nav_time_view",
    )

    # Date Range Selection
    st.markdown(
        '<div class="qbr-control-title">📅 REPORT DATE RANGE</div>',
        unsafe_allow_html=True,
    )

    # Get available date range from data
    db_date = SessionLocal()
    try:
        date_range = db_date.execute(text("""
            SELECT MIN(OpenedAt) as min_date, MAX(OpenedAt) as max_date 
            FROM qbr.Ticket WHERE OpenedAt IS NOT NULL
        """)).fetchone()
        
        if date_range and date_range[0]:
            data_start = date_range[0].date() if hasattr(date_range[0], 'date') else date(2026, 7, 1)
            data_end = date_range[1].date() if hasattr(date_range[1], 'date') else date(2026, 7, 31)
        else:
            data_start = date(2026, 7, 1)
            data_end = date(2026, 7, 31)
    except:
        data_start = date(2026, 7, 1)
        data_end = date(2026, 7, 31)
    finally:
        db_date.close()

    dr = st.date_input(
        "Report Date Range",
        value=(data_start, data_end),
        min_value=date(2020, 1, 1),
        max_value=date.today(),
        key="report_date_range",
        label_visibility="collapsed",
    )

# ============================================================
# Process Filters
# ============================================================
start_date = None
end_date = None
tower_id = None
track_id = None

if isinstance(dr, tuple) and len(dr) == 2:
    start_date = datetime.combine(dr[0], datetime.min.time())
    end_date = datetime.combine(dr[1], datetime.max.time())

# Get Tower/Track IDs if selected
if tower != "All" or track != "All":
    db = SessionLocal()
    try:
        if tower != "All":
            result = db.execute(
                text("SELECT TowerID FROM qbr.Tower WHERE TowerName = :name"),
                {"name": tower}
            ).first()
            if result:
                tower_id = result[0]

        if track != "All":
            result = db.execute(
                text("SELECT TrackID FROM qbr.Track WHERE TrackName = :name"),
                {"name": track}
            ).first()
            if result:
                track_id = result[0]
    finally:
        db.close()

# ============================================================
# Load Data from Database
# ============================================================
kpis = get_executive_kpis(start_date, end_date, tower_id, track_id)
volume_df = get_tower_track_volume(start_date, end_date)
alert_freq_df = get_alert_frequency(start_date, end_date, tower_id, track_id)
parent_child_df = get_parent_child_relation(start_date, end_date, tower_id, track_id)
volume_stats = get_volume_stats(start_date, end_date, tower_id, track_id)

# Filter volume dataframe by tower/track selection
if tower != "All" and not volume_df.empty:
    volume_df = volume_df[volume_df['Tower'] == tower]
if track != "All" and not volume_df.empty:
    volume_df = volume_df[volume_df['Track'] == track]

# ============================================================
# Executive KPI Cards - Enhanced 3D Style
# ============================================================
st.markdown(
    '<div class="qbr-section">📈 Executive KPIs</div>',
    unsafe_allow_html=True,
)

# Row 1: Main KPIs with enhanced gradients
c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    st.markdown(
        f"""
        <div class="qbr-kpi" style="background:linear-gradient(135deg,#0e2d49,#146b86,#22a48e)">
            <div class="t">🎫 TOTAL TICKETS</div>
            <div class="v">{kpis['total']:,}</div>
            <div class="s">Selected timeframe</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c2:
    st.markdown(
        f"""
        <div class="qbr-kpi" style="background:linear-gradient(135deg,#2d7d9a,#4a9ab5,#6bb8d0)">
            <div class="t">👑 PARENT TICKETS</div>
            <div class="v">{kpis['parents']:,}</div>
            <div class="s">Root workload</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c3:
    st.markdown(
        f"""
        <div class="qbr-kpi" style="background:linear-gradient(135deg,#ee8233,#f5a85c,#f9c98a)">
            <div class="t">↳ CHILD TICKETS</div>
            <div class="v">{kpis['children']:,}</div>
            <div class="s">Linked workload</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c4:
    total_alerts = len(alert_freq_df) if not alert_freq_df.empty else 0
    st.markdown(
        f"""
        <div class="qbr-kpi" style="background:linear-gradient(135deg,#c91414,#e84444,#f07070)">
            <div class="t">⚡ ALERTS</div>
            <div class="v">{total_alerts:,}</div>
            <div class="s">Monitoring events</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c5:
    max_vol = volume_stats['max_count'] if volume_stats else 0
    min_vol = volume_stats['min_count'] if volume_stats else 0
    st.markdown(
        f"""
        <div class="qbr-kpi" style="background:linear-gradient(135deg,#8a6b09,#b89428,#d4b34a)">
            <div class="t">📊 MAX / MIN</div>
            <div class="v">{max_vol:,} / {min_vol:,}</div>
            <div class="s">Tickets per day</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Row 2: Additional KPIs with vibrant colors
st.write("")
c6, c7, c8, c9 = st.columns(4)

with c6:
    st.markdown(
        f"""
        <div class="qbr-kpi" style="background:linear-gradient(135deg,#3b5998,#5a7bc8,#8b9dc3)">
            <div class="t">📈 AVG TICKETS/DAY</div>
            <div class="v">{volume_stats['avg_count'] if volume_stats else 0:,.1f}</div>
            <div class="s">Daily average</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c7:
    open_tickets = kpis['total'] - kpis['closed']
    st.markdown(
        f"""
        <div class="qbr-kpi" style="background:linear-gradient(135deg,#1e88e5,#5ab1f5,#81d4fa)">
            <div class="t">🔵 OPEN TICKETS</div>
            <div class="v">{open_tickets:,}</div>
            <div class="s">Awaiting resolution</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c8:
    st.markdown(
        f"""
        <div class="qbr-kpi" style="background:linear-gradient(135deg,#43a047,#66bb6a,#a5d6a7)">
            <div class="t">✅ CLOSED TICKETS</div>
            <div class="v">{kpis['closed']:,}</div>
            <div class="s">Successfully resolved</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c9:
    st.markdown(
        f"""
        <div class="qbr-kpi" style="background:linear-gradient(135deg,#d32f2f,#ef5350,#ef9a9a)">
            <div class="t">🔴 CRITICAL</div>
            <div class="v">{kpis['critical']:,}</div>
            <div class="s">Critical priority</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ============================================================
# Volume Statistics Insights - Enhanced
# ============================================================
if volume_stats:
    st.markdown(
        f"""
        <div style="margin:15px 0; padding:14px 18px; border-radius:16px;
                    background:linear-gradient(135deg,#e8f5e9,#f1f8e9,#fffde7);
                    border:1px solid #c8e6c9; color:#1b5e20;
                    box-shadow:0 4px 12px rgba(0,0,0,0.08); font-size:13px; font-weight:700;">
            📊 <b>Volume Insights:</b> Highest volume on <b>{volume_stats['max_day']}</b> ({volume_stats['max_date']}) with <b>{volume_stats['max_count']}</b> tickets &nbsp;|&nbsp;
            Lowest on <b>{volume_stats['min_day']}</b> ({volume_stats['min_date']}) with <b>{volume_stats['min_count']}</b> tickets &nbsp;|&nbsp;
            Average: <b>{volume_stats['avg_count']:.1f}</b> tickets/day
        </div>
        """,
        unsafe_allow_html=True,
    )

# ============================================================
# Trend Charts - Enhanced Styling
# ============================================================
st.markdown(
    '<div class="qbr-section">📈 Trend Analysis</div>',
    unsafe_allow_html=True,
)

# Get trend data based on time view
if view == "Day":
    trend_df = get_daily_trend(start_date, end_date, tower_id, track_id)
    x_col = "Date"
elif view == "Week":
    trend_df = get_weekly_trend(start_date, end_date, tower_id, track_id)
    x_col = "Week"
elif view == "Month":
    trend_df = get_monthly_trend(start_date, end_date, tower_id, track_id)
    x_col = "Month"
else:  # Quarter
    trend_df = get_quarterly_trend(start_date, end_date, tower_id, track_id)
    x_col = "Quarter"

col1, col2 = st.columns(2)

with col1:
    st.markdown("### 📊 Ticket Volume Trend")
    if not trend_df.empty:
        # Create enhanced bar chart with better colors
        fig = px.bar(
            trend_df,
            x=x_col,
            y=["Parents", "Children"] if "Parents" in trend_df.columns else "Total",
            barmode="group",
            template="plotly_white",
            color_discrete_map={"Parents": "#2d7d9a", "Children": "#ee8233", "Total": "#19708b"},
        )
        fig.update_layout(
            height=400,
            margin=dict(l=10, r=10, t=30, b=10),
            legend_title="",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(245,249,252,0.8)",
            font=dict(family="Segoe UI, Aptos, sans-serif", size=12),
            xaxis=dict(gridcolor="rgba(0,0,0,0.05)", showline=True, linecolor="rgba(0,0,0,0.1)"),
            yaxis=dict(gridcolor="rgba(0,0,0,0.05)", showline=True, linecolor="rgba(0,0,0,0.1)"),
        )
        fig.update_traces(marker_line_width=1, marker_line_color="rgba(255,255,255,0.5)")
        st.plotly_chart(fig, use_container_width=True, key="trend_chart")
    else:
        st.info("No trend data available for selected filters.")

with col2:
    st.markdown("### 🏢 Tower/Track Volume")
    if not volume_df.empty:
        # Create enhanced horizontal bar chart
        colors = ["#19708b", "#2d7d9a", "#5b8f3b", "#ee8233", "#c91414", "#8a6b09", "#6b4f8f"]
        fig = px.bar(
            volume_df.head(15),
            x="Total",
            y="Track",
            color="Tower",
            orientation="h",
            template="plotly_white",
            color_discrete_sequence=colors,
        )
        fig.update_layout(
            height=400,
            margin=dict(l=10, r=10, t=30, b=10),
            legend_title="Tower",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(245,249,252,0.8)",
            font=dict(family="Segoe UI, Aptos, sans-serif", size=12),
            xaxis=dict(gridcolor="rgba(0,0,0,0.05)", showline=True, linecolor="rgba(0,0,0,0.1)"),
            yaxis=dict(showline=True, linecolor="rgba(0,0,0,0.1)"),
        )
        fig.update_traces(marker_line_width=1, marker_line_color="rgba(255,255,255,0.5)")
        st.plotly_chart(fig, use_container_width=True, key="volume_chart")
    else:
        st.info("No volume data available for selected filters.")

# ============================================================
# Parent-Child & Alert Frequency
# ============================================================
st.markdown(
    '<div class="qbr-section">👑 Parent-Child & Alert Analysis</div>',
    unsafe_allow_html=True,
)

col3, col4 = st.columns(2)

with col3:
    st.markdown("### Highest Parent → Child Concentration")
    if not parent_child_df.empty:
        st.dataframe(
            parent_child_df.head(10),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No parent-child data available.")

with col4:
    st.markdown("### Highest Alert / Part Frequency")
    if not alert_freq_df.empty:
        st.dataframe(
            alert_freq_df.head(10),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No alert data available.")

# ============================================================
# Tower/Track Alert Summary
# ============================================================
st.markdown(
    '<div class="qbr-section">⚡ Tower/Track Alert Summary</div>',
    unsafe_allow_html=True,
)

alert_summary_df = get_tower_track_alerts(start_date, end_date)
if not alert_summary_df.empty:
    st.dataframe(
        alert_summary_df,
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No alert summary data available.")

# ============================================================
# Executive Summary
# ============================================================
st.markdown(
    '<div class="qbr-section">📌 Executive Summary</div>',
    unsafe_allow_html=True,
)

s1, s2, s3 = st.columns(3)

with s1:
    st.metric("Average Tickets / Day", f"{volume_stats['avg_count'] if volume_stats else 0:,.1f}")

with s2:
    if not volume_df.empty and 'Total' in volume_df.columns:
        top_track = volume_df.loc[volume_df['Total'].idxmax()]
        st.metric("Highest Volume Track", top_track['Track'], f"{top_track['Total']:,} tickets")
    else:
        st.metric("Highest Volume Track", "N/A")

with s3:
    if not alert_freq_df.empty and 'Count' in alert_freq_df.columns:
        top_part = alert_freq_df.loc[alert_freq_df['Count'].idxmax()]
        st.metric("Highest Alert Part", top_part['Part'], f"{top_part['Count']:,} alerts")
    else:
        st.metric("Highest Alert Part", "N/A")

# ============================================================
# Customer Report Download
# ============================================================
st.divider()
st.markdown(
    '<div class="qbr-section">📥 Customer Report</div>',
    unsafe_allow_html=True,
)

report_name = st.text_input(
    "Report Name",
    value="QBR Executive Report",
    key="report_name",
)

report_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
csv_name = f"{report_name.strip() or 'QBR_Executive_Report'}_{report_stamp}.csv"
excel_name = f"{report_name.strip() or 'QBR_Executive_Report'}_{report_stamp}.xlsx"

e1, e2 = st.columns(2)

with e1:
    # Create CSV from volume data
    if not volume_df.empty:
        csv_data = volume_df.to_csv(index=False).encode("utf-8")
    else:
        csv_data = b"No data available"
    
    st.download_button(
        "⬇️ Download CSV",
        csv_data,
        csv_name,
        "text/csv",
        use_container_width=True,
    )

with e2:
    # Create Excel report
    import io
    excel_buffer = io.BytesIO()
    
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        # Use filtered data for all sheets
        filtered_volume = volume_df.copy() if not volume_df.empty else pd.DataFrame()
        filtered_alerts = alert_freq_df.copy() if not alert_freq_df.empty else pd.DataFrame()
        filtered_parent_child = parent_child_df.copy() if not parent_child_df.empty else pd.DataFrame()
        
        if not filtered_volume.empty:
            filtered_volume.to_excel(writer, index=False, sheet_name="Tower Track Volume")
        if not filtered_alerts.empty:
            filtered_alerts.to_excel(writer, index=False, sheet_name="Alert Frequency")
        if not filtered_parent_child.empty:
            filtered_parent_child.to_excel(writer, index=False, sheet_name="Parent-Child")
        
        # Summary sheet with current filtered data
        summary_df = pd.DataFrame([
            ["Report Name", report_name],
            ["Report Date", datetime.now().strftime("%Y-%m-%d %H:%M")],
            ["Date Range", f"{start_date.strftime('%Y-%m-%d') if start_date else 'All'} to {end_date.strftime('%Y-%m-%d') if end_date else 'All'}"],
            ["Tower", tower],
            ["Track", track],
            ["", ""],
            ["Total Tickets", kpis['total']],
            ["Parent Tickets", kpis['parents']],
            ["Child Tickets", kpis['children']],
            ["Closed Tickets", kpis['closed']],
            ["Open Tickets", kpis['total'] - kpis['closed']],
            ["Critical Priority", kpis['critical']],
            ["High Priority", kpis['high']],
            ["Moderate Priority", kpis['moderate']],
            ["", ""],
            ["Total Alerts", len(alert_freq_df) if not alert_freq_df.empty else 0],
        ], columns=["Metric", "Value"])
        summary_df.to_excel(writer, index=False, sheet_name="Executive Summary")
    
    st.download_button(
        "📗 Download Excel",
        excel_buffer.getvalue(),
        excel_name,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

st.caption(
    "Hierarchy: Tower → Track → Time View → Date Range → "
    "Tickets → Parent/Child → Alerts | Future dates disabled."
)
