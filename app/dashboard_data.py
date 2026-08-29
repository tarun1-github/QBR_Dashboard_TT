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
    cols=_columns(db,"Ticket"); joins=""
    has_tower="TowerID" in cols and _table_exists(db,"Tower"); has_track="TrackID" in cols and _table_exists(db,"Track"); has_tt="TowerTrackID" in cols and _table_exists(db,"TowerTrack")
    if has_tower: joins+=f" LEFT JOIN qbr.Tower t ON t.TowerID={alias}.TowerID"
    if has_track: joins+=f" LEFT JOIN qbr.Track tr ON tr.TrackID={alias}.TrackID"
    if has_tt: joins+=f" LEFT JOIN qbr.TowerTrack tt ON tt.TowerTrackID={alias}.TowerTrackID"
    ag=f"NULLIF(LTRIM(RTRIM({alias}.AssignmentGroup)),'')" if "AssignmentGroup" in cols else "NULL"
    tf=f"CASE WHEN UPPER(COALESCE({ag},'')) LIKE '%FN-SFNOC%' OR UPPER(COALESCE({ag},'')) LIKE '%FN-THD%' OR UPPER(COALESCE({ag},'')) LIKE '%HSBC-DATA%' THEN 'Foundation' ELSE NULL END"
    trf=f"CASE WHEN UPPER(COALESCE({ag},'')) LIKE '%FN-SFNOC%' THEN 'SFNOC' WHEN UPPER(COALESCE({ag},'')) LIKE '%FN-THD%' OR UPPER(COALESCE({ag},'')) LIKE '%JLK%' THEN 'THD Data' WHEN UPPER(COALESCE({ag},'')) LIKE '%HSBC-DATA%' THEN 'HSBC Data' ELSE NULL END"
    tp=[]; rp=[]
    if "ProjectName" in cols: tp.append(f"NULLIF(NULLIF(LTRIM(RTRIM({alias}.ProjectName)),''),'Unknown')")
    if has_tower: tp.append("t.TowerName")
    if has_tt: tp.append("tt.TowerName")
    tp.append(tf)
    if "TrackName" in cols: rp.append(f"NULLIF(NULLIF(LTRIM(RTRIM({alias}.TrackName)),''),'Unknown')")
    if has_track: rp.append("tr.TrackName")
    if has_tt: rp.append("tt.TrackName")
    rp.append(trf)
    tower_expr="COALESCE("+",".join(tp)+",'Unknown')"; track_expr="COALESCE("+",".join(rp)+",'Unknown')"
    return cols,joins,tower_expr,track_expr,f"(:tower IS NULL OR {tower_expr}=:tower) AND (:track IS NULL OR {track_expr}=:track)"


def _alert_context(db, alias: str = "a"):
    cols = _columns(db, "Alert")
    joins = ""
    has_tower = "TowerID" in cols and _table_exists(db, "Tower")
    has_track = "TrackID" in cols and _table_exists(db, "Track")
    has_tt = "TowerTrackID" in cols and _table_exists(db, "TowerTrack")
    if has_tower: joins += f" LEFT JOIN qbr.Tower t ON t.TowerID={alias}.TowerID"
    if has_track: joins += f" LEFT JOIN qbr.Track tr ON tr.TrackID={alias}.TrackID"
    if has_tt: joins += f" LEFT JOIN qbr.TowerTrack tt ON tt.TowerTrackID={alias}.TowerTrackID"
    assignment = f"NULLIF(LTRIM(RTRIM({alias}.AssignmentGroup)),'')" if "AssignmentGroup" in cols else "NULL"
    tower_fallback = f"CASE WHEN UPPER(COALESCE({assignment},'')) LIKE '%FN-SFNOC%' OR UPPER(COALESCE({assignment},'')) LIKE '%FN-THD%' OR UPPER(COALESCE({assignment},'')) LIKE '%HSBC-DATA%' THEN 'Foundation' ELSE NULL END"
    track_fallback = f"CASE WHEN UPPER(COALESCE({assignment},'')) LIKE '%FN-SFNOC%' THEN 'SFNOC' WHEN UPPER(COALESCE({assignment},'')) LIKE '%FN-THD%' OR UPPER(COALESCE({assignment},'')) LIKE '%JLK%' THEN 'THD Data' WHEN UPPER(COALESCE({assignment},'')) LIKE '%HSBC-DATA%' THEN 'HSBC Data' ELSE NULL END"
    tower_parts=[]; track_parts=[]
    if "ProjectName" in cols: tower_parts.append(f"NULLIF(NULLIF(LTRIM(RTRIM({alias}.ProjectName)),''),'Unknown')")
    if has_tower: tower_parts.append("t.TowerName")
    if has_tt: tower_parts.append("tt.TowerName")
    tower_parts.append(tower_fallback)
    if "TrackName" in cols: track_parts.append(f"NULLIF(NULLIF(LTRIM(RTRIM({alias}.TrackName)),''),'Unknown')")
    if has_track: track_parts.append("tr.TrackName")
    if has_tt: track_parts.append("tt.TrackName")
    track_parts.append(track_fallback)
    tower_expr="COALESCE("+",".join(tower_parts)+",'Unknown')"
    track_expr="COALESCE("+",".join(track_parts)+",'Unknown')"
    scope=" AND ".join([f"(:tower IS NULL OR {tower_expr}=:tower)",f"(:track IS NULL OR {track_expr}=:track)"])
    return cols,joins,tower_expr,track_expr,scope


def get_tower_track_hierarchy():
    db = SessionLocal()
    try:
        out = {}
        # Prefer TowerTrack, but also merge qbr.Tower/qbr.Track because some
        # environments have a partial TowerTrack catalogue.
        if _table_exists(db, "TowerTrack"):
            rows = db.execute(text("SELECT TowerTrackID,TowerName,TrackName FROM qbr.TowerTrack WHERE ISNULL(IsActive,1)=1 ORDER BY TowerName,TrackName")).fetchall()
            for r in rows:
                out.setdefault(str(r.TowerName), {})[str(r.TrackName)] = {"TowerTrackID": r.TowerTrackID, "TrackName": str(r.TrackName)}
        if _table_exists(db, "Tower") and _table_exists(db, "Track"):
            rows = db.execute(text("SELECT t.TowerID,tr.TrackID,t.TowerName,tr.TrackName FROM qbr.Tower t JOIN qbr.Track tr ON tr.TowerID=t.TowerID WHERE ISNULL(t.IsActive,1)=1 AND ISNULL(tr.IsActive,1)=1 ORDER BY t.TowerName,tr.TrackName")).fetchall()
            for r in rows:
                tower = str(r.TowerName); track = str(r.TrackName)
                out.setdefault(tower, {}).setdefault(track, {"TowerTrackID": r.TrackID, "TrackName": track})
        result = {tower: list(tracks.values()) for tower, tracks in out.items()}
        if "Foundation" in result:
            wanted = ["SFNOC", "THD Data", "HSBC Data"]
            found = {str(x["TrackName"]): x for x in result["Foundation"]}
            result["Foundation"] = [found[name] for name in wanted if name in found]
        return result
    finally:
        db.close()


def get_executive_kpis(start_date=None,end_date=None,tower=None,track=None):
    db=SessionLocal()
    try:
        cols,joins,_tower,_track,scope=_ticket_context(db,"tk"); date_col="OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        parent="CASE WHEN UPPER(ISNULL(tk.TicketType,''))='PARENT' THEN 1 ELSE 0 END" if "TicketType" in cols else "0"
        child="CASE WHEN UPPER(ISNULL(tk.TicketType,''))='CHILD' THEN 1 ELSE 0 END" if "TicketType" in cols else "0"
        closed="CASE WHEN tk.ClosedAt IS NOT NULL THEN 1 ELSE 0 END" if "ClosedAt" in cols else "CASE WHEN LOWER(ISNULL(tk.State,''))='closed' THEN 1 ELSE 0 END"
        priority="ISNULL(tk.Priority,'')" if "Priority" in cols else "''"
        q=f"SELECT COUNT(*) Total,SUM({parent}) Parents,SUM({child}) Children,SUM({closed}) Closed,SUM(CASE WHEN {priority} IN ('1 - Critical','Critical','1') THEN 1 ELSE 0 END) Critical,SUM(CASE WHEN {priority} IN ('2 - High','High','2') THEN 1 ELSE 0 END) High,SUM(CASE WHEN {priority} IN ('3 - Moderate','Moderate','3','Medium') THEN 1 ELSE 0 END) Moderate FROM qbr.Ticket tk {joins} WHERE {_date_filter('tk',date_col)} AND {scope}"
        r=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchone()
        return {"total":_safe_int(r.Total),"parents":_safe_int(r.Parents),"children":_safe_int(r.Children),"closed":_safe_int(r.Closed),"critical":_safe_int(r.Critical),"high":_safe_int(r.High),"moderate":_safe_int(r.Moderate)}
    finally: db.close()


def get_alert_total(start_date=None,end_date=None,tower=None,track=None):
    db=SessionLocal()
    try:
        _cols,joins,_tower,_track,scope=_alert_context(db,"a")
        return _safe_int(db.execute(text(f"SELECT COUNT(*) FROM qbr.Alert a {joins} WHERE {_date_filter('a','AlertTime')} AND {scope}"),_params(start_date,end_date,tower,track)).scalar())
    finally: db.close()


def get_tower_track_volume(start_date=None,end_date=None,tower=None,track=None):
    db=SessionLocal()
    try:
        cols,joins,tower_expr,track_expr,scope=_ticket_context(db,"tk"); date_col="OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        q=f"SELECT {tower_expr} Tower,{track_expr} Track,COUNT(*) Total,SUM(CASE WHEN UPPER(ISNULL(tk.TicketType,''))='PARENT' THEN 1 ELSE 0 END) Parents,SUM(CASE WHEN UPPER(ISNULL(tk.TicketType,''))='CHILD' THEN 1 ELSE 0 END) Children FROM qbr.Ticket tk {joins} WHERE {_date_filter('tk',date_col)} AND {scope} GROUP BY {tower_expr},{track_expr} ORDER BY Total DESC"
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
        q=f"SELECT {bucket} Bucket,COUNT(*) Total,SUM(CASE WHEN UPPER(ISNULL(tk.TicketType,''))='PARENT' THEN 1 ELSE 0 END) Parents,SUM(CASE WHEN UPPER(ISNULL(tk.TicketType,''))='CHILD' THEN 1 ELSE 0 END) Children FROM qbr.Ticket tk {joins} WHERE tk.{date_col} IS NOT NULL AND {_date_filter('tk',date_col)} AND {scope} GROUP BY {group} ORDER BY Bucket"
        rows=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchall(); data=[]
        for r in rows:
            b=r.Bucket; x=b.strftime('%d %b %Y') if period=='day' else b.strftime('%d %b') if period=='week' else b.strftime('%b %Y') if period=='month' else f"Q{((b.month-1)//3)+1} {b.year}"
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
        cols,joins,_tower,_track,scope=_alert_context(db,"a")
        device_expr="ISNULL(a.Part,'Unknown')" if "Part" in cols else ("ISNULL(a.Device,'Unknown')" if "Device" in cols else "'Unknown'")
        q=f"SELECT {device_expr} Device,ISNULL(a.AlertType,'Unknown') AlertType,ISNULL(a.Severity,'Unknown') Severity,COUNT(*) AlertCount FROM qbr.Alert a {joins} WHERE {_date_filter('a','AlertTime')} AND {scope} GROUP BY {device_expr},ISNULL(a.AlertType,'Unknown'),ISNULL(a.Severity,'Unknown') ORDER BY AlertCount DESC,Device"
        rows=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchall()
        return pd.DataFrame([{"Device":r.Device,"AlertType":r.AlertType,"Severity":r.Severity,"Count":_safe_int(r.AlertCount)} for r in rows])
    finally: db.close()


def get_parent_child_relation(start_date=None,end_date=None,tower=None,track=None):
    """Return parent groups and exact child TicketNumber values.

    The old implementation used TicketKey/TicketKey-like numeric IDs, which is
    why the UI showed values such as 131 instead of the actual ServiceNow
    ticket number. TicketNumber is the authoritative display identifier.
    """
    db=SessionLocal()
    try:
        cols,joins,tower_expr,track_expr,scope=_ticket_context(db,"c"); date_col="OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        if "ParentTicketNumber" not in cols or "TicketType" not in cols:return pd.DataFrame(),pd.DataFrame()
        ticket_id = "CAST(c.TicketNumber AS nvarchar(100))" if "TicketNumber" in cols else ("CAST(c.TicketKey AS nvarchar(100))" if "TicketKey" in cols else "CAST(c.ID AS nvarchar(100))")
        q=f"SELECT CAST(c.ParentTicketNumber AS nvarchar(255)) ParentTicket,{tower_expr} Tower,{track_expr} Track,COUNT(*) ChildCount,MAX(c.Priority) Priority,MAX(c.State) State FROM qbr.Ticket c {joins} WHERE UPPER(ISNULL(c.TicketType,''))='CHILD' AND c.ParentTicketNumber IS NOT NULL AND {_date_filter('c',date_col)} AND {scope} GROUP BY CAST(c.ParentTicketNumber AS nvarchar(255)),{tower_expr},{track_expr} ORDER BY ChildCount DESC"
        rows=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchall()
        parents=pd.DataFrame([{"ParentTicket":r.ParentTicket,"Tower":r.Tower,"Track":r.Track,"ChildCount":_safe_int(r.ChildCount),"Priority":r.Priority,"State":r.State} for r in rows])
        q2=f"SELECT {ticket_id} ChildTicket,CAST(c.ParentTicketNumber AS nvarchar(255)) ParentTicket,{tower_expr} Tower,{track_expr} Track,c.Priority,c.State FROM qbr.Ticket c {joins} WHERE UPPER(ISNULL(c.TicketType,''))='CHILD' AND c.ParentTicketNumber IS NOT NULL AND {_date_filter('c',date_col)} AND {scope} ORDER BY c.ParentTicketNumber,{ticket_id}"
        rows2=db.execute(text(q2),_params(start_date,end_date,tower,track)).fetchall()
        children=pd.DataFrame([{"ChildTicket":r.ChildTicket,"ParentTicket":r.ParentTicket,"Tower":r.Tower,"Track":r.Track,"Priority":r.Priority,"State":r.State} for r in rows2])
        return parents,children
    finally: db.close()


def get_volume_stats(start_date=None,end_date=None,tower=None,track=None):
    db=SessionLocal()
    try:
        cols,joins,_tower,_track,scope=_ticket_context(db,"tk"); date_col="OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        q=f"WITH d AS (SELECT CAST(tk.{date_col} AS date) TicketDate,COUNT(*) DailyTotal FROM qbr.Ticket tk {joins} WHERE tk.{date_col} IS NOT NULL AND {_date_filter('tk',date_col)} AND {scope} GROUP BY CAST(tk.{date_col} AS date)) SELECT MAX(DailyTotal) MaxCount,MIN(DailyTotal) MinCount,AVG(CAST(DailyTotal AS float)) AvgCount,(SELECT TOP 1 TicketDate FROM d ORDER BY DailyTotal DESC,TicketDate) MaxDate,(SELECT TOP 1 TicketDate FROM d ORDER BY DailyTotal ASC,TicketDate) MinDate FROM d"
        r=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchone()
        if not r or r.MaxCount is None:return None
        return {"max_count":_safe_int(r.MaxCount),"min_count":_safe_int(r.MinCount),"avg_count":round(float(r.AvgCount),1),"max_date":r.MaxDate,"min_date":r.MinDate}
    finally: db.close()


def get_tower_track_alerts(start_date=None,end_date=None,tower=None,track=None):
    db=SessionLocal()
    try:
        _cols,joins,tower_expr,track_expr,scope=_alert_context(db,"a")
        q=f"SELECT {tower_expr} Tower,{track_expr} Track,COUNT(*) TotalAlerts,SUM(CASE WHEN UPPER(ISNULL(a.Severity,'')) LIKE '%CRITICAL%' THEN 1 ELSE 0 END) Critical,SUM(CASE WHEN UPPER(ISNULL(a.Severity,'')) LIKE '%HIGH%' THEN 1 ELSE 0 END) High,SUM(CASE WHEN UPPER(ISNULL(a.Severity,'')) LIKE '%MODERATE%' OR UPPER(ISNULL(a.Severity,'')) LIKE '%MEDIUM%' THEN 1 ELSE 0 END) Moderate FROM qbr.Alert a {joins} WHERE {_date_filter('a','AlertTime')} AND {scope} GROUP BY {tower_expr},{track_expr} ORDER BY TotalAlerts DESC,Tower,Track"
        rows=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchall()
        return pd.DataFrame([{"Tower":r.Tower,"Track":r.Track,"TotalAlerts":_safe_int(r.TotalAlerts),"Critical":_safe_int(r.Critical),"High":_safe_int(r.High),"Moderate":_safe_int(r.Moderate)} for r in rows])
    finally: db.close()
