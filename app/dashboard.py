"""QBR Executive Dashboard - CPDB driven customer command center."""
from __future__ import annotations

import io
from datetime import date, datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import text

from app.db import SessionLocal
from app.login_block import render_login, render_flash, initialise_auth_state, clear_session
from app.dashboard_data import (
    get_tower_track_hierarchy, get_executive_kpis, get_alert_total,
    get_tower_track_volume, get_daily_trend, get_weekly_trend,
    get_monthly_trend, get_quarterly_trend, get_alert_frequency,
    get_parent_child_relation, get_volume_stats, get_tower_track_alerts,
)

st.set_page_config(page_title="QBR Executive Dashboard", page_icon="📊", layout="wide")
initialise_auth_state()
if not st.session_state.get("user"):
    render_flash(); render_login(); st.stop()
render_flash()

st.markdown("""
<style>
[data-testid="stAppViewContainer"]{background:linear-gradient(135deg,#f7fbfd,#eaf5f7 55%,#e1f0f2);}
.main .block-container{padding-top:1rem;padding-bottom:2rem;}
section[data-testid="stSidebar"]{background:linear-gradient(180deg,#0d2e4a,#075d78 52%,#087b79)!important;box-shadow:8px 0 25px rgba(0,0,0,.18);}
.qbr-side-title,.qbr-side-head{color:#fff;font-weight:900;letter-spacing:.5px;border-radius:15px;padding:10px 13px;margin:7px 0 10px;background:linear-gradient(135deg,#0c4967,#138b9a,#159d8b);box-shadow:5px 6px 0 rgba(0,0,0,.18);}
.qbr-side-head{font-size:12px;margin-top:12px;}
section[data-testid="stSidebar"] .stButton>button{border-radius:18px!important;background:linear-gradient(145deg,#fff,#e7f2f5)!important;color:#12344d!important;font-weight:800!important;box-shadow:5px 6px 0 rgba(0,0,0,.17)!important;}
section[data-testid="stSidebar"] div[data-baseweb="select"]>div,section[data-testid="stSidebar"] input{border-radius:15px!important;background:#fff!important;color:#12344d!important;}
.qbr-hero{padding:22px 28px;border-radius:25px;background:linear-gradient(135deg,#0c2d48,#126b86,#21a58d);color:#fff;box-shadow:0 15px 30px rgba(12,45,72,.25),7px 7px 0 rgba(12,45,72,.12);margin-bottom:18px;}
.qbr-hero h1{margin:0;font:900 34px 'Segoe UI',Aptos,sans-serif}.qbr-hero p{margin:7px 0 0;font-size:14px}
.qbr-section{font:900 23px 'Segoe UI',Aptos,sans-serif;color:#12344d;margin:20px 0 9px;padding:9px 15px;border-radius:15px;background:linear-gradient(135deg,#e9f5f7,#fff);box-shadow:3px 4px 0 rgba(15,39,66,.08);}
.qbr-kpi{min-height:112px;padding:17px 18px;border-radius:21px;color:#fff;box-shadow:0 12px 24px rgba(15,39,66,.20),6px 7px 0 rgba(15,39,66,.10),inset 0 1px rgba(255,255,255,.3);}
.qbr-kpi .t{font-size:11px;font-weight:900;letter-spacing:.5px}.qbr-kpi .v{font-size:31px;font-weight:900;margin-top:7px;text-shadow:0 2px 4px rgba(0,0,0,.2)}.qbr-kpi .s{font-size:10px}
.qbr-card{padding:14px 17px;border-radius:18px;background:linear-gradient(145deg,#fff,#eef6f8);box-shadow:7px 8px 0 rgba(15,39,66,.10),0 12px 25px rgba(15,39,66,.10);border:1px solid #d7e6ea;}
.stButton>button,.stDownloadButton>button{border-radius:16px!important;font-weight:800!important;box-shadow:4px 5px 0 rgba(15,39,66,.14)!important;}
.js-plotly-plot{border-radius:18px;overflow:hidden;box-shadow:0 9px 25px rgba(15,39,66,.12);}
.qbr-msg{padding:12px 16px;border-radius:15px;margin:10px 0;box-shadow:5px 6px 0 rgba(15,39,66,.10);font-weight:700}.ok{background:#e8faef;border:1px solid #72c994;color:#12623a}.bad{background:#fff0f0;border:1px solid #e28b8b;color:#982323}.inf{background:#eaf5ff;border:1px solid #80b6e7;color:#185486}
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
        if db.execute(text("SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='qbr' AND TABLE_NAME='UserTrackAccess' AND COLUMN_NAME='TowerTrackID'")).first():
            q="""SELECT tt.TowerName,tt.TrackName FROM qbr.UserTrackAccess a JOIN qbr.AppUser u ON u.UserID=a.UserID JOIN qbr.TowerTrack tt ON tt.TowerTrackID=a.TowerTrackID WHERE LOWER(u.Username)=LOWER(:u) AND ISNULL(tt.IsActive,1)=1 ORDER BY tt.TowerName,tt.TrackName"""
        else:
            q="""SELECT t.TowerName,tr.TrackName FROM qbr.UserTrackAccess a JOIN qbr.AppUser u ON u.UserID=a.UserID JOIN qbr.Track tr ON tr.TrackID=a.TrackID JOIN qbr.Tower t ON t.TowerID=tr.TowerID WHERE LOWER(u.Username)=LOWER(:u) AND ISNULL(tr.IsActive,1)=1 ORDER BY t.TowerName,tr.TrackName"""
        return [(r[0],r[1]) for r in db.execute(text(q),{"u":username}).fetchall()]
    finally: db.close()

def admin_rows():
    db=SessionLocal()
    try:
        q="""SELECT u.DisplayName,u.Username,u.RoleName,tt.TowerName,tt.TrackName,uta.CanView,uta.CanExport,uta.CanManage,uta.UserTrackAccessID FROM qbr.UserTrackAccess uta JOIN qbr.AppUser u ON u.UserID=uta.UserID JOIN qbr.TowerTrack tt ON tt.TowerTrackID=uta.TowerTrackID WHERE ISNULL(tt.IsActive,1)=1 ORDER BY tt.TowerName,tt.TrackName,u.DisplayName"""
        return db.execute(text(q)).mappings().all()
    finally: db.close()

def manager_users():
    db=SessionLocal()
    try:
        return db.execute(text("SELECT UserID,Username,DisplayName,RoleName,IsActive FROM qbr.AppUser WHERE IsActive=1 ORDER BY DisplayName")).mappings().all()
    finally: db.close()

def assign_manager(username,tower,track):
    db=SessionLocal()
    try:
        u=db.execute(text("SELECT UserID,DisplayName,RoleName FROM qbr.AppUser WHERE LOWER(Username)=LOWER(:u)"),{"u":username}).mappings().first()
        tt=db.execute(text("SELECT TowerTrackID FROM qbr.TowerTrack WHERE TowerName=:t AND TrackName=:tr AND IsActive=1"),{"t":tower,"tr":track}).mappings().first()
        if not u or not tt:return False,"User or track not found."
        if str(u["RoleName"]).upper()!="MANAGER":return False,f'{u["DisplayName"]} current role is {u["RoleName"]}. Only MANAGER can be assigned.'
        exists=db.execute(text("""SELECT u.DisplayName,tt.TowerName,tt.TrackName FROM qbr.UserTrackAccess a JOIN qbr.AppUser u ON u.UserID=a.UserID JOIN qbr.TowerTrack tt ON tt.TowerTrackID=a.TowerTrackID WHERE a.UserID=:uid"""),{"uid":u["UserID"]}).mappings().first()
        if exists:return False,f'{u["DisplayName"]} is already assigned to {exists["TowerName"]} → {exists["TrackName"]}. One track per manager.'
        occupied=db.execute(text("""SELECT u.DisplayName FROM qbr.UserTrackAccess a JOIN qbr.AppUser u ON u.UserID=a.UserID WHERE a.TowerTrackID=:tt AND UPPER(u.RoleName)='MANAGER'"""),{"tt":tt["TowerTrackID"]}).mappings().first()
        if occupied:return False,f'{tower} → {track} is already assigned to {occupied["DisplayName"]}. One manager per track.'
        db.execute(text("INSERT INTO qbr.UserTrackAccess(UserID,TowerTrackID,CanView,CanExport,CanManage) VALUES(:uid,:tt,1,1,0)"),{"uid":u["UserID"],"tt":tt["TowerTrackID"]})
        db.commit(); return True,f'{u["DisplayName"]} added to {tower} → {track} successfully.'
    except Exception as e: db.rollback(); return False,str(e)
    finally: db.close()

def remove_manager(username,tower,track):
    db=SessionLocal()
    try:
        r=db.execute(text("""DELETE a FROM qbr.UserTrackAccess a JOIN qbr.AppUser u ON u.UserID=a.UserID JOIN qbr.TowerTrack tt ON tt.TowerTrackID=a.TowerTrackID WHERE LOWER(u.Username)=LOWER(:u) AND tt.TowerName=:t AND tt.TrackName=:tr"""),{"u":username,"t":tower,"tr":track})
        if r.rowcount==0: db.rollback(); return False,f'{username} has no assignment on {tower} → {track}.'
        db.commit(); return True,f'{username} removed from {tower} → {track} successfully.'
    except Exception as e: db.rollback(); return False,str(e)
    finally: db.close()

def update_role(username,new_role):
    db=SessionLocal()
    try:
        old=db.execute(text("SELECT DisplayName,RoleName FROM qbr.AppUser WHERE LOWER(Username)=LOWER(:u)"),{"u":username}).mappings().first()
        if not old:return False,"User not found."
        db.execute(text("UPDATE qbr.AppUser SET RoleName=:r,UpdatedAt=SYSUTCDATETIME() WHERE LOWER(Username)=LOWER(:u)"),{"r":new_role,"u":username})
        if new_role in ("SUPERUSER","SUPERVISOR"):
            db.execute(text("DELETE a FROM qbr.UserTrackAccess a JOIN qbr.AppUser u ON u.UserID=a.UserID WHERE LOWER(u.Username)=LOWER(:u)"),{"u":username})
        db.commit(); return True,f'{old["DisplayName"]} role changed from {old["RoleName"]} to {new_role} successfully.'
    except Exception as e:db.rollback();return False,str(e)
    finally:db.close()

r=role(); title="Supervisor Dashboard" if r=="SUPERVISOR" else "Manager Dashboard" if r=="MANAGER" else "Superuser Dashboard"
st.markdown(f'<div class="qbr-hero"><h1>📊 QBR Executive Dashboard</h1><p>HCLTech Customer Operations Command Center &nbsp;•&nbsp; <b>{title}</b> &nbsp;•&nbsp; Signed in: <b>{dname()}</b> &nbsp;•&nbsp; Role: <b>{r}</b></p></div>',unsafe_allow_html=True)

hierarchy=get_tower_track_hierarchy()
with st.sidebar:
    st.markdown('<div class="qbr-side-title">🎛️ QBR DASHBOARD CONTROLS</div>',unsafe_allow_html=True)
    if st.button("🔄 Pull / Refresh Data",use_container_width=True): st.cache_data.clear(); st.rerun()
    if st.button("🔐 Change Password",use_container_width=True): st.session_state.auth_mode="change"; st.rerun()
    if st.button("🚪 Sign out",use_container_width=True): clear_session(); st.rerun()
    st.divider()
    allowed=assigned_tracks(uname()) if r=="MANAGER" else []
    tower_options=sorted({x[0] for x in allowed}) if r=="MANAGER" else list(hierarchy.keys())
    tower=st.selectbox("1️⃣ TOWER",["All"]+tower_options,label_visibility="visible")
    if tower=="All": tracks=sorted({d["TrackName"] for v in hierarchy.values() for d in v})
    else: tracks=[d["TrackName"] for d in hierarchy.get(tower,[])]
    if r=="MANAGER": tracks=[tr for tw,tr in allowed if tower=="All" or tw==tower]
    track=st.selectbox("2️⃣ TRACK",["All"]+tracks,label_visibility="visible")
    view=st.selectbox("3️⃣ TIME VIEW",["Day","Week","Month","Quarter"],index=0)
    st.markdown('<div class="qbr-side-head">📅 REPORT DATE RANGE</div>',unsafe_allow_html=True)
    dr=st.date_input("Report Date Range",value=(date(2026,7,15),min(date.today(),date(2026,8,31))),min_value=date(2020,1,1),max_value=date.today(),label_visibility="collapsed")

start=end=None
if isinstance(dr,(tuple,list)) and len(dr)==2: start,end=dr[0],dr[1]
elif isinstance(dr,date): start=end=dr
if r=="MANAGER" and allowed:
    if tower=="All" and len(allowed)==1: tower=allowed[0][0]
    if track=="All" and len(allowed)==1: track=allowed[0][1]

scope_tower=None if tower=="All" else tower
scope_track=None if track=="All" else track
k=get_executive_kpis(start,end,scope_tower,scope_track)
alerts_total=get_alert_total(start,end,scope_tower,scope_track)
vol=get_tower_track_volume(start,end,scope_tower,scope_track)
stats=get_volume_stats(start,end,scope_tower,scope_track)
alerts=get_alert_frequency(start,end,scope_tower,scope_track)
pc_df,children_df=get_parent_child_relation(start,end,scope_tower,scope_track)
alert_summary=get_tower_track_alerts(start,end,scope_tower,scope_track)

st.markdown('<div class="qbr-section">📈 Executive KPI Snapshot</div>',unsafe_allow_html=True)
kpis=[("🎫 TOTAL TICKETS",k["total"],"Selected timeframe","linear-gradient(135deg,#0d5470,#1d8a9a,#23a58c)"),("👑 PARENT TICKETS",k["parents"],"Root workload","linear-gradient(135deg,#4e7f32,#78a94d,#9bc96e)"),("↳ CHILD TICKETS",k["children"],"Linked workload","linear-gradient(135deg,#e87525,#f19a45,#f6bd73)"),("⚡ ALERTS",alerts_total,"Monitoring events","linear-gradient(135deg,#b80f17,#dc3038,#ef6868)"),("📊 MAX / MIN",f'{stats["max_count"] if stats else 0} / {stats["min_count"] if stats else 0}',"Tickets per day","linear-gradient(135deg,#7d6008,#a7831b,#c4a340)"),("📈 AVG / DAY",f'{stats["avg_count"] if stats else 0:,.1f}',"Daily average","linear-gradient(135deg,#315a9d,#4b7dcc,#789fe2)"),("🔵 OPEN",k["total"]-k["closed"],"Awaiting resolution","linear-gradient(135deg,#166db1,#268bd0,#61b5eb)"),("✅ CLOSED",k["closed"],"Resolved","linear-gradient(135deg,#2d8037,#52a85b,#82c886)"),("🔴 CRITICAL",k["critical"],"Critical priority","linear-gradient(135deg,#b62222,#db4747,#ee7777)")]
first_kpis=kpis[:5]; second_kpis=kpis[5:9]
for c,(lab,val,sub,bg) in zip(st.columns(5),first_kpis): c.markdown(f'<div class="qbr-kpi" style="background:{bg}"><div class="t">{lab}</div><div class="v">{val:,}</div><div class="s">{sub}</div></div>',unsafe_allow_html=True)
for c,(lab,val,sub,bg) in zip(st.columns(4),second_kpis): c.markdown(f'<div class="qbr-kpi" style="background:{bg}"><div class="t">{lab}</div><div class="v">{val:,}</div><div class="s">{sub}</div></div>',unsafe_allow_html=True)

if view=="Day": trend=get_daily_trend(start,end,scope_tower,scope_track); x="Date"
elif view=="Week": trend=get_weekly_trend(start,end,scope_tower,scope_track); x="Week"
elif view=="Month": trend=get_monthly_trend(start,end,scope_tower,scope_track); x="Month"
else: trend=get_quarterly_trend(start,end,scope_tower,scope_track); x="Quarter"

st.markdown('<div class="qbr-section">📊 Executive Volume & Trend</div>',unsafe_allow_html=True)
c1,c2=st.columns(2)
with c1:
    st.markdown("### 📈 Ticket Volume Trend")
    if not trend.empty:
        fig=go.Figure()
        for name,col,color in [("Parents","Parents","#19708b"),("Children","Children","#ee8233"),("Total","Total","#6b4f8f")]:
            if col in trend: fig.add_trace(go.Bar(x=trend[x],y=trend[col],name=name,marker=dict(color=color,line=dict(color="rgba(255,255,255,.8)",width=2)),text=trend[col],textposition="auto"))
        fig.update_layout(barmode="group",height=430,paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="#f7fbfd",font=dict(family="Segoe UI",color="#12344d"),margin=dict(l=20,r=20,t=25,b=45),xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#dce8ed"),legend=dict(orientation="h"))
        st.plotly_chart(fig,use_container_width=True)
    else: msg("inf","No ticket trend data","Try a wider date range.")
with c2:
    st.markdown("### 🏢 Tower / Track Ticket Volume")
    if not vol.empty:
        d=vol.head(15).sort_values("Total")
        fig=go.Figure(go.Bar(x=d.Total,y=d.Track,orientation="h",marker=dict(color=d.Total,colorscale=[[0,"#168b9a"],[.5,"#6a9d46"],[1,"#e56d2f"]],line=dict(color="white",width=2)),text=d.Total,textposition="auto",customdata=d.Tower,hovertemplate="<b>%{y}</b><br>Tower: %{customdata}<br>Tickets: %{x}<extra></extra>"))
        fig.update_layout(height=430,paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="#f7fbfd",font=dict(family="Segoe UI",color="#12344d"),margin=dict(l=20,r=20,t=25,b=35),xaxis=dict(gridcolor="#dce8ed"),yaxis=dict(showgrid=False))
        st.plotly_chart(fig,use_container_width=True)
    else: msg("inf","No ticket volume data","Check the selected Tower, Track and date range.")

st.markdown('<div class="qbr-section">👑 Parent-Child & Alert Analysis</div>',unsafe_allow_html=True)
c1,c2=st.columns(2)
with c1:
    st.markdown("### 👑 Highest Parent → Child Concentration")
    if not pc_df.empty:
        d=pc_df.head(10).sort_values("ChildCount")
        fig=go.Figure(go.Bar(x=d.ChildCount,y=d.ParentTicket,orientation="h",marker=dict(color=d.ChildCount,colorscale=[[0,"#2c7e9a"],[1,"#ee8233"]],line=dict(color="white",width=2)),text=d.ChildCount,textposition="auto",customdata=d.Track,hovertemplate="<b>Parent %{y}</b><br>Children: %{x}<br>Track: %{customdata}<extra></extra>"))
        fig.update_layout(height=400,paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="#f7fbfd",font=dict(family="Segoe UI",color="#12344d"),margin=dict(l=20,r=20,t=20,b=35),xaxis=dict(gridcolor="#dce8ed"),yaxis=dict(showgrid=False))
        st.plotly_chart(fig,use_container_width=True)
        with st.expander("🔍 View child ticket details"): st.dataframe(children_df,use_container_width=True,hide_index=True)
    else: msg("inf","Parent-child data not available","The dashboard found no child records for the selected scope.")
with c2:
    st.markdown("### ⚡ Highest Alert / Part Frequency")
    if not alerts.empty:
        d=alerts.head(12).sort_values("Count").copy(); d["Label"]=d["Part"]+" • "+d["AlertType"]
        fig=go.Figure(go.Bar(x=d.Count,y=d.Label,orientation="h",marker=dict(color=d.Count,colorscale=[[0,"#d6b24a"],[.5,"#ee8233"],[1,"#c91414"]],line=dict(color="white",width=2)),text=d.Count,textposition="auto",customdata=d.Severity,hovertemplate="<b>%{y}</b><br>Alerts: %{x}<br>Severity: %{customdata}<extra></extra>"))
        fig.update_layout(height=400,paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="#f7fbfd",font=dict(family="Segoe UI",color="#12344d"),margin=dict(l=20,r=20,t=20,b=35),xaxis=dict(gridcolor="#dce8ed"),yaxis=dict(showgrid=False))
        st.plotly_chart(fig,use_container_width=True)
    else: msg("inf","Alert data not available","Check the selected scope and date range.")

st.markdown('<div class="qbr-section">⚡ Tower / Track Alert Summary</div>',unsafe_allow_html=True)
if not alert_summary.empty:
    d=alert_summary.head(15).sort_values("TotalAlerts")
    fig=go.Figure(go.Bar(x=d.TotalAlerts,y=d.Track,orientation="h",marker=dict(color=d.TotalAlerts,colorscale=[[0,"#2c7e9a"],[.5,"#ee8233"],[1,"#c91414"]],line=dict(color="white",width=2)),text=d.TotalAlerts,textposition="auto",customdata=d.Tower,hovertemplate="<b>%{y}</b><br>Tower: %{customdata}<br>Alerts: %{x}<extra></extra>"))
    fig.update_layout(height=470,paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="#f7fbfd",font=dict(family="Segoe UI",color="#12344d"),margin=dict(l=20,r=20,t=20,b=35),xaxis=dict(gridcolor="#dce8ed"),yaxis=dict(showgrid=False))
    st.plotly_chart(fig,use_container_width=True); st.dataframe(alert_summary,use_container_width=True,hide_index=True)
else: msg("inf","No alert summary data","No alert rows match the selected filters.")

if r in ("SUPERUSER","SUPERVISOR"):
    st.markdown('<div class="qbr-section">👥 Manager & Role Administration</div>',unsafe_allow_html=True)
    st.caption("Assignment rule: one manager per Tower → Track, and one Tower → Track per manager.")
    users=manager_users(); active_managers=[u for u in users if str(u["RoleName"]).upper()=="MANAGER"]
    towers=list(hierarchy.keys()); selected_tower=st.selectbox("Tower",towers,key="admin_tower")
    selected_tracks=[d["TrackName"] for d in hierarchy.get(selected_tower,[])]
    selected_track=st.selectbox("Track",selected_tracks,key="admin_track")
    managers=st.selectbox("Manager",[u["Username"] for u in active_managers],format_func=lambda x: next((u["DisplayName"] for u in active_managers if u["Username"]==x),x),key="admin_manager") if active_managers else None
    a,b,c=st.columns(3)
    with a:
        if st.button("➕ Assign Manager",use_container_width=True) and managers:
            ok,detail=assign_manager(managers,selected_tower,selected_track); msg("ok" if ok else "bad","Assignment successful." if ok else "Assignment failed.",detail)
            if ok: st.rerun()
    with b:
        if st.button("➖ Remove Manager",use_container_width=True) and managers:
            ok,detail=remove_manager(managers,selected_tower,selected_track); msg("ok" if ok else "bad","Removal successful." if ok else "Removal failed.",detail)
            if ok: st.rerun()
    with c:
        if st.button("🔄 Refresh Access",use_container_width=True): st.rerun()
    rows=admin_rows()
    if rows:
        st.dataframe(pd.DataFrame(rows)[["DisplayName","Username","RoleName","TowerName","TrackName","CanView","CanExport","CanManage"]].rename(columns={"DisplayName":"Manager","RoleName":"Role","TowerName":"Tower","TrackName":"Track","CanView":"View","CanExport":"Export","CanManage":"Manage"}),use_container_width=True,hide_index=True)
    st.markdown("### 🛡️ Role Management")
    role_user=st.selectbox("User",[u["Username"] for u in users],format_func=lambda x: next((f'{u["DisplayName"]} ({u["RoleName"]})' for u in users if u["Username"]==x),x),key="role_user")
    current=next((u["RoleName"] for u in users if u["Username"]==role_user),"")
    roles=["MANAGER","SUPERVISOR","SUPERUSER"]
    new_role=st.selectbox(f"Current role: {current}",roles,index=roles.index(current) if current in roles else 0,key="new_role")
    if st.button("🛡️ Update Role",use_container_width=True):
        ok,detail=update_role(role_user,new_role); msg("ok" if ok else "bad","Role updated successfully." if ok else "Role update failed.",detail)
        if ok: st.rerun()

st.markdown('<div class="qbr-section">📥 Customer Report</div>',unsafe_allow_html=True)
summary=pd.DataFrame([["Report Date",datetime.now().strftime("%Y-%m-%d %H:%M")],["Tower",tower],["Track",track],["From",start],["To",end],["Total Tickets",k["total"]],["Parent Tickets",k["parents"]],["Child Tickets",k["children"]],["Alerts",alerts_total],["Max Tickets/Day",stats["max_count"] if stats else 0],["Min Tickets/Day",stats["min_count"] if stats else 0]],columns=["Metric","Value"])
all_export=pd.concat([summary,vol],ignore_index=True)
st.download_button("⬇️ Download CSV",all_export.to_csv(index=False).encode(),"QBR_Executive_Report.csv","text/csv",use_container_width=True)
buf=io.BytesIO()
with pd.ExcelWriter(buf,engine="openpyxl") as writer:
    summary.to_excel(writer,index=False,sheet_name="Executive Summary"); vol.to_excel(writer,index=False,sheet_name="Ticket Volume"); alerts.to_excel(writer,index=False,sheet_name="Alert Frequency"); pc_df.to_excel(writer,index=False,sheet_name="Parent Child"); alert_summary.to_excel(writer,index=False,sheet_name="Alert Summary")
st.download_button("📗 Download Excel",buf.getvalue(),"QBR_Executive_Report.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)
st.caption("Hierarchy: Tower → Track → Time View → Date Range → Tickets → Parent/Child → Alerts. Future dates are disabled.")
