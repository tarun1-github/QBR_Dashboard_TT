"""CPDB-backed analytics for the QBR Executive Dashboard.

The deployed CPDB has existed in more than one schema revision. This module
uses the live qbr tables as the source of truth and detects the available
columns so the dashboard does not depend on obsolete TicketNumber/ResolvedAt
columns or on a particular Tower/Track revision.
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import text
from app.db import SessionLocal


def _columns(db, table: str) -> set[str]:
    rows = db.execute(text("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA='qbr' AND TABLE_NAME=:table
    """), {"table": table}).fetchall()
    return {str(r[0]) for r in rows}


def _table_exists(db, table: str) -> bool:
    return bool(db.execute(text("""
        SELECT 1 FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA='qbr' AND TABLE_NAME=:table
    """), {"table": table}).first())


def _safe_int(value):
    return int(value or 0)


def _params(start_date=None, end_date=None, tower=None, track=None):
    return {"start_date": start_date, "end_date": end_date, "tower": tower, "track": track}


def _date_filter(alias: str, date_col: str) -> str:
    return f"(:start_date IS NULL OR {alias}.{date_col} >= :start_date) AND (:end_date IS NULL OR {alias}.{date_col} < DATEADD(day,1,:end_date))"


def _hierarchy_filter(alias: str, cols: set[str]) -> str:
    parts = []
    if "ProjectName" in cols:
        parts.append(f"(:tower IS NULL OR {alias}.ProjectName=:tower)")
    elif "TowerName" in cols:
        parts.append(f"(:tower IS NULL OR {alias}.TowerName=:tower)")
    if "TrackName" in cols:
        parts.append(f"(:track IS NULL OR {alias}.TrackName=:track)")
    return " AND ".join(parts) if parts else "1=1"


def get_tower_track_hierarchy():
    db = SessionLocal()
    try:
        if _table_exists(db, "TowerTrack"):
            rows = db.execute(text("""
                SELECT TowerTrackID,TowerName,TrackName FROM qbr.TowerTrack
                WHERE ISNULL(IsActive,1)=1 ORDER BY TowerName,TrackName
            """)).fetchall()
            out = {}
            for r in rows:
                out.setdefault(r.TowerName, []).append({"TowerTrackID": r.TowerTrackID, "TrackName": r.TrackName})
            return out
        rows = db.execute(text("""
            SELECT t.TowerID,tr.TrackID,t.TowerName,tr.TrackName
            FROM qbr.Tower t JOIN qbr.Track tr ON tr.TowerID=t.TowerID
            WHERE ISNULL(t.IsActive,1)=1 AND ISNULL(tr.IsActive,1)=1
            ORDER BY ISNULL(t.DisplayOrder,9999),t.TowerName,ISNULL(tr.DisplayOrder,9999),tr.TrackName
        """)).fetchall()
        out = {}
        for r in rows:
            out.setdefault(r.TowerName, []).append({"TowerTrackID": r.TrackID, "TrackName": r.TrackName})
        return out
    finally:
        db.close()


def get_executive_kpis(start_date=None,end_date=None,tower=None,track=None):
    db=SessionLocal()
    try:
        cols=_columns(db,"Ticket")
        date_col="OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        parent="CASE WHEN tk.TicketType='Parent' THEN 1 ELSE 0 END" if "TicketType" in cols else "0"
        child="CASE WHEN tk.TicketType='Child' THEN 1 ELSE 0 END" if "TicketType" in cols else "0"
        closed="CASE WHEN tk.ClosedAt IS NOT NULL THEN 1 ELSE 0 END" if "ClosedAt" in cols else "CASE WHEN LOWER(ISNULL(tk.State,''))='closed' THEN 1 ELSE 0 END"
        priority="ISNULL(tk.Priority,'')" if "Priority" in cols else "''"
        q=f"""SELECT COUNT(*) Total,SUM({parent}) Parents,SUM({child}) Children,SUM({closed}) Closed,
            SUM(CASE WHEN {priority} IN ('1 - Critical','Critical','1') THEN 1 ELSE 0 END) Critical,
            SUM(CASE WHEN {priority} IN ('2 - High','High','2') THEN 1 ELSE 0 END) High,
            SUM(CASE WHEN {priority} IN ('3 - Moderate','Moderate','3','Medium') THEN 1 ELSE 0 END) Moderate
            FROM qbr.Ticket tk WHERE {_date_filter('tk',date_col)} AND {_hierarchy_filter('tk',cols)}"""
        r=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchone()
        return {"total":_safe_int(r.Total),"parents":_safe_int(r.Parents),"children":_safe_int(r.Children),"closed":_safe_int(r.Closed),"critical":_safe_int(r.Critical),"high":_safe_int(r.High),"moderate":_safe_int(r.Moderate)}
    finally: db.close()


def get_alert_total(start_date=None,end_date=None,tower=None,track=None):
    db=SessionLocal()
    try:
        cols=_columns(db,"Alert")
        q=f"SELECT COUNT(*) FROM qbr.Alert a WHERE {_date_filter('a','AlertTime')} AND {_hierarchy_filter('a',cols)}"
        return _safe_int(db.execute(text(q),_params(start_date,end_date,tower,track)).scalar())
    finally: db.close()


def get_tower_track_volume(start_date=None,end_date=None,tower=None,track=None):
    db=SessionLocal()
    try:
        cols=_columns(db,"Ticket")
        date_col="OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        if {"ProjectName","TrackName"}.issubset(cols):
            q=f"""SELECT ISNULL(tk.ProjectName,'Unknown') Tower,ISNULL(tk.TrackName,'Unknown') Track,COUNT(*) Total,
                SUM(CASE WHEN tk.TicketType='Parent' THEN 1 ELSE 0 END) Parents,
                SUM(CASE WHEN tk.TicketType='Child' THEN 1 ELSE 0 END) Children
                FROM qbr.Ticket tk WHERE {_date_filter('tk',date_col)} AND {_hierarchy_filter('tk',cols)}
                GROUP BY tk.ProjectName,tk.TrackName ORDER BY Total DESC"""
        else:
            q=f"""SELECT t.TowerName Tower,tr.TrackName Track,COUNT(tk.TicketKey) Total,
                SUM(CASE WHEN tk.TicketType='Parent' THEN 1 ELSE 0 END) Parents,
                SUM(CASE WHEN tk.TicketType='Child' THEN 1 ELSE 0 END) Children
                FROM qbr.Tower t JOIN qbr.Track tr ON tr.TowerID=t.TowerID
                LEFT JOIN qbr.Ticket tk ON tk.TowerID=t.TowerID AND tk.TrackID=tr.TrackID AND {_date_filter('tk',date_col)}
                WHERE (:tower IS NULL OR t.TowerName=:tower) AND (:track IS NULL OR tr.TrackName=:track)
                GROUP BY t.TowerName,tr.TrackName ORDER BY Total DESC"""
        rows=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchall()
        return pd.DataFrame([{"Tower":r.Tower,"Track":r.Track,"Total":_safe_int(r.Total),"Parents":_safe_int(r.Parents),"Children":_safe_int(r.Children)} for r in rows])
    finally: db.close()


def _trend(start_date,end_date,tower,track,period):
    db=SessionLocal()
    try:
        cols=_columns(db,"Ticket"); date_col="OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        if period=='day': bucket=f"CAST(tk.{date_col} AS date)"; label='Date'; group=bucket
        elif period=='week': bucket=f"DATEADD(week,DATEDIFF(week,0,tk.{date_col}),0)"; label='Week'; group=bucket
        elif period=='month': bucket=f"DATEFROMPARTS(YEAR(tk.{date_col}),MONTH(tk.{date_col}),1)"; label='Month'; group=f"YEAR(tk.{date_col}),MONTH(tk.{date_col})"
        else: bucket=f"DATEFROMPARTS(YEAR(tk.{date_col}),((DATEPART(quarter,tk.{date_col})-1)*3)+1,1)"; label='Quarter'; group=f"YEAR(tk.{date_col}),DATEPART(quarter,tk.{date_col})"
        q=f"""SELECT {bucket} Bucket,COUNT(*) Total,SUM(CASE WHEN tk.TicketType='Parent' THEN 1 ELSE 0 END) Parents,SUM(CASE WHEN tk.TicketType='Child' THEN 1 ELSE 0 END) Children
            FROM qbr.Ticket tk WHERE tk.{date_col} IS NOT NULL AND {_date_filter('tk',date_col)} AND {_hierarchy_filter('tk',cols)}
            GROUP BY {group} ORDER BY Bucket"""
        rows=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchall(); data=[]
        for r in rows:
            b=r.Bucket
            x=b.strftime('%d %b %Y') if period=='day' else b.strftime('%d %b') if period=='week' else b.strftime('%b %Y') if period=='month' else f"Q{((b.month-1)//3)+1} {b.year}"
            data.append({label:x,"Total":_safe_int(r.Total),"Parents":_safe_int(r.Parents),"Children":_safe_int(r.Children)})
        return pd.DataFrame(data)
    finally: db.close()


def get_daily_trend(*args): return _trend(*args,'day')
def get_weekly_trend(*args): return _trend(*args,'week')
def get_monthly_trend(*args): return _trend(*args,'month')
def get_quarterly_trend(*args): return _trend(*args,'quarter')


def get_alert_frequency(start_date=None,end_date=None,tower=None,track=None):
    db=SessionLocal()
    try:
        cols=_columns(db,"Alert")
        q=f"""SELECT ISNULL(a.Part,'Unknown') Part,ISNULL(a.AlertType,'Unknown') AlertType,ISNULL(a.Severity,'Unknown') Severity,COUNT(*) AlertCount
            FROM qbr.Alert a WHERE {_date_filter('a','AlertTime')} AND {_hierarchy_filter('a',cols)}
            GROUP BY ISNULL(a.Part,'Unknown'),ISNULL(a.AlertType,'Unknown'),ISNULL(a.Severity,'Unknown') ORDER BY AlertCount DESC,Part"""
        rows=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchall()
        return pd.DataFrame([{"Part":r.Part,"AlertType":r.AlertType,"Severity":r.Severity,"Count":_safe_int(r.AlertCount)} for r in rows])
    finally: db.close()


def get_parent_child_relation(start_date=None,end_date=None,tower=None,track=None):
    db=SessionLocal()
    try:
        cols=_columns(db,"Ticket"); date_col="OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        if "ParentTicketNumber" not in cols: return pd.DataFrame(),pd.DataFrame()
        ticket_id="CAST(c.TicketKey AS nvarchar(100))" if "TicketKey" in cols else "CAST(c.ID AS nvarchar(100))"
        q=f"""SELECT CAST(c.ParentTicketNumber AS nvarchar(255)) ParentTicket,ISNULL(c.ProjectName,'Unknown') Tower,ISNULL(c.TrackName,'Unknown') Track,COUNT(*) ChildCount,MAX(c.Priority) Priority,MAX(c.State) State
            FROM qbr.Ticket c WHERE c.TicketType='Child' AND c.ParentTicketNumber IS NOT NULL AND {_date_filter('c',date_col)} AND {_hierarchy_filter('c',cols)}
            GROUP BY CAST(c.ParentTicketNumber AS nvarchar(255)),c.ProjectName,c.TrackName ORDER BY ChildCount DESC"""
        rows=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchall()
        parents=pd.DataFrame([{"ParentTicket":r.ParentTicket,"Tower":r.Tower,"Track":r.Track,"ChildCount":_safe_int(r.ChildCount),"Priority":r.Priority,"State":r.State} for r in rows])
        q2=f"""SELECT {ticket_id} ChildTicket,CAST(c.ParentTicketNumber AS nvarchar(255)) ParentTicket,ISNULL(c.ProjectName,'Unknown') Tower,ISNULL(c.TrackName,'Unknown') Track,c.Priority,c.State
            FROM qbr.Ticket c WHERE c.TicketType='Child' AND c.ParentTicketNumber IS NOT NULL AND {_date_filter('c',date_col)} AND {_hierarchy_filter('c',cols)} ORDER BY c.ParentTicketNumber,{ticket_id}"""
        rows2=db.execute(text(q2),_params(start_date,end_date,tower,track)).fetchall()
        children=pd.DataFrame([{"ChildTicket":r.ChildTicket,"ParentTicket":r.ParentTicket,"Tower":r.Tower,"Track":r.Track,"Priority":r.Priority,"State":r.State} for r in rows2])
        return parents,children
    finally: db.close()


def get_volume_stats(start_date=None,end_date=None,tower=None,track=None):
    db=SessionLocal()
    try:
        cols=_columns(db,"Ticket"); date_col="OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        q=f"""WITH d AS (SELECT CAST(tk.{date_col} AS date) TicketDate,COUNT(*) DailyTotal FROM qbr.Ticket tk WHERE tk.{date_col} IS NOT NULL AND {_date_filter('tk',date_col)} AND {_hierarchy_filter('tk',cols)} GROUP BY CAST(tk.{date_col} AS date))
            SELECT MAX(DailyTotal) MaxCount,MIN(DailyTotal) MinCount,AVG(CAST(DailyTotal AS float)) AvgCount,(SELECT TOP 1 TicketDate FROM d ORDER BY DailyTotal DESC,TicketDate) MaxDate,(SELECT TOP 1 TicketDate FROM d ORDER BY DailyTotal ASC,TicketDate) MinDate FROM d"""
        r=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchone()
        if not r or r.MaxCount is None:return None
        return {"max_count":_safe_int(r.MaxCount),"min_count":_safe_int(r.MinCount),"avg_count":round(float(r.AvgCount),1),"max_date":r.MaxDate,"min_date":r.MinDate}
    finally: db.close()


def get_tower_track_alerts(start_date=None,end_date=None,tower=None,track=None):
    db=SessionLocal()
    try:
        cols=_columns(db,"Alert")
        q=f"""SELECT ISNULL(a.ProjectName,'Unknown') Tower,ISNULL(a.TrackName,'Unknown') Track,COUNT(*) TotalAlerts,SUM(CASE WHEN a.Severity='Critical' THEN 1 ELSE 0 END) Critical,SUM(CASE WHEN a.Severity='High' THEN 1 ELSE 0 END) High,SUM(CASE WHEN a.Severity='Moderate' THEN 1 ELSE 0 END) Moderate
            FROM qbr.Alert a WHERE {_date_filter('a','AlertTime')} AND {_hierarchy_filter('a',cols)} GROUP BY a.ProjectName,a.TrackName ORDER BY TotalAlerts DESC,a.ProjectName,a.TrackName"""
        rows=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchall()
        return pd.DataFrame([{"Tower":r.Tower,"Track":r.Track,"TotalAlerts":_safe_int(r.TotalAlerts),"Critical":_safe_int(r.Critical),"High":_safe_int(r.High),"Moderate":_safe_int(r.Moderate)} for r in rows])
    finally: db.close()
