"""QBR Executive Dashboard - CPDB-driven customer operations command center."""
from __future__ import annotations
import io,sys
from datetime import date,datetime
from pathlib import Path
PROJECT_ROOT=Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:sys.path.insert(0,str(PROJECT_ROOT))
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import text
from app.db import SessionLocal
from app.auth import change_password
from app.login_block import render_login,render_flash,initialise_auth_state,clear_session
from app.dashboard_data import get_tower_track_hierarchy,get_executive_kpis,get_alert_total,get_tower_track_volume,get_daily_trend,get_weekly_trend,get_monthly_trend,get_quarterly_trend,get_alert_frequency,get_parent_child_relation,get_volume_stats,get_tower_track_alerts

st.set_page_config(page_title="QBR Executive Dashboard",page_icon="📊",layout="wide",initial_sidebar_state="expanded")
initialise_auth_state()
if not st.session_state.get("user"):
    render_flash();render_login()
if not st.session_state.get("user"):st.stop()
render_flash()

st.markdown("""<style>
[data-testid="stAppViewContainer"]{background:linear-gradient(180deg,#f8fbfc 0%,#edf6f8 55%,#e5f1f4 100%)}
.main .block-container{padding:1rem 1.5rem 3rem;max-width:1700px}
section[data-testid="stSidebar"]{background:linear-gradient(180deg,#082f4d,#075d76 55%,#087d78)!important;box-shadow:10px 0 28px rgba(5,36,56,.22)}
.qbr-side-title{color:#fff;font-weight:1000;letter-spacing:.6px;border-radius:16px;padding:12px 14px;margin:5px 0 12px;background:linear-gradient(135deg,#0b4969,#1097a0,#18ad8a);box-shadow:0 7px 0 rgba(0,0,0,.16)}
.qbr-side-head{color:#e8ffff;font-size:11px;font-weight:1000;letter-spacing:.7px;border-radius:12px;padding:8px 11px;margin:13px 0 6px;background:rgba(11,143,151,.8)}
section[data-testid="stSidebar"] .stButton>button{border-radius:13px!important;background:linear-gradient(145deg,#fff,#e2f0f3)!important;color:#12344d!important;font-weight:900!important;box-shadow:4px 5px 0 rgba(0,0,0,.15)!important;border:1px solid #c4dce3!important}
section[data-testid="stSidebar"] div[data-baseweb="select"]>div,section[data-testid="stSidebar"] input{border-radius:12px!important;background:#fff!important;color:#12344d!important;border:1px solid #cfe2e7!important}
.qbr-hero{padding:23px 28px;border-radius:25px;background:linear-gradient(135deg,#082c49,#0e6783 52%,#19a78e);color:#fff;box-shadow:0 14px 30px rgba(8,44,73,.21),7px 8px 0 rgba(8,44,73,.11);margin-bottom:15px}.qbr-hero h1{margin:0;font:1000 34px 'Segoe UI',Aptos,sans-serif}.qbr-hero p{margin:7px 0 0;font-size:13px}
.qbr-section{font:1000 20px 'Segoe UI',Aptos,sans-serif;color:#12344d;margin:19px 0 9px;padding:10px 14px;border-radius:15px;background:#fff;border:1px solid #d6e6ea;box-shadow:4px 5px 0 rgba(15,39,66,.07)}
.qbr-kpi{min-height:105px;padding:16px;border-radius:20px;color:#fff;box-shadow:0 10px 22px rgba(15,39,66,.15),5px 6px 0 rgba(15,39,66,.09)}.qbr-kpi .t{font-size:10px;font-weight:1000;letter-spacing:.5px}.qbr-kpi .v{font-size:31px;font-weight:1000;margin-top:7px;text-shadow:0 2px 4px rgba(0,0,0,.18)}.qbr-kpi .s{font-size:10px;opacity:.94}
.qbr-card{padding:10px 13px;border-radius:18px;background:#fff;border:1px solid #d6e6ea;box-shadow:0 8px 20px rgba(15,39,66,.07)}
.qbr-alert-stat{padding:13px 15px;border-radius:16px;background:linear-gradient(145deg,#fff,#f1f8fa);border:1px solid #d5e7eb;box-shadow:4px 5px 0 rgba(15,39,66,.08)}.qbr-alert-stat .n{font-size:26px;font-weight:1000;color:#12344d}.qbr-alert-stat .l{font-size:10px;font-weight:900;color:#607b87;text-transform:uppercase;letter-spacing:.5px}
.js-plotly-plot{border-radius:16px;overflow:hidden;border:1px solid #d8e8eb;box-shadow:0 7px 18px rgba(15,39,66,.07);background:#fff}
.qbr-msg{padding:12px 15px;border-radius:14px;margin:8px 0;box-shadow:3px 4px 0 rgba(15,39,66,.08);font-weight:800}.ok{background:#e7faef;border:1px solid #68c98d;color:#12623a}.bad{background:#fff0f0;border:1px solid #df8a8a;color:#982323}.inf{background:#eaf5ff;border:1px solid #7fb8e8;color:#185486}
.qbr-pill{display:inline-block;padding:5px 10px;border-radius:999px;font-weight:900;font-size:10px;margin:2px 4px 2px 0;box-shadow:2px 3px 0 rgba(15,39,66,.08)}
.qbr-volume-note{font-size:11px;color:#557789;margin:2px 0 8px;font-weight:700}
footer{visibility:hidden}
</style>""",unsafe_allow_html=True)

def msg(kind,title,detail=""):
    cls={"ok":"ok","bad":"bad","inf":"inf"}.get(kind,"inf");icon={"ok":"✓","bad":"!","inf":"i"}.get(kind,"i");st.markdown(f'<div class="qbr-msg {cls}">{icon}&nbsp;&nbsp;<b>{title}</b> {detail}</div>',unsafe_allow_html=True)
def user():return st.session_state.user or {}
def role():return str(user().get("RoleName") or user().get("role") or "").upper()
def uname():return str(user().get("Username") or user().get("username") or "")
def dname():return str(user().get("DisplayName") or user().get("name") or uname())

def assigned_tracks(username):
    db=SessionLocal()
    try:
        cols={str(r[0]) for r in db.execute(text("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='qbr' AND TABLE_NAME='UserTrackAccess'")).fetchall()}
        q="SELECT tt.TowerName,tt.TrackName FROM qbr.UserTrackAccess a JOIN qbr.AppUser u ON u.UserID=a.UserID JOIN qbr.TowerTrack tt ON tt.TowerTrackID=a.TowerTrackID WHERE LOWER(u.Username)=LOWER(:u) AND ISNULL(tt.IsActive,1)=1 ORDER BY tt.TowerName,tt.TrackName" if "TowerTrackID" in cols else "SELECT t.TowerName,tr.TrackName FROM qbr.UserTrackAccess a JOIN qbr.AppUser u ON u.UserID=a.UserID JOIN qbr.Track tr ON tr.TrackID=a.TrackID JOIN qbr.Tower t ON t.TowerID=tr.TowerID WHERE LOWER(u.Username)=LOWER(:u) AND ISNULL(tr.IsActive,1)=1 ORDER BY t.TowerName,tr.TrackName"
        return [(r[0],r[1]) for r in db.execute(text(q),{"u":username}).fetchall()]
    finally:db.close()

def admin_rows():
    db=SessionLocal()
    try:
        cols={str(r[0]) for r in db.execute(text("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='qbr' AND TABLE_NAME='UserTrackAccess'")).fetchall()}
        q="SELECT u.DisplayName,u.Username,u.RoleName,tt.TowerName,tt.TrackName,uta.CanView,uta.CanExport,uta.CanManage FROM qbr.UserTrackAccess uta JOIN qbr.AppUser u ON u.UserID=uta.UserID JOIN qbr.TowerTrack tt ON tt.TowerTrackID=uta.TowerTrackID WHERE ISNULL(tt.IsActive,1)=1 ORDER BY tt.TowerName,tt.TrackName,u.DisplayName" if "TowerTrackID" in cols else "SELECT u.DisplayName,u.Username,u.RoleName,t.TowerName,tr.TrackName,uta.CanView,uta.CanExport,uta.CanManage FROM qbr.UserTrackAccess uta JOIN qbr.AppUser u ON u.UserID=uta.UserID JOIN qbr.Track tr ON tr.TrackID=uta.TrackID JOIN qbr.Tower t ON t.TowerID=tr.TowerID WHERE ISNULL(tr.IsActive,1)=1 ORDER BY t.TowerName,tr.TrackName,u.DisplayName"
        return db.execute(text(q)).mappings().all()
    finally:db.close()

def manager_users():
    db=SessionLocal()
    try:return db.execute(text("SELECT UserID,Username,DisplayName,RoleName,IsActive FROM qbr.AppUser WHERE IsActive=1 ORDER BY DisplayName")).mappings().all()
    finally:db.close()

def _assignment_target(db,tower,track):
    cols={str(r[0]) for r in db.execute(text("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='qbr' AND TABLE_NAME='UserTrackAccess'")).fetchall()}
    if "TowerTrackID" in cols:return db.execute(text("SELECT TowerTrackID FROM qbr.TowerTrack WHERE TowerName=:t AND TrackName=:tr AND ISNULL(IsActive,1)=1"),{"t":tower,"tr":track}).scalar(),"TowerTrackID"
    return db.execute(text("SELECT tr.TrackID FROM qbr.Track tr JOIN qbr.Tower t ON t.TowerID=tr.TowerID WHERE t.TowerName=:t AND tr.TrackName=:tr AND ISNULL(tr.IsActive,1)=1"),{"t":tower,"tr":track}).scalar(),"TrackID"

def assign_manager(username,tower,track):
    db=SessionLocal()
    try:
        u=db.execute(text("SELECT UserID,DisplayName,RoleName FROM qbr.AppUser WHERE LOWER(Username)=LOWER(:u)"),{"u":username}).mappings().first();target,target_col=_assignment_target(db,tower,track)
        if not u or not target:return False,"User or Tower → Track not found."
        if str(u["RoleName"]).upper()!="MANAGER":return False,f'{u["DisplayName"]} current role is {u["RoleName"]}. Change the role to MANAGER first.'
        if target_col=="TowerTrackID":
            existing=db.execute(text("SELECT TOP 1 u.DisplayName,tt.TowerName,tt.TrackName FROM qbr.UserTrackAccess a JOIN qbr.AppUser u ON u.UserID=a.UserID JOIN qbr.TowerTrack tt ON tt.TowerTrackID=a.TowerTrackID WHERE a.UserID=:uid"),{"uid":u["UserID"]}).mappings().first();occupied=db.execute(text("SELECT TOP 1 u.DisplayName FROM qbr.UserTrackAccess a JOIN qbr.AppUser u ON u.UserID=a.UserID WHERE a.TowerTrackID=:target AND UPPER(u.RoleName)='MANAGER'"),{"target":target}).mappings().first()
        else:
            existing=db.execute(text("SELECT TOP 1 u.DisplayName,t.TowerName,tr.TrackName FROM qbr.UserTrackAccess a JOIN qbr.AppUser u ON u.UserID=a.UserID JOIN qbr.Track tr ON tr.TrackID=a.TrackID JOIN qbr.Tower t ON t.TowerID=tr.TowerID WHERE a.UserID=:uid"),{"uid":u["UserID"]}).mappings().first();occupied=db.execute(text("SELECT TOP 1 u.DisplayName FROM qbr.UserTrackAccess a JOIN qbr.AppUser u ON u.UserID=a.UserID WHERE a.TrackID=:target AND UPPER(u.RoleName)='MANAGER'"),{"target":target}).mappings().first()
        if existing:return False,f'{u["DisplayName"]} is already assigned to {existing["TowerName"]} → {existing["TrackName"]}. One track per manager.'
        if occupied:return False,f'{tower} → {track} is already assigned to {occupied["DisplayName"]}. One manager per track.'
        db.execute(text(f"INSERT INTO qbr.UserTrackAccess(UserID,{target_col},CanView,CanExport,CanManage) VALUES(:uid,:target,1,1,0)"),{"uid":u["UserID"],"target":target});db.commit();return True,f'{u["DisplayName"]} added to {tower} → {track} successfully.'
    except Exception as e:db.rollback();return False,str(e)
    finally:db.close()

def remove_manager(username,tower,track):
    db=SessionLocal()
    try:
        target,target_col=_assignment_target(db,tower,track)
        if not target:return False,f'{tower} → {track} was not found.'
        r=db.execute(text(f"DELETE a FROM qbr.UserTrackAccess a JOIN qbr.AppUser u ON u.UserID=a.UserID WHERE LOWER(u.Username)=LOWER(:u) AND a.{target_col}=:target"),{"u":username,"target":target})
        if r.rowcount==0:db.rollback();return False,f'{username} has no assignment on {tower} → {track}.'
        db.commit();return True,f'{username} removed from {tower} → {track} successfully.'
    except Exception as e:db.rollback();return False,str(e)
    finally:db.close()

def update_role(username,new_role):
    db=SessionLocal()
    try:
        old=db.execute(text("SELECT DisplayName,RoleName FROM qbr.AppUser WHERE LOWER(Username)=LOWER(:u)"),{"u":username}).mappings().first()
        if not old:return False,"User not found."
        db.execute(text("UPDATE qbr.AppUser SET RoleName=:r WHERE LOWER(Username)=LOWER(:u)"),{"r":new_role,"u":username});db.commit();return True,f'{old["DisplayName"]} role changed from {old["RoleName"]} to {new_role} successfully.'
    except Exception as e:db.rollback();return False,str(e)
    finally:db.close()

def _safe_int(v):
    try:return int(v or 0)
    except Exception:return 0
def _safe_float(v):
    try:return float(v or 0)
    except Exception:return 0.0
def render_kpi(col,item):
    lab,val,sub,bg,kind=item;display=f"{_safe_int(val):,}" if kind=="int" else f"{_safe_float(val):,.1f}" if kind=="float" else str(val);col.markdown(f'<div class="qbr-kpi" style="background:{bg}"><div class="t">{lab}</div><div class="v">{display}</div><div class="s">{sub}</div></div>',unsafe_allow_html=True)

def _fig(title,height=360):
    fig=go.Figure();fig.update_layout(title=dict(text=title,font=dict(size=16,color="#12344d"),x=.01),height=height,margin=dict(l=10,r=18,t=48,b=35),paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="#fff",font=dict(family="Segoe UI",color="#12344d",size=11),hoverlabel=dict(bgcolor="#12344d",font_color="#fff"),showlegend=False);return fig

def _cuboid(fig,x,y,z,width,depth,height,label,color):
    x0,x1=x-width/2,x+width/2;y0,y1=y-depth/2,y+depth/2;z0,z1=0,height
    X=[x0,x1,x1,x0,x0,x1,x1,x0];Y=[y0,y0,y1,y1,y0,y0,y1,y1];Z=[z0,z0,z0,z0,z1,z1,z1,z1]
    I=[0,0,0,1,1,2,4,4,4,5,5,6];J=[1,2,4,2,3,6,5,6,0,6,1,7];K=[2,4,5,3,7,7,6,0,1,7,2,4]
    fig.add_trace(go.Mesh3d(x=X,y=Y,z=Z,i=I,j=J,k=K,color=color,opacity=.92,flatshading=True,hovertemplate=f"{label}<br><b>{height}</b> tickets<extra></extra>",showlegend=False))
    fig.add_trace(go.Scatter3d(x=[x],y=[y],z=[height+.35],mode="text",text=[str(height)],textfont=dict(size=10,color="#12344d"),hoverinfo="skip",showlegend=False))

def executive_volume_figure(df, x_col, title="📈 Executive Ticket Volume", height=430):
    """Clean executive trend: total tickets as bars, parent/child as lines."""
    d = df.copy().reset_index(drop=True)
    if d.empty:
        return go.Figure()
    d["Total"] = pd.to_numeric(d["Total"], errors="coerce").fillna(0).astype(int)
    parents = pd.to_numeric(d.get("Parents", 0), errors="coerce").fillna(0).astype(int) if "Parents" in d else pd.Series([0] * len(d))
    children = pd.to_numeric(d.get("Children", 0), errors="coerce").fillna(0).astype(int) if "Children" in d else pd.Series([0] * len(d))
    labels = d[x_col].astype(str).tolist()
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels, y=d["Total"], name="Total",
        marker=dict(color="#198da2", line=dict(color="#0f6f82", width=1)),
        text=d["Total"], textposition="outside",
        hovertemplate="<b>%{x}</b><br>Total tickets: %{y}<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        x=labels, y=parents, name="Parent", mode="lines+markers+text",
        text=parents.astype(str), textposition="top center",
        line=dict(color="#6b9e3b", width=3), marker=dict(size=7),
        hovertemplate="<b>%{x}</b><br>Parent: %{y}<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        x=labels, y=children, name="Child", mode="lines+markers+text",
        text=children.astype(str), textposition="top center",
        line=dict(color="#ef7d2b", width=3), marker=dict(size=7),
        hovertemplate="<b>%{x}</b><br>Child: %{y}<extra></extra>"
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color="#12344d"), x=0.01),
        height=height, margin=dict(l=40, r=25, t=50, b=45),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#ffffff",
        font=dict(family="Segoe UI", size=11, color="#12344d"),
        hoverlabel=dict(bgcolor="#12344d", font_color="#ffffff"),
        legend=dict(orientation="h", x=0, y=1.08),
        bargap=0.28
    )
    fig.update_xaxes(title="Period", showgrid=False, tickangle=-25)
    fig.update_yaxes(title="Tickets", rangemode="tozero", gridcolor="#e3edf0")
    return fig

def ticket_volume_by_tower_track_figure(df, title="📊 Ticket Volume by Tower → Track", height=430):
    """Clean executive horizontal ranking of ticket volume."""
    d = df.copy()
    if d.empty:
        return go.Figure()
    d["Total"] = pd.to_numeric(d["Total"], errors="coerce").fillna(0).astype(int)
    d["Label"] = d["Tower"].astype(str) + " → " + d["Track"].astype(str)
    d = d.sort_values("Total", ascending=True).tail(12)
    palette = {"Foundation":"#5b9f3b", "Collaboration":"#198da2", "Security":"#d94a4a", "Non-CMS":"#9b7b24"}
    colors = [palette.get(str(t), "#547a90") for t in d["Tower"]]
    fig = go.Figure(go.Bar(
        x=d["Total"], y=d["Label"], orientation="h",
        marker=dict(color=colors, line=dict(color="#ffffff", width=1)),
        text=d["Total"], textposition="outside", cliponaxis=False,
        customdata=d[["Tower","Track"]],
        hovertemplate="<b>%{y}</b><br>Tower: %{customdata[0]}<br>Track: %{customdata[1]}<br>Tickets: %{x}<extra></extra>"
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color="#12344d"), x=0.01),
        height=height, margin=dict(l=10, r=55, t=50, b=35),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#ffffff",
        font=dict(family="Segoe UI", size=11, color="#12344d"), showlegend=False
    )
    fig.update_xaxes(title="Tickets", rangemode="tozero", gridcolor="#e3edf0")
    fig.update_yaxes(title="", showgrid=False, automargin=True)
    return fig




def horizontal_bar(labels,values,title,color,height=360,suffix=""):
    pairs=sorted([(str(a),_safe_int(b)) for a,b in zip(labels,values)],key=lambda x:x[1])[-12:];labs=[a for a,b in pairs];vals=[b for a,b in pairs];fig=_fig(title,height);fig.add_trace(go.Bar(y=labs,x=vals,orientation="h",marker=dict(color=color,line=dict(color="#fff",width=1)),text=vals,texttemplate="%{text}"+suffix,textposition="outside",cliponaxis=False,hovertemplate="%{y}<br><b>%{x}</b>"+suffix+"<extra></extra>"));fig.update_xaxes(title="Count",rangemode="tozero",gridcolor="#e4eef1");fig.update_yaxes(showgrid=False,automargin=True);return fig

def alert_summary_figure(df):
    d=df.head(12).copy();d["Label"]=d["Tower"].astype(str)+" → "+d["Track"].astype(str);d=d.iloc[::-1];fig=_fig("⚡ Alerts by Tower / Track",410)
    for col,label,color in [("Critical","Critical","#c91f2b"),("High","High","#ee7d2b"),("Moderate","Moderate","#d2a63a")]:
        if col in d:fig.add_trace(go.Bar(y=d["Label"],x=pd.to_numeric(d[col],errors="coerce").fillna(0),name=label,orientation="h",marker_color=color,text=pd.to_numeric(d[col],errors="coerce").fillna(0).astype(int),textposition="inside",hovertemplate=f"%{{y}}<br>{label}: <b>%{{x}}</b><extra></extra>"))
    fig.update_layout(barmode="stack",showlegend=True,legend=dict(orientation="h",y=1.02,x=0,font=dict(size=10)));fig.update_xaxes(title="Alert count",rangemode="tozero",gridcolor="#e4eef1");fig.update_yaxes(showgrid=False,automargin=True);return fig

r=role();title="Supervisor Dashboard" if r=="SUPERVISOR" else "Manager Dashboard" if r=="MANAGER" else "Superuser Dashboard"
st.markdown(f'<div class="qbr-hero"><h1>📊 QBR Executive Dashboard</h1><p>HCLTech Customer Operations Command Center &nbsp;•&nbsp; <b>{title}</b> &nbsp;•&nbsp; Signed in: <b>{dname()}</b> &nbsp;•&nbsp; Role: <b>{r}</b></p></div>',unsafe_allow_html=True)

if st.session_state.get("show_change_password",False):
    st.markdown('<div class="qbr-card" style="max-width:620px;margin:4vh auto;padding:28px;">',unsafe_allow_html=True);st.markdown(f'<h1 style="text-align:center;color:#12344d;">🔐 Change Password</h1><p style="text-align:center;color:#557789;">Account: <b>{dname()}</b></p>',unsafe_allow_html=True)
    current_pw=st.text_input("🔐 Current Password",type="password",key="cp_current");new_pw=st.text_input("🔑 New Password",type="password",key="cp_new");confirm_pw=st.text_input("✅ Confirm New Password",type="password",key="cp_confirm");a,b=st.columns(2)
    with a:
        if st.button("🔐 UPDATE PASSWORD",use_container_width=True):
            if not(len(new_pw)>=8 and any(c.isupper() for c in new_pw) and any(c.islower() for c in new_pw) and any(c.isdigit() for c in new_pw)):msg("bad","Password policy failed.","Use 8+ characters with uppercase, lowercase and a number.")
            elif new_pw!=confirm_pw:msg("bad","Passwords do not match.")
            else:
                db=SessionLocal()
                try:
                    if change_password(db,user()["UserID"],current_pw,new_pw):db.commit();msg("ok","Password changed successfully.");st.session_state.show_change_password=False;st.rerun()
                    else:db.rollback();msg("bad","Current password is incorrect.")
                except Exception as exc:db.rollback();msg("bad","Unable to change password.",str(exc))
                finally:db.close()
    with b:
        if st.button("← BACK TO DASHBOARD",use_container_width=True):st.session_state.show_change_password=False;st.rerun()
    st.markdown('</div>',unsafe_allow_html=True);st.stop()

hierarchy=get_tower_track_hierarchy()
with st.sidebar:
    st.markdown('<div class="qbr-side-title">🎛️ QBR DASHBOARD CONTROLS</div>',unsafe_allow_html=True)
    # No st.cache_data.clear(): the previous button caused Streamlit's
    # confirmation dialog and was unnecessary because dashboard queries are
    # intentionally live against CPDB. A rerun is sufficient.
    if st.button("🔄 Refresh Data",use_container_width=True):st.rerun()
    if st.button("🔐 Change Password",use_container_width=True):st.session_state.show_change_password=True;st.rerun()
    if st.button("🚪 Sign out",use_container_width=True):clear_session();st.rerun()
    st.divider();allowed=assigned_tracks(uname()) if r=="MANAGER" else []
    tower_options=sorted({x[0] for x in allowed}) if r=="MANAGER" else sorted(hierarchy.keys())
    st.markdown('<div class="qbr-side-head">1️⃣ TOWER</div>',unsafe_allow_html=True);tower=st.selectbox("Tower",["All"]+tower_options,label_visibility="collapsed",key="scope_tower")
    tracks = (
    sorted({str(track_name) for track_list in hierarchy.values() for track_name in track_list})
    if tower == "All"
    else sorted([str(track_name) for track_name in hierarchy.get(tower, [])])
    )
    st.markdown('<div class="qbr-side-head">2️⃣ TRACK</div>',unsafe_allow_html=True);track=st.selectbox("Track",["All"]+tracks,label_visibility="collapsed",key="scope_track")
    st.markdown('<div class="qbr-side-head">3️⃣ TIME VIEW</div>',unsafe_allow_html=True);view=st.selectbox("Time View",["Day","Week","Month","Quarter"],key="scope_view")
    st.markdown('<div class="qbr-side-head">📅 REPORT DATE RANGE</div>',unsafe_allow_html=True);dr=st.date_input("Report Date Range",value=(date(2026,7,15),date.today()),min_value=date(2020,1,1),max_value=date.today(),label_visibility="collapsed",key="scope_dates")

start=end=None
if isinstance(dr,(tuple,list)) and len(dr)==2:start,end=dr[0],dr[1]
elif isinstance(dr,date):start=end=dr
if r=="MANAGER" and len(allowed)==1:tower=allowed[0][0] if tower=="All" else tower;track=allowed[0][1] if track=="All" else track
scope_tower=None if tower=="All" else tower;scope_track=None if track=="All" else track
k=get_executive_kpis(start,end,scope_tower,scope_track);alerts_total=get_alert_total(start,end,scope_tower,scope_track);vol=get_tower_track_volume(start,end,scope_tower,scope_track);stats=get_volume_stats(start,end,scope_tower,scope_track);alerts=get_alert_frequency(start,end,scope_tower,scope_track);pc_df,children_df=get_parent_child_relation(start,end,scope_tower,scope_track);alert_summary=get_tower_track_alerts(start,end,scope_tower,scope_track)

st.markdown('<div class="qbr-section">📌 Executive KPI Snapshot</div>',unsafe_allow_html=True)
kpis=[("🎫 TOTAL TICKETS",k.get("total",0),"Selected timeframe","linear-gradient(135deg,#0b5774,#168f9e,#1ca88e)","int"),("👑 PARENT TICKETS",k.get("parents",0),"Root workload","linear-gradient(135deg,#4d7e31,#79ad4d,#9bca69)","int"),("↳ CHILD TICKETS",k.get("children",0),"Linked workload","linear-gradient(135deg,#e87323,#f29b45,#f6bf76)","int"),("⚡ ALERTS",alerts_total,"Monitoring events","linear-gradient(135deg,#b30e16,#db3039,#ee6868)","int"),("📊 MAX / MIN",f"{_safe_int(stats.get('max_count') if stats else 0):,} / {_safe_int(stats.get('min_count') if stats else 0):,}","Tickets per day","linear-gradient(135deg,#7b5c08,#a7841d,#c7a743)","text"),("📈 AVG / DAY",stats.get("avg_count",0) if stats else 0,"Daily average","linear-gradient(135deg,#31599b,#4b7ccc,#789fe3)","float"),("🔵 OPEN",max(0,_safe_int(k.get("total"))- _safe_int(k.get("closed"))),"Awaiting resolution","linear-gradient(135deg,#166cad,#268bd0,#63b8ed)","int"),("✅ CLOSED",k.get("closed",0),"Resolved","linear-gradient(135deg,#2d8037,#52a95b,#83c987)","int"),("🔴 CRITICAL",k.get("critical",0),"Critical priority","linear-gradient(135deg,#b52222,#dc4949,#ef7777)","int")]
for c,item in zip(st.columns(5),kpis[:5]):render_kpi(c,item)
for c,item in zip(st.columns(4),kpis[5:]):render_kpi(c,item)

if stats and stats.get("max_date") is not None and stats.get("min_date") is not None:
    max_date=pd.to_datetime(stats["max_date"]).strftime("%d %b %Y")
    min_date=pd.to_datetime(stats["min_date"]).strftime("%d %b %Y")
    st.markdown(f'<div class="qbr-volume-note">📌 Maximum ticket volume: <b>{_safe_int(stats.get("max_count")):,}</b> tickets on <b>{max_date}</b> &nbsp; • &nbsp; Minimum ticket volume: <b>{_safe_int(stats.get("min_count")):,}</b> tickets on <b>{min_date}</b>.</div>',unsafe_allow_html=True)

if view=="Day":trend=get_daily_trend(start,end,scope_tower,scope_track);x="Date"
elif view=="Week":trend=get_weekly_trend(start,end,scope_tower,scope_track);x="Week"
elif view=="Month":trend=get_monthly_trend(start,end,scope_tower,scope_track);x="Month"
else:trend=get_quarterly_trend(start,end,scope_tower,scope_track);x="Quarter"

st.markdown('<div class="qbr-section">📈 Executive Volume & Trend</div>',unsafe_allow_html=True)
st.markdown('<div class="qbr-volume-note">Executive view • Total tickets are shown as columns; parent and child workload are shown as trend lines. Hover for the exact count.</div>',unsafe_allow_html=True)
a,b=st.columns([1.45,1])
with a:
    if not trend.empty:st.plotly_chart(executive_volume_figure(trend,x,"📈 Executive Ticket Volume",430),use_container_width=True,config={"displayModeBar":False})
    else:msg("inf","No ticket trend data.","Try a wider date range.")
with b:
    if not vol.empty:st.plotly_chart(ticket_volume_by_tower_track_figure(vol,"📊 Ticket Volume by Tower → Track",430),use_container_width=True,config={"displayModeBar":False})
    else:msg("inf","No Tower / Track ticket volume.","No ticket rows match the selected filters.")

st.markdown('<div class="qbr-section">👑 Parent-Child & Alert Analysis</div>',unsafe_allow_html=True);a,b=st.columns(2)
with a:
    if not pc_df.empty:
        d=pc_df.head(10);st.plotly_chart(horizontal_bar(d["ParentTicket"].astype(str).tolist(),d["ChildCount"].tolist(),"👑 Parent → Child Concentration","#7b6848",360," child"),use_container_width=True,config={"displayModeBar":False});st.markdown(f'<span class="qbr-pill" style="background:#e8f4ff;color:#155486;">{len(children_df)} child records</span><span class="qbr-pill" style="background:#e9faef;color:#17613a;">{len(pc_df)} parent groups</span>',unsafe_allow_html=True)
        with st.expander("🔍 View exact parent → child relationships"):st.dataframe(children_df,use_container_width=True,hide_index=True)
    else:msg("inf","No parent-child relationship rows.","The selected scope returned no Child tickets with ParentTicketNumber.")
with b:
    if not alerts.empty:
        d=alerts.groupby("Device",as_index=False)["Count"].sum().sort_values("Count",ascending=False).head(10);st.plotly_chart(horizontal_bar(d["Device"].astype(str).tolist(),d["Count"].tolist(),"⚡ Highest Alert / Device Frequency","#d3342f",360," alerts"),use_container_width=True,config={"displayModeBar":False})
    else:msg("inf","No alert frequency rows.","No alert rows match the selected filters.")

st.markdown('<div class="qbr-section">⚡ Tower / Track Alert Summary</div>',unsafe_allow_html=True)
if not alert_summary.empty:
    total_a=int(pd.to_numeric(alert_summary["TotalAlerts"],errors="coerce").fillna(0).sum());critical_a=int(pd.to_numeric(alert_summary["Critical"],errors="coerce").fillna(0).sum());high_a=int(pd.to_numeric(alert_summary["High"],errors="coerce").fillna(0).sum());moderate_a=int(pd.to_numeric(alert_summary["Moderate"],errors="coerce").fillna(0).sum());track_a=len(alert_summary);s1,s2,s3,s4,s5=st.columns(5)
    for col,num,label in [(s1,total_a,"Total alerts"),(s2,critical_a,"Critical"),(s3,high_a,"High"),(s4,moderate_a,"Moderate"),(s5,track_a,"Affected Tower → Track")]:col.markdown(f'<div class="qbr-alert-stat"><div class="n">{num:,}</div><div class="l">{label}</div></div>',unsafe_allow_html=True)
    st.plotly_chart(alert_summary_figure(alert_summary),use_container_width=True,config={"displayModeBar":False});d=alert_summary.head(20).copy();d["TotalAlerts"]=pd.to_numeric(d["TotalAlerts"],errors="coerce").fillna(0).astype(int);st.dataframe(d[["Tower","Track","TotalAlerts","Critical","High","Moderate"]],use_container_width=True,hide_index=True)
else:msg("inf","No Tower / Track alert rows.","No alert rows match the selected filters.")

if r in ("SUPERUSER","SUPERVISOR"):
    st.markdown('<div class="qbr-section">👥 Manager & Role Administration</div>',unsafe_allow_html=True);st.caption("Assignment rule: one manager per Tower → Track, and one Tower → Track per manager.");users=manager_users();active_managers=[u for u in users if str(u["RoleName"]).upper()=="MANAGER"];towers=sorted(hierarchy.keys())
    if towers and active_managers:
        tsel=st.selectbox("Tower",towers,key="admin_tower");trsel=st.selectbox("Track",[str(track_name) for track_name in hierarchy.get(tsel, [])],key="admin_track");msel=st.selectbox("Manager",[u["Username"] for u in active_managers],format_func=lambda x:next((f'{u["DisplayName"]} • {u["RoleName"]}' for u in active_managers if u["Username"]==x),x),key="admin_manager");aa,bb,cc=st.columns(3)
        with aa:
            if st.button("➕ Assign Manager",use_container_width=True):
                ok,detail=assign_manager(msel,tsel,trsel);msg("ok" if ok else "bad","Assignment successful." if ok else "Assignment failed.",detail)
                if ok:st.rerun()
        with bb:
            if st.button("➖ Remove Manager",use_container_width=True):
                ok,detail=remove_manager(msel,tsel,trsel);msg("ok" if ok else "bad","Removal successful." if ok else "Removal failed.",detail)
                if ok:st.rerun()
        with cc:
            if st.button("🔄 Refresh Access",use_container_width=True):st.rerun()
    rows=admin_rows()
    if rows:
        df_admin=pd.DataFrame(rows)[["DisplayName","Username","RoleName","TowerName","TrackName","CanView","CanExport","CanManage"]].rename(columns={"DisplayName":"Manager","RoleName":"Role","TowerName":"Tower","TrackName":"Track","CanView":"View","CanExport":"Export","CanManage":"Manage"});st.dataframe(df_admin,use_container_width=True,hide_index=True)
    st.markdown("### 🛡️ Role Management")
    if users:
        role_user=st.selectbox("User",[u["Username"] for u in users],format_func=lambda x:next((f'{u["DisplayName"]} • current role: {u["RoleName"]}' for u in users if u["Username"]==x),x),key="role_user");current=next((str(u["RoleName"]).upper() for u in users if u["Username"]==role_user),"");roles=["MANAGER","SUPERVISOR","SUPERUSER"];new_role=st.selectbox(f"Current role: {current}",roles,index=roles.index(current) if current in roles else 0,key="new_role")
        if st.button("🛡️ Update Role",use_container_width=True):
            ok,detail=update_role(role_user,new_role);msg("ok" if ok else "bad","Role updated successfully." if ok else "Role update failed.",detail)
            if ok:st.rerun()

st.markdown('<div class="qbr-section">📗 Excel Analysis Pack</div>',unsafe_allow_html=True)
summary=pd.DataFrame([["Report Date",datetime.now().strftime("%Y-%m-%d %H:%M")],["Tower",tower],["Track",track],["From",start],["To",end],["Total Tickets",k.get("total",0)],["Parent Tickets",k.get("parents",0)],["Child Tickets",k.get("children",0)],["Alerts",alerts_total],["Max Tickets/Day",stats.get("max_count",0) if stats else 0],["Min Tickets/Day",stats.get("min_count",0) if stats else 0]],columns=["Metric","Value"])
buf=io.BytesIO()
with pd.ExcelWriter(buf,engine="openpyxl") as writer:
    summary.to_excel(writer,index=False,sheet_name="Executive Summary");trend.to_excel(writer,index=False,sheet_name="Ticket Trend");vol.to_excel(writer,index=False,sheet_name="Tower Track Volume");alerts.to_excel(writer,index=False,sheet_name="Alert Frequency");pc_df.to_excel(writer,index=False,sheet_name="Parent Child");alert_summary.to_excel(writer,index=False,sheet_name="Alert Summary")
st.download_button("📗 Download Excel Analysis Pack",buf.getvalue(),"QBR_Executive_Analysis.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)
st.caption("Excel Analysis Pack is structured for Excel Power Query / Power Pivot modelling; Streamlit remains the live CPDB dashboard.")
