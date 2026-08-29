"""CPDB-backed analytics for the QBR Executive Dashboard."""
from __future__ import annotations

import pandas as pd
from sqlalchemy import text
from app.db import SessionLocal


def _columns(db, table: str) -> set[str]:
    rows = db.execute(text("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='qbr' AND TABLE_NAME=:table"), {"table": table}).fetchall()
    return {str(r[0]) for r in rows}


def _table_exists(db, table: str) -> bool:
    return bool(db.execute(text("SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='qbr' AND TABLE_NAME=:table"), {"table": table}).first())


def _safe_int(value):
    try: return int(value or 0)
    except (TypeError, ValueError): return 0


def _params(start_date=None, end_date=None, tower=None, track=None):
    return {"start_date": start_date, "end_date": end_date, "tower": tower, "track": track}


def _date_filter(alias: str, date_col: str) -> str:
    return f"(:start_date IS NULL OR {alias}.{date_col} >= :start_date) AND (:end_date IS NULL OR {alias}.{date_col} < DATEADD(day,1,:end_date))"


def _ticket_context(db, alias: str = "tk"):
    """Resolve hierarchy from the ticket's stored ProjectName/TrackName first.

    The CPDB ticket rows already carry the business hierarchy. Prefer those
    values over potentially stale FK mappings so THD Data/SFNOC/HSBC Data
    cannot become an artificial 'Unknown' bucket in the dashboard.
    """
    cols = _columns(db, "Ticket")
    joins = ""
    tower_expr = f"ISNULL({alias}.ProjectName,'Unknown')" if "ProjectName" in cols else "'Unknown'"
    track_expr = f"ISNULL({alias}.TrackName,'Unknown')" if "TrackName" in cols else "'Unknown'"
    scope = []

    if "ProjectName" in cols:
        scope.append(f"(:tower IS NULL OR {alias}.ProjectName=:tower)")
    elif "TowerName" in cols:
        scope.append(f"(:tower IS NULL OR {alias}.TowerName=:tower)")
    if "TrackName" in cols:
        scope.append(f"(:track IS NULL OR {alias}.TrackName=:track)")

    # Fallback only when the business-name columns do not exist.
    if "ProjectName" not in cols and "TowerName" not in cols and {"TowerID", "TrackID"}.issubset(cols) and _table_exists(db, "Tower") and _table_exists(db, "Track"):
        joins = f" LEFT JOIN qbr.Tower t ON t.TowerID={alias}.TowerID LEFT JOIN qbr.Track tr ON tr.TrackID={alias}.TrackID"
        tower_expr = "ISNULL(t.TowerName,'Unknown')"
        track_expr = "ISNULL(tr.TrackName,'Unknown')"
        scope = ["(:tower IS NULL OR t.TowerName=:tower)", "(:track IS NULL OR tr.TrackName=:track)"]
    elif "ProjectName" not in cols and "TowerName" not in cols and "TowerTrackID" in cols and _table_exists(db, "TowerTrack"):
        joins = f" LEFT JOIN qbr.TowerTrack tt ON tt.TowerTrackID={alias}.TowerTrackID"
        tower_expr = "ISNULL(tt.TowerName,'Unknown')"
        track_expr = "ISNULL(tt.TrackName,'Unknown')"
        scope = ["(:tower IS NULL OR tt.TowerName=:tower)", "(:track IS NULL OR tt.TrackName=:track)"]

    return cols, joins, tower_expr, track_expr, (" AND ".join(scope) if scope else "1=1")


def _alert_context(db, alias: str = "a"):
    cols = _columns(db, "Alert")
    joins = ""
    tower_expr = f"ISNULL({alias}.ProjectName,'Unknown')" if "ProjectName" in cols else "'Unknown'"
    track_expr = f"ISNULL({alias}.TrackName,'Unknown')" if "TrackName" in cols else "'Unknown'"
    scope = []
    if "ProjectName" in cols:
        scope.append(f"(:tower IS NULL OR {alias}.ProjectName=:tower)")
    elif "TowerName" in cols:
        scope.append(f"(:tower IS NULL OR {alias}.TowerName=:tower)")
    if "TrackName" in cols:
        scope.append(f"(:track IS NULL OR {alias}.TrackName=:track)")

    if "ProjectName" not in cols and "TowerName" not in cols and {"TowerID", "TrackID"}.issubset(cols) and _table_exists(db, "Tower") and _table_exists(db, "Track"):
        joins = f" LEFT JOIN qbr.Tower t ON t.TowerID={alias}.TowerID LEFT JOIN qbr.Track tr ON tr.TrackID={alias}.TrackID"
        tower_expr = "ISNULL(t.TowerName,'Unknown')"
        track_expr = "ISNULL(tr.TrackName,'Unknown')"
        scope = ["(:tower IS NULL OR t.TowerName=:tower)", "(:track IS NULL OR tr.TrackName=:track)"]
    return cols, joins, tower_expr, track_expr, (" AND ".join(scope) if scope else "1=1")


def get_tower_track_hierarchy():
    db=SessionLocal()
    try:
        # Business hierarchy: Foundation is explicitly ordered as requested.
        if _table_exists(db,"TowerTrack"):
            rows=db.execute(text("SELECT TowerTrackID,TowerName,TrackName FROM qbr.TowerTrack WHERE ISNULL(IsActive,1)=1 ORDER BY CASE WHEN TowerName='Foundation' THEN 0 ELSE 1 END,TowerName,TrackName")).fetchall()
            out={}
            for r in rows: out.setdefault(r.TowerName,[]).append({"TowerTrackID":r.TowerTrackID,"TrackName":r.TrackName})
        else:
            rows=db.execute(text("SELECT t.TowerID,tr.TrackID,t.TowerName,tr.TrackName FROM qbr.Tower t JOIN qbr.Track tr ON tr.TowerID=t.TowerID WHERE ISNULL(t.IsActive,1)=1 AND ISNULL(tr.IsActive,1)=1 ORDER BY CASE WHEN t.TowerName='Foundation' THEN 0 ELSE 1 END,t.TowerName,tr.TrackName")).fetchall()
            out={}
            for r in rows: out.setdefault(r.TowerName,[]).append({"TowerTrackID":r.TrackID,"TrackName":r.TrackName})

        # Keep Foundation's business menu deterministic and free of accidental tracks.
        if "Foundation" in out:
            wanted=["SFNOC","THD Data","HSBC Data"]
            found={d["TrackName"]:d for d in out["Foundation"]}
            out["Foundation"]=[found[name] for name in wanted if name in found]
        return out
    finally: db.close()


def get_executive_kpis(start_date=None,end_date=None,tower=None,track=None):
    db=SessionLocal()
    try:
        cols,joins,_tower,_track,scope=_ticket_context(db,"tk"); date_col="OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        parent="CASE WHEN tk.TicketType='Parent' THEN 1 ELSE 0 END" if "TicketType" in cols else "0"
        child="CASE WHEN tk.TicketType='Child' THEN 1 ELSE 0 END" if "TicketType" in cols else "0"
        closed="CASE WHEN tk.ClosedAt IS NOT NULL THEN 1 ELSE 0 END" if "ClosedAt" in cols else "CASE WHEN LOWER(ISNULL(tk.State,''))='closed' THEN 1 ELSE 0 END"
        priority="ISNULL(tk.Priority,'')" if "Priority" in cols else "''"
        q=f"""SELECT COUNT(*) Total,SUM({parent}) Parents,SUM({child}) Children,SUM({closed}) Closed,
        SUM(CASE WHEN {priority} IN ('1 - Critical','Critical','1') THEN 1 ELSE 0 END) Critical,
        SUM(CASE WHEN {priority} IN ('2 - High','High','2') THEN 1 ELSE 0 END) High,
        SUM(CASE WHEN {priority} IN ('3 - Moderate','Moderate','3','Medium') THEN 1 ELSE 0 END) Moderate
        FROM qbr.Ticket tk {joins} WHERE {_date_filter('tk',date_col)} AND {scope}"""
        r=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchone()
        return {"total":_safe_int(r.Total),"parents":_safe_int(r.Parents),"children":_safe_int(r.Children),"closed":_safe_int(r.Closed),"critical":_safe_int(r.Critical),"high":_safe_int(r.High),"moderate":_safe_int(r.Moderate)}
    finally: db.close()


def get_alert_total(start_date=None,end_date=None,tower=None,track=None):
    db=SessionLocal()
    try:
        _cols,joins,_tower,_track,scope=_alert_context(db,"a")
        q=f"SELECT COUNT(*) FROM qbr.Alert a {joins} WHERE {_date_filter('a','AlertTime')} AND {scope}"
        return _safe_int(db.execute(text(q),_params(start_date,end_date,tower,track)).scalar())
    finally: db.close()


def get_tower_track_volume(start_date=None,end_date=None,tower=None,track=None):
    db=SessionLocal()
    try:
        cols,joins,tower_expr,track_expr,scope=_ticket_context(db,"tk"); date_col="OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        q=f"""SELECT {tower_expr} Tower,{track_expr} Track,COUNT(*) Total,
        SUM(CASE WHEN tk.TicketType='Parent' THEN 1 ELSE 0 END) Parents,
        SUM(CASE WHEN tk.TicketType='Child' THEN 1 ELSE 0 END) Children
        FROM qbr.Ticket tk {joins} WHERE {_date_filter('tk',date_col)} AND {scope}
        GROUP BY {tower_expr},{track_expr} ORDER BY Total DESC"""
        rows=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchall()
        return pd.DataFrame([{"Tower":r.Tower,"Track":r.Track,"Total":_safe_int(r.Total),"Parents":_safe_int(r.Parents),"Children":_safe_int(r.Children)} for r in rows])
    finally: db.close()


def _trend(start_date,end_date,tower,track,period):
    db=SessionLocal()
    try:
        cols,joins,_tower,_track,scope=_ticket_context(db,"tk"); date_col="OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        if period=='day': bucket=f"CAST(tk.{date_col} AS date)"; label='Date'; group=bucket
        elif period=='week': bucket=f"DATEADD(week,DATEDIFF(week,0,tk.{date_col}),0)"; label='Week'; group=bucket
        elif period=='month': bucket=f"DATEFROMPARTS(YEAR(tk.{date_col}),MONTH(tk.{date_col}),1)"; label='Month'; group=f"YEAR(tk.{date_col}),MONTH(tk.{date_col})"
        else: bucket=f"DATEFROMPARTS(YEAR(tk.{date_col}),((DATEPART(quarter,tk.{date_col})-1)*3)+1,1)"; label='Quarter'; group=f"YEAR(tk.{date_col}),DATEPART(quarter,tk.{date_col})"
        q=f"""SELECT {bucket} Bucket,COUNT(*) Total,SUM(CASE WHEN tk.TicketType='Parent' THEN 1 ELSE 0 END) Parents,SUM(CASE WHEN tk.TicketType='Child' THEN 1 ELSE 0 END) Children
        FROM qbr.Ticket tk {joins} WHERE tk.{date_col} IS NOT NULL AND {_date_filter('tk',date_col)} AND {scope}
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
        cols,joins,tower_expr,track_expr,scope=_alert_context(db,"a")
        q=f"""SELECT ISNULL(a.Part,'Unknown') Part,ISNULL(a.AlertType,'Unknown') AlertType,ISNULL(a.Severity,'Unknown') Severity,COUNT(*) AlertCount
        FROM qbr.Alert a {joins} WHERE {_date_filter('a','AlertTime')} AND {scope}
        GROUP BY ISNULL(a.Part,'Unknown'),ISNULL(a.AlertType,'Unknown'),ISNULL(a.Severity,'Unknown') ORDER BY AlertCount DESC,Part"""
        rows=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchall()
        return pd.DataFrame([{"Part":r.Part,"AlertType":r.AlertType,"Severity":r.Severity,"Count":_safe_int(r.AlertCount)} for r in rows])
    finally: db.close()


def get_parent_child_relation(start_date=None,end_date=None,tower=None,track=None):
    db=SessionLocal()
    try:
        cols,joins,tower_expr,track_expr,scope=_ticket_context(db,"c"); date_col="OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        if "ParentTicketNumber" not in cols or "TicketType" not in cols:return pd.DataFrame(),pd.DataFrame()
        ticket_id="CAST(c.TicketKey AS nvarchar(100))" if "TicketKey" in cols else "CAST(c.ID AS nvarchar(100))"
        q=f"""SELECT CAST(c.ParentTicketNumber AS nvarchar(255)) ParentTicket,{tower_expr} Tower,{track_expr} Track,COUNT(*) ChildCount,MAX(c.Priority) Priority,MAX(c.State) State
        FROM qbr.Ticket c {joins} WHERE c.TicketType='Child' AND c.ParentTicketNumber IS NOT NULL AND {_date_filter('c',date_col)} AND {scope}
        GROUP BY CAST(c.ParentTicketNumber AS nvarchar(255)),{tower_expr},{track_expr} ORDER BY ChildCount DESC"""
        rows=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchall()
        parents=pd.DataFrame([{"ParentTicket":r.ParentTicket,"Tower":r.Tower,"Track":r.Track,"ChildCount":_safe_int(r.ChildCount),"Priority":r.Priority,"State":r.State} for r in rows])
        q2=f"""SELECT {ticket_id} ChildTicket,CAST(c.ParentTicketNumber AS nvarchar(255)) ParentTicket,{tower_expr} Tower,{track_expr} Track,c.Priority,c.State
        FROM qbr.Ticket c {joins} WHERE c.TicketType='Child' AND c.ParentTicketNumber IS NOT NULL AND {_date_filter('c',date_col)} AND {scope}
        ORDER BY c.ParentTicketNumber,{ticket_id}"""
        rows2=db.execute(text(q2),_params(start_date,end_date,tower,track)).fetchall()
        children=pd.DataFrame([{"ChildTicket":r.ChildTicket,"ParentTicket":r.ParentTicket,"Tower":r.Tower,"Track":r.Track,"Priority":r.Priority,"State":r.State} for r in rows2])
        return parents,children
    finally: db.close()


def get_volume_stats(start_date=None,end_date=None,tower=None,track=None):
    db=SessionLocal()
    try:
        cols,joins,_tower,_track,scope=_ticket_context(db,"tk"); date_col="OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        q=f"""WITH d AS (SELECT CAST(tk.{date_col} AS date) TicketDate,COUNT(*) DailyTotal FROM qbr.Ticket tk {joins} WHERE tk.{date_col} IS NOT NULL AND {_date_filter('tk',date_col)} AND {scope} GROUP BY CAST(tk.{date_col} AS date))
        SELECT MAX(DailyTotal) MaxCount,MIN(DailyTotal) MinCount,AVG(CAST(DailyTotal AS float)) AvgCount,(SELECT TOP 1 TicketDate FROM d ORDER BY DailyTotal DESC,TicketDate) MaxDate,(SELECT TOP 1 TicketDate FROM d ORDER BY DailyTotal ASC,TicketDate) MinDate FROM d"""
        r=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchone()
        if not r or r.MaxCount is None:return None
        return {"max_count":_safe_int(r.MaxCount),"min_count":_safe_int(r.MinCount),"avg_count":round(float(r.AvgCount),1),"max_date":r.MaxDate,"min_date":r.MinDate}
    finally: db.close()


def get_tower_track_alerts(start_date=None,end_date=None,tower=None,track=None):
    db=SessionLocal()
    try:
        cols,joins,tower_expr,track_expr,scope=_alert_context(db,"a")
        q=f"""SELECT {tower_expr} Tower,{track_expr} Track,COUNT(*) TotalAlerts,SUM(CASE WHEN a.Severity='Critical' THEN 1 ELSE 0 END) Critical,SUM(CASE WHEN a.Severity='High' THEN 1 ELSE 0 END) High,SUM(CASE WHEN a.Severity='Moderate' THEN 1 ELSE 0 END) Moderate
        FROM qbr.Alert a {joins} WHERE {_date_filter('a','AlertTime')} AND {scope}
        GROUP BY {tower_expr},{track_expr} ORDER BY TotalAlerts DESC,Tower,Track"""
        rows=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchall()
        return pd.DataFrame([{"Tower":r.Tower,"Track":r.Track,"TotalAlerts":_safe_int(r.TotalAlerts),"Critical":_safe_int(r.Critical),"High":_safe_int(r.High),"Moderate":_safe_int(r.Moderate)} for r in rows])
    finally: db.close()
