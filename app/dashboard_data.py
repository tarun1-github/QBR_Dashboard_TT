"""CPDB-backed analytics for the QBR Executive Dashboard.

Architecture rule:
    qbr.Ticket is the single fact table.
    qbr.Customer is the authoritative CompanyAccount -> Tower -> Track map.
    Caller containing EMS/CMSP identifies monitoring-generated tickets.

No dashboard query depends on qbr.Alert or qbr.TicketAlert.
"""
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
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _params(start_date=None, end_date=None, tower=None, track=None):
    return {"start_date": start_date, "end_date": end_date, "tower": tower, "track": track}


def _date_filter(alias: str, date_col: str) -> str:
    return f"(:start_date IS NULL OR {alias}.{date_col} >= :start_date) AND (:end_date IS NULL OR {alias}.{date_col} < DATEADD(day,1,:end_date))"


def _normal_account_expr(alias: str) -> str:
    return f"CASE WHEN UPPER(LTRIM(RTRIM(ISNULL({alias}.CompanyAccount,'')))) LIKE '%HOME%' THEN 'Home Depot' ELSE LTRIM(RTRIM(ISNULL({alias}.CompanyAccount,''))) END"


def _monitoring_predicate(alias: str = "tk") -> str:
    """Monitoring event rule: Caller contains EMS or CMSP."""
    return (
        f"(UPPER(LTRIM(RTRIM(ISNULL({alias}.Caller,'')))) LIKE '%EMS%' "
        f"OR UPPER(LTRIM(RTRIM(ISNULL({alias}.Caller,'')))) LIKE '%CMSP%')"
    )


def _ticket_context(db, alias: str = "tk"):
    """Resolve CompanyAccount -> Customer -> Tower/Track first, then legacy FK values."""
    cols = _columns(db, "Ticket")
    joins = ""

    if _table_exists(db, "Customer"):
        joins += (
            f" LEFT JOIN qbr.Customer cust "
            f"ON UPPER(LTRIM(RTRIM(ISNULL(cust.CompanyAccountName,''))))="
            f"UPPER({_normal_account_expr(alias)}) AND ISNULL(cust.IsActive,1)=1"
        )
        joins += " LEFT JOIN qbr.Track tr_cust ON tr_cust.TrackID=cust.TrackID AND ISNULL(tr_cust.IsActive,1)=1"
        joins += " LEFT JOIN qbr.Tower tw_cust ON tw_cust.TowerID=cust.TowerID AND ISNULL(tw_cust.IsActive,1)=1"

    if "TowerID" in cols and _table_exists(db, "Tower"):
        joins += f" LEFT JOIN qbr.Tower tw ON tw.TowerID={alias}.TowerID"
    if "TrackID" in cols and _table_exists(db, "Track"):
        joins += f" LEFT JOIN qbr.Track tr ON tr.TrackID={alias}.TrackID"

    track_parts = []
    if _table_exists(db, "Customer"):
        track_parts.append("NULLIF(LTRIM(RTRIM(tr_cust.TrackName)),'')")
    if "TrackName" in cols:
        track_parts.append(f"NULLIF(NULLIF(LTRIM(RTRIM({alias}.TrackName)),''),'Unknown')")
    if "TrackID" in cols and _table_exists(db, "Track"):
        track_parts.append("NULLIF(LTRIM(RTRIM(tr.TrackName)),'')")

    if "AssignmentGroup" in cols:
        ag = f"UPPER(LTRIM(RTRIM(ISNULL({alias}.AssignmentGroup,''))))"
        track_parts.append(
            "CASE "
            f"WHEN {ag} LIKE '%SFNOC%' THEN 'SFNOC' "
            f"WHEN {ag} LIKE '%THD%' OR {ag} LIKE '%JLK%' THEN 'THD Data' "
            f"WHEN {ag} LIKE '%HSBC%DATA%' THEN 'HSBC Data' "
            f"WHEN {ag} IN ('BOA EV','BOA-EV','BOA-EV-L1','BOA-EV-L2') THEN 'BOA EV' "
            f"WHEN {ag} LIKE '%PROBLEM MANAGEMENT%' THEN 'Problem Management' "
            f"WHEN {ag} IN ('BOA TP','BOA-TP') THEN 'BOA TP' "
            f"WHEN {ag} IN ('GTM TP','GTM-TP') THEN 'GTM TP' "
            f"WHEN {ag} LIKE '%HD VOICE%' THEN 'HD Voice (Bgl)' "
            f"WHEN {ag}='SCNOC' THEN 'SCNOC' "
            f"WHEN {ag} LIKE '%CYBER%' THEN 'Cybersecurity' "
            f"WHEN {ag}='DC-ACI' THEN 'DC-ACI' "
            f"WHEN {ag}='INFRA' THEN 'Infra' "
            f"WHEN {ag}='SOC' THEN 'SOC' "
            f"WHEN {ag} LIKE '%RIL%' THEN 'RIL' "
            "ELSE NULL END"
        )
    track_expr = "COALESCE(" + ",".join(track_parts) + ",'Unknown')"

    tower_parts = []
    if _table_exists(db, "Customer"):
        tower_parts.append("NULLIF(LTRIM(RTRIM(tw_cust.TowerName)),'')")
    if "TowerID" in cols and _table_exists(db, "Tower"):
        tower_parts.append("NULLIF(LTRIM(RTRIM(tw.TowerName)),'')")
    # ProjectName is not authoritative; keep only as a last legacy fallback.
    if "ProjectName" in cols:
        tower_parts.append(f"NULLIF(NULLIF(LTRIM(RTRIM({alias}.ProjectName)),''),'Unknown')")
    tower_parts.append(f"CASE WHEN {track_expr} IN ('SFNOC','THD Data','HSBC Data') THEN 'Foundation' ELSE NULL END")
    tower_expr = "COALESCE(" + ",".join(tower_parts) + ",'Unknown')"
    scope = f"(:tower IS NULL OR {tower_expr}=:tower) AND (:track IS NULL OR {track_expr}=:track)"
    return cols, joins, tower_expr, track_expr, scope


def get_tower_track_hierarchy():
    db = SessionLocal()
    try:
        rows = db.execute(text("SELECT t.TowerName,tr.TrackName FROM qbr.Track tr JOIN qbr.Tower t ON t.TowerID=tr.TowerID WHERE ISNULL(t.IsActive,1)=1 AND ISNULL(tr.IsActive,1)=1 ORDER BY t.DisplayOrder,tr.DisplayOrder,tr.TrackName")).fetchall()
        result = {}
        for row in rows:
            tower, track = str(row.TowerName), str(row.TrackName)
            if tower == "Foundation" and track.upper() in {"THD", "DATA FOUNDATION", "THD DATA"}:
                track = "THD Data"
            result.setdefault(tower, [])
            if track not in result[tower]:
                result[tower].append(track)
        if "Foundation" in result:
            desired = ["SFNOC", "THD Data", "HSBC Data"]
            result["Foundation"] = [x for x in desired if x in result["Foundation"]]
        return result
    finally:
        db.close()


def get_executive_kpis(start_date=None,end_date=None,tower=None,track=None):
    db=SessionLocal()
    try:
        cols,joins,_tower,_track,scope=_ticket_context(db,"tk")
        date_col="OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        parent="CASE WHEN UPPER(ISNULL(tk.TicketType,''))='PARENT' THEN 1 ELSE 0 END" if "TicketType" in cols else "0"
        child="CASE WHEN UPPER(ISNULL(tk.TicketType,''))='CHILD' THEN 1 ELSE 0 END" if "TicketType" in cols else "0"
        closed="CASE WHEN tk.ClosedAt IS NOT NULL THEN 1 ELSE 0 END" if "ClosedAt" in cols else "CASE WHEN LOWER(ISNULL(tk.State,''))='closed' THEN 1 ELSE 0 END"
        priority="ISNULL(tk.Priority,'')" if "Priority" in cols else "''"
        monitoring=f"CASE WHEN {_monitoring_predicate('tk')} THEN 1 ELSE 0 END" if "Caller" in cols else "0"
        q=f"SELECT COUNT(*) Total,SUM({parent}) Parents,SUM({child}) Children,SUM({closed}) Closed,SUM({monitoring}) Monitoring,SUM(CASE WHEN {priority} IN ('1 - Critical','Critical','1') THEN 1 ELSE 0 END) Critical,SUM(CASE WHEN {priority} IN ('2 - High','High','2') THEN 1 ELSE 0 END) High,SUM(CASE WHEN {priority} IN ('3 - Moderate','Moderate','3','Medium') THEN 1 ELSE 0 END) Moderate FROM qbr.Ticket tk {joins} WHERE {_date_filter('tk',date_col)} AND {scope}"
        r=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchone()
        return {"total":_safe_int(r.Total),"parents":_safe_int(r.Parents),"children":_safe_int(r.Children),"closed":_safe_int(r.Closed),"monitoring":_safe_int(r.Monitoring),"critical":_safe_int(r.Critical),"high":_safe_int(r.High),"moderate":_safe_int(r.Moderate)}
    finally: db.close()


def get_alert_total(start_date=None,end_date=None,tower=None,track=None):
    db=SessionLocal()
    try:
        cols,joins,_tower,_track,scope=_ticket_context(db,"tk")
        if "Caller" not in cols:return 0
        date_col="OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        pred=_monitoring_predicate("tk")
        q=f"SELECT COUNT(*) FROM qbr.Ticket tk {joins} WHERE {pred} AND {_date_filter('tk',date_col)} AND {scope}"
        return _safe_int(db.execute(text(q),_params(start_date,end_date,tower,track)).scalar())
    finally: db.close()


def get_tower_track_volume(start_date=None,end_date=None,tower=None,track=None):
    db=SessionLocal()
    try:
        cols,joins,tower_expr,track_expr,_scope=_ticket_context(db,"tk");date_col="OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        q=f"SELECT b.Tower,b.Track,COUNT(*) Total,SUM(CASE WHEN UPPER(ISNULL(b.TicketType,''))='PARENT' THEN 1 ELSE 0 END) Parents,SUM(CASE WHEN UPPER(ISNULL(b.TicketType,''))='CHILD' THEN 1 ELSE 0 END) Children FROM (SELECT {tower_expr} Tower,{track_expr} Track,tk.TicketType FROM qbr.Ticket tk {joins} WHERE {_date_filter('tk',date_col)}) b WHERE (:tower IS NULL OR b.Tower=:tower) AND (:track IS NULL OR b.Track=:track) GROUP BY b.Tower,b.Track ORDER BY Total DESC"
        rows=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchall()
        return pd.DataFrame([{"Tower":r.Tower,"Track":r.Track,"Total":_safe_int(r.Total),"Parents":_safe_int(r.Parents),"Children":_safe_int(r.Children)} for r in rows])
    finally: db.close()


def _trend(start_date,end_date,tower,track,period):
    db=SessionLocal()
    try:
        cols,joins,_tower,_track,scope=_ticket_context(db,"tk");date_col="OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        if period=="day": bucket=f"CAST(tk.{date_col} AS date)";label="Date";group=bucket
        elif period=="week": bucket=f"DATEADD(week,DATEDIFF(week,0,tk.{date_col}),0)";label="Week";group=bucket
        elif period=="month": bucket=f"DATEFROMPARTS(YEAR(tk.{date_col}),MONTH(tk.{date_col}),1)";label="Month";group=f"YEAR(tk.{date_col}),MONTH(tk.{date_col})"
        else: bucket=f"DATEFROMPARTS(YEAR(tk.{date_col}),((DATEPART(quarter,tk.{date_col})-1)*3)+1,1)";label="Quarter";group=f"YEAR(tk.{date_col}),DATEPART(quarter,tk.{date_col})"
        q=f"SELECT {bucket} Bucket,COUNT(*) Total,SUM(CASE WHEN UPPER(ISNULL(tk.TicketType,''))='PARENT' THEN 1 ELSE 0 END) Parents,SUM(CASE WHEN UPPER(ISNULL(tk.TicketType,''))='CHILD' THEN 1 ELSE 0 END) Children FROM qbr.Ticket tk {joins} WHERE tk.{date_col} IS NOT NULL AND {_date_filter('tk',date_col)} AND {scope} GROUP BY {group} ORDER BY Bucket"
        rows=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchall();data=[]
        for row in rows:
            b=row.Bucket;x=b.strftime("%d %b %Y") if period=="day" else b.strftime("%d %b") if period=="week" else b.strftime("%b %Y") if period=="month" else f"Q{((b.month-1)//3)+1} {b.year}"
            data.append({label:x,"Total":_safe_int(row.Total),"Parents":_safe_int(row.Parents),"Children":_safe_int(row.Children)})
        return pd.DataFrame(data)
    finally: db.close()


def get_daily_trend(*args): return _trend(*args,"day")
def get_weekly_trend(*args): return _trend(*args,"week")
def get_monthly_trend(*args): return _trend(*args,"month")
def get_quarterly_trend(*args): return _trend(*args,"quarter")


def get_alert_frequency(start_date=None,end_date=None,tower=None,track=None):
    db=SessionLocal()
    try:
        cols,joins,_tower,_track,scope=_ticket_context(db,"tk");date_col="OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        if "Caller" not in cols:return pd.DataFrame(columns=["Device","AlertType","Severity","Count"])
        device="ISNULL(tk.Device,'Unknown')" if "Device" in cols else ("ISNULL(tk.Part,'Unknown')" if "Part" in cols else "'Unknown'")
        pred=_monitoring_predicate("tk")
        q=f"SELECT {device} Device,'Monitoring-generated ticket' AlertType,ISNULL(tk.Priority,'Unknown') Severity,COUNT(*) AlertCount FROM qbr.Ticket tk {joins} WHERE {pred} AND {_date_filter('tk',date_col)} AND {scope} GROUP BY {device},ISNULL(tk.Priority,'Unknown') ORDER BY AlertCount DESC,Device"
        rows=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchall()
        return pd.DataFrame([{"Device":r.Device,"AlertType":r.AlertType,"Severity":r.Severity,"Count":_safe_int(r.AlertCount)} for r in rows])
    finally: db.close()


def get_parent_child_relation(start_date=None,end_date=None,tower=None,track=None):
    db=SessionLocal()
    try:
        cols,joins,tower_expr,track_expr,_scope=_ticket_context(db,"c");date_col="OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        if "ParentTicketNumber" not in cols or "TicketType" not in cols:return pd.DataFrame(),pd.DataFrame()
        ticket_id="CAST(c.TicketNumber AS nvarchar(100))" if "TicketNumber" in cols else "CAST(c.TicketKey AS nvarchar(100))"
        q=f"SELECT b.ParentTicket,b.Tower,b.Track,COUNT(*) ChildCount,MAX(b.Priority) Priority,MAX(b.State) State FROM (SELECT CAST(c.ParentTicketNumber AS nvarchar(255)) ParentTicket,{tower_expr} Tower,{track_expr} Track,c.Priority,c.State FROM qbr.Ticket c {joins} WHERE UPPER(ISNULL(c.TicketType,''))='CHILD' AND c.ParentTicketNumber IS NOT NULL AND {_date_filter('c',date_col)}) b WHERE (:tower IS NULL OR b.Tower=:tower) AND (:track IS NULL OR b.Track=:track) GROUP BY b.ParentTicket,b.Tower,b.Track ORDER BY ChildCount DESC"
        rows=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchall();parents=pd.DataFrame([{"ParentTicket":r.ParentTicket,"Tower":r.Tower,"Track":r.Track,"ChildCount":_safe_int(r.ChildCount),"Priority":r.Priority,"State":r.State} for r in rows])
        q2=f"SELECT b.ChildTicket,b.ParentTicket,b.Tower,b.Track,b.Priority,b.State FROM (SELECT {ticket_id} ChildTicket,CAST(c.ParentTicketNumber AS nvarchar(255)) ParentTicket,{tower_expr} Tower,{track_expr} Track,c.Priority,c.State FROM qbr.Ticket c {joins} WHERE UPPER(ISNULL(c.TicketType,''))='CHILD' AND c.ParentTicketNumber IS NOT NULL AND {_date_filter('c',date_col)}) b WHERE (:tower IS NULL OR b.Tower=:tower) AND (:track IS NULL OR b.Track=:track) ORDER BY b.ParentTicket,b.ChildTicket"
        rows2=db.execute(text(q2),_params(start_date,end_date,tower,track)).fetchall();children=pd.DataFrame([{"ChildTicket":r.ChildTicket,"ParentTicket":r.ParentTicket,"Tower":r.Tower,"Track":r.Track,"Priority":r.Priority,"State":r.State} for r in rows2])
        return parents,children
    finally: db.close()


def get_volume_stats(start_date=None,end_date=None,tower=None,track=None):
    db=SessionLocal()
    try:
        cols,joins,_tower,_track,scope=_ticket_context(db,"tk");date_col="OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        q=f"WITH d AS (SELECT CAST(tk.{date_col} AS date) TicketDate,COUNT(*) DailyTotal FROM qbr.Ticket tk {joins} WHERE tk.{date_col} IS NOT NULL AND {_date_filter('tk',date_col)} AND {scope} GROUP BY CAST(tk.{date_col} AS date)) SELECT MAX(DailyTotal) MaxCount,MIN(DailyTotal) MinCount,AVG(CAST(DailyTotal AS float)) AvgCount,(SELECT TOP 1 TicketDate FROM d ORDER BY DailyTotal DESC,TicketDate) MaxDate,(SELECT TOP 1 TicketDate FROM d ORDER BY DailyTotal ASC,TicketDate) MinDate FROM d"
        row=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchone()
        if not row or row.MaxCount is None:return None
        return {"max_count":_safe_int(row.MaxCount),"min_count":_safe_int(row.MinCount),"avg_count":round(float(row.AvgCount),1),"max_date":row.MaxDate,"min_date":row.MinDate}
    finally: db.close()


def get_tower_track_alerts(start_date=None,end_date=None,tower=None,track=None):
    db=SessionLocal()
    try:
        cols,joins,tower_expr,track_expr,_scope=_ticket_context(db,"tk");date_col="OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        if "Caller" not in cols:return pd.DataFrame(columns=["Tower","Track","TotalAlerts","Critical","High","Moderate"])
        pred=_monitoring_predicate("tk")
        q=f"SELECT b.Tower,b.Track,COUNT(*) TotalAlerts,SUM(CASE WHEN UPPER(ISNULL(b.Priority,'')) LIKE '%CRITICAL%' OR b.Priority='1' THEN 1 ELSE 0 END) Critical,SUM(CASE WHEN UPPER(ISNULL(b.Priority,'')) LIKE '%HIGH%' OR b.Priority='2' THEN 1 ELSE 0 END) High,SUM(CASE WHEN UPPER(ISNULL(b.Priority,'')) LIKE '%MODERATE%' OR UPPER(ISNULL(b.Priority,'')) LIKE '%MEDIUM%' OR b.Priority='3' THEN 1 ELSE 0 END) Moderate FROM (SELECT {tower_expr} Tower,{track_expr} Track,tk.Priority FROM qbr.Ticket tk {joins} WHERE {pred} AND {_date_filter('tk',date_col)}) b WHERE (:tower IS NULL OR b.Tower=:tower) AND (:track IS NULL OR b.Track=:track) GROUP BY b.Tower,b.Track ORDER BY TotalAlerts DESC,b.Tower,b.Track"
        rows=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchall()
        return pd.DataFrame([{"Tower":r.Tower,"Track":r.Track,"TotalAlerts":_safe_int(r.TotalAlerts),"Critical":_safe_int(r.Critical),"High":_safe_int(r.High),"Moderate":_safe_int(r.Moderate)} for r in rows])
    finally: db.close()
	
def _monitoring_predicate(alias: str = "tk") -> str:
    return (
        f"(UPPER(LTRIM(RTRIM(ISNULL({alias}.Caller,'')))) LIKE '%EMS%' "
        f"OR UPPER(LTRIM(RTRIM(ISNULL({alias}.Caller,'')))) LIKE '%CMSP%')"
    )
