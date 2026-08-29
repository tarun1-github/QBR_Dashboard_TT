"""QBR Executive Dashboard - CPDB-driven customer operations command center."""
from __future__ import annotations

import io
import sys
from datetime import date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import text

from app.db import SessionLocal
from app.auth import change_password
from app.login_block import render_login, render_flash, initialise_auth_state, clear_session
from app.dashboard_data import (
    get_tower_track_hierarchy, get_executive_kpis, get_alert_total,
    get_tower_track_volume, get_daily_trend, get_weekly_trend,
    get_monthly_trend, get_quarterly_trend, get_alert_frequency,
    get_parent_child_relation, get_volume_stats, get_tower_track_alerts,
)

st.set_page_config(page_title="QBR Executive Dashboard", page_icon="📊", layout="wide", initial_sidebar_state="expanded")
initialise_auth_state()
if not st.session_state.get("user"):
    render_flash()
    render_login()
    st.stop()
render_flash()

st.markdown("""
<style>
[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 15% 5%,#ffffff 0,#eef8fa 38%,#dceef2 100%);}
.main .block-container{padding-top:1rem;padding-bottom:3rem;max-width:1600px;}
section[data-testid="stSidebar"]{background:linear-gradient(180deg,#092c49 0%,#075b77 52%,#087d78 100%)!important;box-shadow:10px 0 30px rgba(5,36,56,.24);}
.qbr-side-title{color:#fff;font-weight:1000;letter-spacing:.7px;border-radius:17px;padding:12px 14px;margin:5px 0 12px;background:linear-gradient(135deg,#0b4969,#1097a0,#18ad8a);box-shadow:0 8px 0 rgba(0,0,0,.18),0 12px 25px rgba(0,0,0,.15);}
.qbr-side-head{color:#d9fbff;font-size:11px;font-weight:900;letter-spacing:.7px;border-radius:14px;padding:9px 12px;margin:15px 0 7px;background:linear-gradient(135deg,#0c6b7b,#0b8c95);box-shadow:4px 5px 0 rgba(0,0,0,.15);}
section[data-testid="stSidebar"] .stButton>button{border-radius:16px!important;background:linear-gradient(145deg,#ffffff,#dfeff3)!important;color:#12344d!important;font-weight:900!important;box-shadow:5px 6px 0 rgba(0,0,0,.18)!important;border:1px solid #c4dce3!important;}
section[data-testid="stSidebar"] div[data-baseweb="select"]>div,section[data-testid="stSidebar"] input{border-radius:14px!important;background:#fff!important;color:#12344d!important;border:2px solid #d5e7eb!important;box-shadow:inset 2px 2px 7px rgba(12,55,76,.08)!important;}
.qbr-hero{padding:25px 30px;border-radius:28px;background:linear-gradient(135deg,#082c49 0%,#0e6582 48%,#19a78e 100%);color:#fff;box-shadow:0 18px 38px rgba(8,44,73,.26),8px 9px 0 rgba(8,44,73,.13),inset 0 1px rgba(255,255,255,.25);margin-bottom:18px;}
.qbr-hero h1{margin:0;font:1000 35px 'Segoe UI',Aptos,sans-serif;letter-spacing:.3px}.qbr-hero p{margin:8px 0 0;font-size:14px;opacity:.96}
.qbr-section{font:1000 22px 'Segoe UI',Aptos,sans-serif;color:#12344d;margin:23px 0 10px;padding:11px 16px;border-radius:17px;background:linear-gradient(145deg,#ffffff,#eaf5f7);box-shadow:5px 6px 0 rgba(15,39,66,.09),0 10px 22px rgba(15,39,66,.08);border:1px solid #d4e5e9;}
.qbr-kpi{min-height:118px;padding:18px;border-radius:23px;color:#fff;box-shadow:0 15px 28px rgba(15,39,66,.20),7px 8px 0 rgba(15,39,66,.12),inset 0 1px rgba(255,255,255,.35);transform:translateY(-1px);}
.qbr-kpi .t{font-size:11px;font-weight:1000;letter-spacing:.6px}.qbr-kpi .v{font-size:33px;font-weight:1000;margin-top:8px;text-shadow:0 3px 5px rgba(0,0,0,.22)}.qbr-kpi .s{font-size:10px;opacity:.96}
.qbr-card{padding:14px 17px;border-radius:20px;background:linear-gradient(145deg,#fff,#edf7f8);box-shadow:8px 9px 0 rgba(15,39,66,.09),0 14px 28px rgba(15,39,66,.10);border:1px solid #d3e5e9;}
.stButton>button,.stDownloadButton>button{border-radius:16px!important;font-weight:900!important;box-shadow:5px 6px 0 rgba(15,39,66,.14)!important;}
.js-plotly-plot{border-radius:20px;overflow:hidden;box-shadow:0 12px 30px rgba(15,39,66,.13);border:1px solid #d8e8eb;}
.qbr-msg{padding:13px 17px;border-radius:16px;margin:10px 0;box-shadow:5px 6px 0 rgba(15,39,66,.10);font-weight:800}.ok{background:#e7faef;border:1px solid #68c98d;color:#12623a}.bad{background:#fff0f0;border:1px solid #df8a8a;color:#982323}.inf{background:#eaf5ff;border:1px solid #7fb8e8;color:#185486}
.qbr-pill{display:inline-block;padding:6px 11px;border-radius:999px;font-weight:900;font-size:11px;margin:2px 4px 2px 0;box-shadow:3px 4px 0 rgba(15,39,66,.10)}
footer{visibility:hidden}
</style>
""", unsafe_allow_html=True)

def msg(kind,title,detail=""):
    cls={"ok":"ok","bad":"bad","inf":"inf"}.get(kind,"inf")
    icon={"ok":"✓","bad":"!","inf":"i"}.get(kind,"i")
    st.markdown(f'<div class="qbr-msg {cls}">{icon}&nbsp;&nbsp;<b>{title}</b> {detail}</div>',unsafe_allow_html=True)

def user(): return st.session_state.user or {}
def role(): return str(user().get("RoleName") or user().get("role") or "").upper()
def uname(): return str(user().get("Username") or user().get("username") or "")
def dname(): return str(user().get("DisplayName") or user().get("name") or uname())

def assigned_tracks(username):
    db=SessionLocal()
    try:
        if not db.execute(text("SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='qbr' AND TABLE_NAME='UserTrackAccess'")).first(): return []
        cols={str(r[0]) for r in db.execute(text("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='qbr' AND TABLE_NAME='UserTrackAccess'")).fetchall()}
        if "TowerTrackID" in cols and db.execute(text("SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='qbr' AND TABLE_NAME='TowerTrack'")).first():
            q="""SELECT tt.TowerName,tt.TrackName FROM qbr.UserTrackAccess a JOIN qbr.AppUser u ON u.UserID=a.UserID JOIN qbr.TowerTrack tt ON tt.TowerTrackID=a.TowerTrackID WHERE LOWER(u.Username)=LOWER(:u) AND ISNULL(tt.IsActive,1)=1 ORDER BY tt.TowerName,tt.TrackName"""
        else:
            q="""SELECT t.TowerName,tr.TrackName FROM qbr.UserTrackAccess a JOIN qbr.AppUser u ON u.UserID=a.UserID JOIN qbr.Track tr ON tr.TrackID=a.TrackID JOIN qbr.Tower t ON t.TowerID=tr.TowerID WHERE LOWER(u.Username)=LOWER(:u) AND ISNULL(tr.IsActive,1)=1 ORDER BY t.TowerName,tr.TrackName"""
        return [(r[0],r[1]) for r in db.execute(text(q),{"u":username}).fetchall()]
    finally: db.close()

def admin_rows():
    db=SessionLocal()
    try:
        cols={str(r[0]) for r in db.execute(text("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='qbr' AND TABLE_NAME='UserTrackAccess'")).fetchall()}
        if "TowerTrackID" in cols:
            q="""SELECT u.DisplayName,u.Username,u.RoleName,tt.TowerName,tt.TrackName,uta.CanView,uta.CanExport,uta.CanManage,uta.UserTrackAccessID FROM qbr.UserTrackAccess uta JOIN qbr.AppUser u ON u.UserID=uta.UserID JOIN qbr.TowerTrack tt ON tt.TowerTrackID=uta.TowerTrackID WHERE ISNULL(tt.IsActive,1)=1 ORDER BY tt.TowerName,tt.TrackName,u.DisplayName"""
        else:
            q="""SELECT u.DisplayName,u.Username,u.RoleName,t.TowerName,tr.TrackName,uta.CanView,uta.CanExport,uta.CanManage,uta.UserTrackAccessID FROM qbr.UserTrackAccess uta JOIN qbr.AppUser u ON u.UserID=uta.UserID JOIN qbr.Track tr ON tr.TrackID=uta.TrackID JOIN qbr.Tower t ON t.TowerID=tr.TowerID WHERE ISNULL(tr.IsActive,1)=1 ORDER BY t.TowerName,tr.TrackName,u.DisplayName"""
        return db.execute(text(q)).mappings().all()
    finally: db.close()

def manager_users():
    db=SessionLocal()
    try: return db.execute(text("SELECT UserID,Username,DisplayName,RoleName,IsActive FROM qbr.AppUser WHERE IsActive=1 ORDER BY DisplayName")).mappings().all()
    finally: db.close()

def _assignment_target(db,tower,track):
    cols={str(r[0]) for r in db.execute(text("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='qbr' AND TABLE_NAME='UserTrackAccess'")).fetchall()}
    if "TowerTrackID" in cols:
        return db.execute(text("SELECT TowerTrackID FROM qbr.TowerTrack WHERE TowerName=:t AND TrackName=:tr AND ISNULL(IsActive,1)=1"),{"t":tower,"tr":track}).scalar(),"TowerTrackID"
    return db.execute(text("SELECT tr.TrackID FROM qbr.Track tr JOIN qbr.Tower t ON t.TowerID=tr.TowerID WHERE t.TowerName=:t AND tr.TrackName=:tr AND ISNULL(tr.IsActive,1)=1"),{"t":tower,"tr":track}).scalar(),"TrackID"

def assign_manager(username,tower,track):
    db=SessionLocal()
    try:
        u=db.execute(text("SELECT UserID,DisplayName,RoleName FROM qbr.AppUser WHERE LOWER(Username)=LOWER(:u)"),{"u":username}).mappings().first()
        target,target_col=_assignment_target(db,tower,track)
        if not u or not target:return False,"User or Tower → Track not found."
        if str(u["RoleName"]).upper()!="MANAGER":return False,f'{u["DisplayName"]} current role is {u["RoleName"]}. Change the role to MANAGER first.'
        if target_col=="TowerTrackID":
            exists=db.execute(text("""SELECT u.DisplayName,tt.TowerName,tt.TrackName FROM qbr.UserTrackAccess a JOIN qbr.AppUser u ON u.UserID=a.UserID JOIN qbr.TowerTrack tt ON tt.TowerTrackID=a.TowerTrackID WHERE a.UserID=:uid"""),{"uid":u["UserID"]}).mappings().first()
            occupied=db.execute(text("""SELECT u.DisplayName FROM qbr.UserTrackAccess a JOIN qbr.AppUser u ON u.UserID=a.UserID WHERE a.TowerTrackID=:target AND UPPER(u.RoleName)='MANAGER'"""),{"target":target}).mappings().first()
            if exists:return False,f'{u["DisplayName"]} is already assigned to {exists["TowerName"]} → {exists["TrackName"]}. One track per manager.'
            if occupied:return False,f'{tower} → {track} is already assigned to {occupied["DisplayName"]}. One manager per track.'
            db.execute(text("INSERT INTO qbr.UserTrackAccess(UserID,TowerTrackID,CanView,CanExport,CanManage) VALUES(:uid,:target,1,1,0)"),{"uid":u["UserID"],"target":target})
        else:
            exists=db.execute(text("""SELECT u.DisplayName,t.TowerName,tr.TrackName FROM qbr.UserTrackAccess a JOIN qbr.AppUser u ON u.UserID=a.UserID JOIN qbr.Track tr ON tr.TrackID=a.TrackID JOIN qbr.Tower t ON t.TowerID=tr.TowerID WHERE a.UserID=:uid"""),{"uid":u["UserID"]}).mappings().first()
            occupied=db.execute(text("""SELECT u.DisplayName FROM qbr.UserTrackAccess a JOIN qbr.AppUser u ON u.UserID=a.UserID WHERE a.TrackID=:target AND UPPER(u.RoleName)='MANAGER'"""),{"target":target}).mappings().first()
            if exists:return False,f'{u["DisplayName"]} is already assigned to {exists["TowerName"]} → {exists["TrackName"]}. One track per manager.'
            if occupied:return False,f'{tower} → {track} is already assigned to {occupied["DisplayName"]}. One manager per track.'
            db.execute(text("INSERT INTO qbr.UserTrackAccess(UserID,TrackID,CanView,CanExport,CanManage) VALUES(:uid,:target,1,1,0)"),{"uid":u["UserID"],"target":target})
        db.commit(); return True,f'{u["DisplayName"]} added to {tower} → {track} successfully.'
    except Exception as e: db.rollback(); return False,str(e)
    finally: db.close()

def remove_manager(username,tower,track):
    db=SessionLocal()
    try:
        target,target_col=_assignment_target(db,tower,track)
        if not target:return False,f'{tower} → {track} was not found.'
        r=db.execute(text(f"""DELETE a FROM qbr.UserTrackAccess a JOIN qbr.AppUser u ON u.UserID=a.UserID WHERE LOWER(u.Username)=LOWER(:u) AND a.{target_col}=:target"""),{"u":username,"target":target})
        if r.rowcount==0: db.rollback(); return False,f'{username} has no assignment on {tower} → {track}.'
        db.commit(); return True,f'{username} removed from {tower} → {track} successfully.'
    except Exception as e: db.rollback(); return False,str(e)
    finally: db.close()

def update_role(username,new_role):
    db=SessionLocal()
    try:
        old=db.execute(text("SELECT DisplayName,RoleName FROM qbr.AppUser WHERE LOWER(Username)=LOWER(:u)"),{"u":username}).mappings().first()
        if not old:return False,"User not found."
        db.execute(text("UPDATE qbr.AppUser SET RoleName=:r WHERE LOWER(Username)=LOWER(:u)"),{"r":new_role,"u":username})
        db.commit(); return True,f'{old["DisplayName"]} role changed from {old["RoleName"]} to {new_role} successfully.'
    except Exception as e:db.rollback();return False,str(e)
    finally:db.close()

def _safe_int(v):
    try:return int(v or 0)
    except:return 0

def _safe_float(v):
    try:return float(v or 0)
    except:return 0.0

def render_kpi(col,item):
    lab,val,sub,bg,kind=item
    if kind=="int": display=f"{_safe_int(val):,}"
    elif kind=="float": display=f"{_safe_float(val):,.1f}"
    else: display=str(val)
    col.markdown(f'<div class="qbr-kpi" style="background:{bg}"><div class="t">{lab}</div><div class="v">{display}</div><div class="s">{sub}</div></div>',unsafe_allow_html=True)

def cuboid_mesh(x,z,color,width=.72,depth=.72):
    x0=x-width/2;x1=x+width/2;y0=-depth/2;y1=depth/2
    X=[x0,x1,x1,x0,x0,x1,x1,x0];Y=[y0,y0,y1,y1,y0,y0,y1,y1];Z=[0,0,0,0,z,z,z,z]
    I=[0,0,0,1,1,2,4,4,4,5,5,6];J=[1,2,4,2,3,3,5,6,0,6,7,7];K=[2,4,5,3,7,7,6,0,1,7,4,4]
    return go.Mesh3d(x=X,y=Y,z=Z,i=I,j=J,k=K,color=color,opacity=.94,flatshading=True,hoverinfo="skip",showlegend=False)

def three_d_bars(labels,values,title,y_title="Count",colors=None,height=410):
    colors=colors or ["#1593a5","#6ea943","#ee7d2b","#7b5aa6","#d02b35","#c29a1c"]
    fig=go.Figure(); maxv=max(values or [1])
    for i,v in enumerate(values):
        fig.add_trace(cuboid_mesh(i,float(v),colors[i%len(colors)]))
        fig.add_trace(go.Scatter3d(x=[i],y=[0],z=[float(v)+maxv*.035],mode="text",text=[str(v)],textfont=dict(size=12,color="#12344d"),showlegend=False,hoverinfo="skip"))
    fig.update_layout(title=dict(text=title,font=dict(size=17,color="#12344d")),height=height,margin=dict(l=0,r=0,t=48,b=0),paper_bgcolor="rgba(0,0,0,0)",scene=dict(xaxis=dict(tickmode="array",tickvals=list(range(len(labels))),ticktext=labels,title="",showbackground=True,backgroundcolor="#f6fbfc",gridcolor="#d7e5e9"),yaxis=dict(title="",showticklabels=False,showgrid=False),zaxis=dict(title=y_title,gridcolor="#d7e5e9"),camera=dict(eye=dict(x=1.65,y=1.6,z=1.25)),font=dict(family="Segoe UI",color="#12344d"),showlegend=False)
    return fig

r=role(); title="Supervisor Dashboard" if r=="SUPERVISOR" else "Manager Dashboard" if r=="MANAGER" else "Superuser Dashboard"
st.markdown(f'<div class="qbr-hero"><h1>📊 QBR Executive Dashboard</h1><p>HCLTech Customer Operations Command Center &nbsp;•&nbsp; <b>{title}</b> &nbsp;•&nbsp; Signed in: <b>{dname()}</b> &nbsp;•&nbsp; Role: <b>{r}</b></p></div>',unsafe_allow_html=True)

if st.session_state.get("show_change_password",False):
    st.markdown('<div class="qbr-card" style="max-width:620px;margin:5vh auto;padding:34px;">',unsafe_allow_html=True)
    st.markdown('<h1 style="text-align:center;color:#12344d;">🔐 Change Password</h1>',unsafe_allow_html=True)
    st.markdown(f'<p style="text-align:center;color:#557789;">Account: <b>{dname()}</b></p>',unsafe_allow_html=True)
    current_pw=st.text_input("🔐 Current Password",type="password",key="cp_current")
    new_pw=st.text_input("🔑 New Password",type="password",key="cp_new")
    confirm_pw=st.text_input("✅ Confirm New Password",type="password",key="cp_confirm")
    a,b=st.columns(2)
    with a:
        if st.button("🔐 UPDATE PASSWORD",use_container_width=True):
            if len(new_pw)<8 or not any(c.isupper() for c in new_pw) or not any(c.islower() for c in new_pw) or not any(c.isdigit() for c in new_pw): msg("bad","Password policy failed.","Use 8+ characters with uppercase, lowercase and a number.")
            elif new_pw!=confirm_pw: msg("bad","Passwords do not match.")
            else:
                db=SessionLocal()
                try:
                    if change_password(db,user()["UserID"],current_pw,new_pw): msg("ok","Password changed successfully."); st.session_state.show_change_password=False; st.rerun()
                    else: msg("bad","Current password is incorrect.")
                except Exception as exc: db.rollback(); msg("bad","Unable to change password.",str(exc))
                finally: db.close()
    with b:
        if st.button("← BACK TO DASHBOARD",use_container_width=True): st.session_state.show_change_password=False; st.rerun()
    st.markdown('</div>',unsafe_allow_html=True); st.stop()

hierarchy=get_tower_track_hierarchy()
with st.sidebar:
    st.markdown('<div class="qbr-side-title">🎛️ QBR DASHBOARD CONTROLS</div>',unsafe_allow_html=True)
    if st.button("🔄 Pull / Refresh Data",use_container_width=True): st.cache_data.clear(); st.rerun()
    if st.button("🔐 Change Password",use_container_width=True): st.session_state.show_change_password=True; st.rerun()
    if st.button("🚪 Sign out",use_container_width=True): clear_session(); st.rerun()
    st.divider()
    allowed=assigned_tracks(uname()) if r=="MANAGER" else []
    tower_options=sorted({x[0] for x in allowed}) if r=="MANAGER" else sorted(hierarchy.keys())
    st.markdown('<div class="qbr-side-head">1️⃣ TOWER</div>',unsafe_allow_html=True)
    tower=st.selectbox("Tower",["All"]+tower_options,label_visibility="collapsed")
    tracks=sorted({d["TrackName"] for v in hierarchy.values() for d in v}) if tower=="All" else [d["TrackName"] for d in hierarchy.get(tower,[])]
    st.markdown('<div class="qbr-side-head">2️⃣ TRACK</div>',unsafe_allow_html=True)
    track=st.selectbox("Track",["All"]+tracks,label_visibility="collapsed")
    st.markdown('<div class="qbr-side-head">3️⃣ TIME VIEW</div>',unsafe_allow_html=True)
    view=st.selectbox("Time View",["Day","Week","Month","Quarter"],index=0,label_visibility="collapsed")
    st.markdown('<div class="qbr-side-head">📅 REPORT DATE RANGE</div>',unsafe_allow_html=True)
    dr=st.date_input("Report Date Range",value=(date(2026,7,15),date.today()),min_value=date(2020,1,1),max_value=date.today(),label_visibility="collapsed")

start=end=None
if isinstance(dr,(tuple,list)) and len(dr)==2:start,end=dr[0],dr[1]
elif isinstance(dr,date):start=end=dr
if r=="MANAGER" and len(allowed)==1:
    tower=allowed[0][0] if tower=="All" else tower
    track=allowed[0][1] if track=="All" else track
scope_tower=None if tower=="All" else tower
scope_track=None if track=="All" else track
k=get_executive_kpis(start,end,scope_tower,scope_track); alerts_total=get_alert_total(start,end,scope_tower,scope_track); vol=get_tower_track_volume(start,end,scope_tower,scope_track); stats=get_volume_stats(start,end,scope_tower,scope_track); alerts=get_alert_frequency(start,end,scope_tower,scope_track); pc_df,children_df=get_parent_child_relation(start,end,scope_tower,scope_track); alert_summary=get_tower_track_alerts(start,end,scope_tower,scope_track)

kpis=[("🎫 TOTAL TICKETS",k.get("total",0),"Selected timeframe","linear-gradient(135deg,#0b5774,#168f9e,#1ca88e)","int"),("👑 PARENT TICKETS",k.get("parents",0),"Root workload","linear-gradient(135deg,#4d7e31,#79ad4d,#9bca69)","int"),("↳ CHILD TICKETS",k.get("children",0),"Linked workload","linear-gradient(135deg,#e87323,#f29b45,#f6bf76)","int"),("⚡ ALERTS",alerts_total,"Monitoring events","linear-gradient(135deg,#b30e16,#db3039,#ee6868)","int"),("📊 MAX / MIN",f"{_safe_int(stats.get('max_count') if stats else 0):,} / {_safe_int(stats.get('min_count') if stats else 0):,}","Tickets per day","linear-gradient(135deg,#7b5c08,#a7841d,#c7a743)","text"),("📈 AVG / DAY",stats.get("avg_count",0) if stats else 0,"Daily average","linear-gradient(135deg,#31599b,#4b7ccc,#789fe3)","float"),("🔵 OPEN",max(0,_safe_int(k.get("total"))- _safe_int(k.get("closed"))),"Awaiting resolution","linear-gradient(135deg,#166cad,#268bd0,#63b8ed)","int"),("✅ CLOSED",k.get("closed",0),"Resolved","linear-gradient(135deg,#2d8037,#52a95b,#83c987)","int"),("🔴 CRITICAL",k.get("critical",0),"Critical priority","linear-gradient(135deg,#b52222,#dc4949,#ef7777)","int")]
for c,item in zip(st.columns(5),kpis[:5]):render_kpi(c,item)
for c,item in zip(st.columns(4),kpis[5:]):render_kpi(c,item)

if view=="Day": trend=get_daily_trend(start,end,scope_tower,scope_track); x="Date"
elif view=="Week": trend=get_weekly_trend(start,end,scope_tower,scope_track); x="Week"
elif view=="Month": trend=get_monthly_trend(start,end,scope_tower,scope_track); x="Month"
else: trend=get_quarterly_trend(start,end,scope_tower,scope_track); x="Quarter"

st.markdown('<div class="qbr-section">📊 Executive Volume & Trend</div>',unsafe_allow_html=True)
a,b=st.columns(2)
with a:
    if not trend.empty:
        st.plotly_chart(three_d_bars(trend[x].astype(str).tolist(),trend["Total"].astype(int).tolist(),"📊 Ticket Volume Trend","Tickets"),use_container_width=True,config={"displayModeBar":False})
        st.caption("3D columns show total ticket volume for each selected time bucket.")
    else: msg("inf","No ticket trend data.","Try a wider date range.")
with b:
    if not vol.empty:
        d=vol.head(12).copy(); d["Label"]=d["Tower"].astype(str)+" → "+d["Track"].astype(str)
        st.plotly_chart(three_d_bars(d["Label"].tolist(),d["Total"].astype(int).tolist(),"🏢 Tower / Track Ticket Volume","Tickets",["#188da1","#73a945","#ed7a2b","#7d5ca5"]),use_container_width=True,config={"displayModeBar":False})
    else: msg("inf","No Tower / Track ticket volume.","No ticket rows match the selected filters.")

st.markdown('<div class="qbr-section">👑 Parent-Child & Alert Analysis</div>',unsafe_allow_html=True)
a,b=st.columns(2)
with a:
    if not pc_df.empty:
        d=pc_df.copy(); d["Relation"]=d["ParentTicket"].astype(str)+"  →  "+d["ChildCount"].astype(str)+" child"; d=d.head(10)
        st.plotly_chart(three_d_bars(d["Relation"].tolist(),d["ChildCount"].astype(int).tolist(),"👑 Parent → Child Concentration","Children",["#765e40","#9a7e4e","#b69662"]),use_container_width=True,config={"displayModeBar":False})
        st.markdown(f'<span class="qbr-pill" style="background:#e8f4ff;color:#155486;">{len(children_df)} child records</span><span class="qbr-pill" style="background:#e9faef;color:#17613a;">{len(pc_df)} parent groups</span>',unsafe_allow_html=True)
        with st.expander("🔍 View exact parent → child relationships"): st.dataframe(children_df,use_container_width=True,hide_index=True)
    else: msg("inf","No parent-child relationship rows.","The selected scope returned no Child tickets with ParentTicketNumber.")
with b:
    if not alerts.empty:
        d=alerts.groupby("Part",as_index=False)["Count"].sum().sort_values("Count",ascending=False).head(10).sort_values("Count")
        st.plotly_chart(three_d_bars(d["Part"].astype(str).tolist(),d["Count"].astype(int).tolist(),"⚡ Highest Alert / Part Frequency","Alerts",["#d2b24d","#ef8b34","#df3d2f","#c4161c"]),use_container_width=True,config={"displayModeBar":False})
    else: msg("inf","No alert frequency rows.","No alert rows match the selected filters.")

st.markdown('<div class="qbr-section">⚡ Tower / Track Alert Summary</div>',unsafe_allow_html=True)
if not alert_summary.empty:
    d=alert_summary.head(15).copy(); d["Label"]=d["Tower"].astype(str)+" → "+d["Track"].astype(str)
    st.plotly_chart(three_d_bars(d["Label"].tolist(),d["TotalAlerts"].astype(int).tolist(),"⚡ Tower / Track Alert Summary","Alerts",["#176e8c","#ee7d2b","#c71b24","#7a5aa7"]),use_container_width=True,config={"displayModeBar":False})
    st.dataframe(d[["Tower","Track","TotalAlerts","Critical","High","Moderate"]],use_container_width=True,hide_index=True)
else: msg("inf","No Tower / Track alert rows.","No alert rows match the selected filters.")

if r in ("SUPERUSER","SUPERVISOR"):
    st.markdown('<div class="qbr-section">👥 Manager & Role Administration</div>',unsafe_allow_html=True)
    st.caption("Assignment rule: one manager per Tower → Track, and one Tower → Track per manager.")
    users=manager_users(); active_managers=[u for u in users if str(u["RoleName"]).upper()=="MANAGER"]; towers=sorted(hierarchy.keys())
    if towers and active_managers:
        tsel=st.selectbox("Tower",towers,key="admin_tower"); trsel=st.selectbox("Track",[d["TrackName"] for d in hierarchy.get(tsel,[])],key="admin_track"); msel=st.selectbox("Manager",[u["Username"] for u in active_managers],format_func=lambda x:next((u["DisplayName"] for u in active_managers if u["Username"]==x),x),key="admin_manager")
        aa,bb,cc=st.columns(3)
        with aa:
            if st.button("➕ Assign Manager",use_container_width=True):
                ok,detail=assign_manager(msel,tsel,trsel); msg("ok" if ok else "bad","Assignment successful." if ok else "Assignment failed.",detail)
                if ok: st.rerun()
        with bb:
            if st.button("➖ Remove Manager",use_container_width=True):
                ok,detail=remove_manager(msel,tsel,trsel); msg("ok" if ok else "bad","Removal successful." if ok else "Removal failed.",detail)
                if ok: st.rerun()
        with cc:
            if st.button("🔄 Refresh Access",use_container_width=True): st.rerun()
    rows=admin_rows()
    if rows:
        df_admin=pd.DataFrame(rows)[["DisplayName","Username","RoleName","TowerName","TrackName","CanView","CanExport","CanManage"]].rename(columns={"DisplayName":"Manager","RoleName":"Role","TowerName":"Tower","TrackName":"Track","CanView":"View","CanExport":"Export","CanManage":"Manage"})
        st.dataframe(df_admin,use_container_width=True,hide_index=True)
    st.markdown("### 🛡️ Role Management")
    if users:
        role_user=st.selectbox("User",[u["Username"] for u in users],format_func=lambda x:next((f'{u["DisplayName"]}  •  current role: {u["RoleName"]}' for u in users if u["Username"]==x),x),key="role_user")
        current=next((str(u["RoleName"]).upper() for u in users if u["Username"]==role_user),""); roles=["MANAGER","SUPERVISOR","SUPERUSER"]
        new_role=st.selectbox(f"Current role: {current}",roles,index=roles.index(current) if current in roles else 0,key="new_role")
        if st.button("🛡️ Update Role",use_container_width=True):
            ok,detail=update_role(role_user,new_role); msg("ok" if ok else "bad","Role updated successfully." if ok else "Role update failed.",detail)
            if ok: st.rerun()

st.markdown('<div class="qbr-section">📗 Excel Analysis Pack</div>',unsafe_allow_html=True)
summary=pd.DataFrame([["Report Date",datetime.now().strftime("%Y-%m-%d %H:%M")],["Tower",tower],["Track",track],["From",start],["To",end],["Total Tickets",k.get("total",0)],["Parent Tickets",k.get("parents",0)],["Child Tickets",k.get("children",0)],["Alerts",alerts_total],["Max Tickets/Day",stats.get("max_count",0) if stats else 0],["Min Tickets/Day",stats.get("min_count",0) if stats else 0]],columns=["Metric","Value"])
buf=io.BytesIO()
with pd.ExcelWriter(buf,engine="openpyxl") as writer:
    summary.to_excel(writer,index=False,sheet_name="Executive Summary"); trend.to_excel(writer,index=False,sheet_name="Ticket Trend"); vol.to_excel(writer,index=False,sheet_name="Tower Track Volume"); alerts.to_excel(writer,index=False,sheet_name="Alert Frequency"); pc_df.to_excel(writer,index=False,sheet_name="Parent Child"); alert_summary.to_excel(writer,index=False,sheet_name="Alert Summary")
st.download_button("📗 Download Excel Analysis Pack",buf.getvalue(),"QBR_Executive_Analysis.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)
st.caption("The Excel pack contains separate analysis sheets suitable for Power Query / Power Pivot modelling. The Streamlit dashboard remains the live CPDB view.")
