"""CPDB-backed analytics for the QBR Executive Dashboard.

Ticket Tower/Track resolution deliberately prefers CompanyAccount -> qbr.ProjectTrack
because the ticket feed contains CompanyAccount while TowerID/TrackID can be blank.
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


def _assignment_track_case(ag: str) -> str:
    a = f"UPPER(COALESCE({ag},''))"
    return (
        "CASE "
        f"WHEN {a} LIKE '%FN-SFNOC%' OR {a} = 'SFNOC' THEN 'SFNOC' "
        f"WHEN {a} LIKE '%FN-THD%' OR {a} LIKE '%JLK%' OR {a} IN ('THD DATA','THD-DATA') THEN 'THD Data' "
        f"WHEN {a} LIKE '%HSBC-DATA%' OR {a} IN ('HSBC DATA','HSBC-DATA') THEN 'HSBC Data' "
        f"WHEN {a} IN ('BOA-EV','BOA-EV-L1','BOA-EV-L2','BOA EV') THEN 'BOA EV' "
        f"WHEN {a} IN ('HSBC-COL','HSBC-COL-L1','HSBC-COL-L2','HSBC COLLAB') THEN 'HSBC' "
        f"WHEN {a} IN ('PM','PM-L1','PROBLEM MANAGEMENT') THEN 'Problem Management' "
        f"WHEN {a} IN ('BOA-TP','BOA TP') THEN 'BOA TP' "
        f"WHEN {a} IN ('GTM-TP','GTM TP') THEN 'GTM TP' "
        f"WHEN {a} IN ('HD-VOICE','HD VOICE (BGL)') THEN 'HD Voice (Bgl)' "
        f"WHEN {a} = 'SCNOC' THEN 'SCNOC' "
        f"WHEN {a} LIKE '%SEC-CYB%' OR {a} = 'CYBERSECURITY' THEN 'Cybersecurity' "
        f"WHEN {a} = 'DC-ACI' THEN 'DC-ACI' "
        f"WHEN {a} = 'INFRA' THEN 'Infra' "
        f"WHEN {a} = 'SOC' THEN 'SOC' "
        f"WHEN {a} IN ('NC-RIL','NC-RIL-L1','NC-RIL-L2','RIL') THEN 'RIL' "
        "ELSE NULL END"
    )


def _projecttrack_company_case(db, company_account: str) -> str:
    """Map Ticket.CompanyAccount to the business ProjectTrack catalogue.

    qbr.ProjectTrack is the authoritative source for the account-to-project
    relationship. The dashboard presents the business track names, so THD is
    normalized to THD Data and Data Foundation is treated as THD Data.
    """
    if not _table_exists(db, "ProjectTrack"):
        return "NULL"
    return (
        "(SELECT TOP 1 "
        "CASE "
        "WHEN UPPER(LTRIM(RTRIM(ISNULL(pt.ProjectName,'')))) IN ('THD','THD DATA') "
        "  OR UPPER(LTRIM(RTRIM(ISNULL(pt.TrackName,'')))) IN ('DATA FOUNDATION','THD DATA','THD') THEN 'THD Data' "
        "ELSE NULLIF(LTRIM(RTRIM(pt.ProjectName)),'') END "
        "FROM qbr.ProjectTrack pt "
        "WHERE ISNULL(pt.IsActive,1)=1 "
        f"AND UPPER(LTRIM(RTRIM(ISNULL(pt.CompanyAccount,'')))) = UPPER(LTRIM(RTRIM(COALESCE({company_account},'')))) "
        "ORDER BY pt.ProjectTrackID)"
    )


def _company_account_fallback(company_account: str) -> str:
    """Explicit business-account fallback when ProjectTrack has no row."""
    a = f"UPPER(LTRIM(RTRIM(COALESCE({company_account},''))))"
    return (
        "CASE "
        f"WHEN {a} IN ('HOME DEPOT','THE HOME DEPOT','THD') THEN 'THD Data' "
        f"WHEN {a} IN ('SFNOC') THEN 'SFNOC' "
        f"WHEN {a} IN ('HSBC DATA') THEN 'HSBC Data' "
        f"WHEN {a} IN ('BANK OF AMERICA','BOA EV') THEN 'BOA EV' "
        f"WHEN {a} IN ('PROBLEM MANAGEMENT','MIXED') THEN 'Problem Management' "
        f"WHEN {a} IN ('RELIANCE','RIL') THEN 'RIL' "
        f"WHEN {a} IN ('CYBERSECURITY') THEN 'Cybersecurity' "
        f"WHEN {a} IN ('BOA TP') THEN 'BOA TP' "
        f"WHEN {a} IN ('GTM TP') THEN 'GTM TP' "
        f"WHEN {a} IN ('HD VOICE','HD VOICE (BGL)') THEN 'HD Voice (Bgl)' "
        f"WHEN {a} IN ('SCNOC') THEN 'SCNOC' "
        f"WHEN {a} IN ('DC-ACI') THEN 'DC-ACI' "
        f"WHEN {a} IN ('INFRA') THEN 'Infra' "
        f"WHEN {a} IN ('SOC') THEN 'SOC' "
        "ELSE NULL END"
    )


def _catalog_track_case(db, ag: str) -> str:
    if not _table_exists(db, "Track"):
        return "NULL"
    return (
        "(SELECT TOP 1 tr_ag.TrackName FROM qbr.Track tr_ag "
        "WHERE ISNULL(tr_ag.IsActive,1)=1 "
        f"AND (UPPER(LTRIM(RTRIM(tr_ag.TrackName))) = UPPER(COALESCE({ag},'')) "
        f"OR UPPER(COALESCE({ag},'')) LIKE '%' + UPPER(LTRIM(RTRIM(tr_ag.TrackName))) + '%' "
        f"OR UPPER(LTRIM(RTRIM(tr_ag.TrackName))) LIKE '%' + UPPER(COALESCE({ag},'')) + '%') "
        "ORDER BY LEN(tr_ag.TrackName) DESC)"
    )


def _ticket_context(db, alias: str = "tk"):
    cols = _columns(db, "Ticket")
    joins = ""
    has_tower = "TowerID" in cols and _table_exists(db, "Tower")
    has_track = "TrackID" in cols and _table_exists(db, "Track")
    has_tt = "TowerTrackID" in cols and _table_exists(db, "TowerTrack")
    if has_tower:
        joins += f" LEFT JOIN qbr.Tower t ON t.TowerID={alias}.TowerID"
    if has_track:
        joins += f" LEFT JOIN qbr.Track tr ON tr.TrackID={alias}.TrackID"
    if has_tt:
        joins += f" LEFT JOIN qbr.TowerTrack tt ON tt.TowerTrackID={alias}.TowerTrackID"

    ag = f"NULLIF(LTRIM(RTRIM({alias}.AssignmentGroup)),'')" if "AssignmentGroup" in cols else "NULL"
    ca = f"NULLIF(LTRIM(RTRIM({alias}.CompanyAccount)),'')" if "CompanyAccount" in cols else "NULL"
    company_track = _projecttrack_company_case(db, ca)
    company_fallback = _company_account_fallback(ca)
    mapped_track = _assignment_track_case(ag)
    catalog_track = _catalog_track_case(db, ag)

    track_parts = []
    # CompanyAccount is deliberately FIRST: the ticket feed has this field and
    # it is the reliable business relationship for the QBR volume chart.
    track_parts.extend([f"NULLIF({company_track},'Unknown')", f"NULLIF({company_fallback},'Unknown')"])
    if "TrackName" in cols:
        track_parts.append(f"NULLIF(NULLIF(LTRIM(RTRIM({alias}.TrackName)),''),'Unknown')")
    if has_track:
        track_parts.append("NULLIF(NULLIF(LTRIM(RTRIM(tr.TrackName)),''),'Unknown')")
    if has_tt:
        track_parts.append("NULLIF(NULLIF(LTRIM(RTRIM(tt.TrackName)),''),'Unknown')")
    track_parts.extend([f"NULLIF({mapped_track},'Unknown')", f"NULLIF({catalog_track},'Unknown')"])
    track_expr = "COALESCE(" + ",".join(track_parts) + ",'Unknown')"

    tower_parts = []
    if "ProjectName" in cols:
        tower_parts.append(f"NULLIF(NULLIF(LTRIM(RTRIM({alias}.ProjectName)),''),'Unknown')")
    if has_tower:
        tower_parts.append("NULLIF(NULLIF(LTRIM(RTRIM(t.TowerName)),''),'Unknown')")
    if has_tt:
        tower_parts.append("NULLIF(NULLIF(LTRIM(RTRIM(tt.TowerName)),''),'Unknown')")
    # Business rule: these three tracks belong to Foundation.
    tower_parts.append(f"CASE WHEN {track_expr} IN ('SFNOC','THD Data','HSBC Data') THEN 'Foundation' ELSE NULL END")
    track_tower_lookup = (
        "(SELECT TOP 1 t_ag.TowerName FROM qbr.Track tr_ag "
        "JOIN qbr.Tower t_ag ON t_ag.TowerID=tr_ag.TowerID "
        "WHERE ISNULL(tr_ag.IsActive,1)=1 AND ISNULL(t_ag.IsActive,1)=1 "
        f"AND (UPPER(LTRIM(RTRIM(tr_ag.TrackName)))=UPPER({track_expr}) "
        f"OR (UPPER({track_expr})='THD DATA' AND UPPER(LTRIM(RTRIM(tr_ag.TrackName))) IN ('THD DATA','DATA FOUNDATION','THD'))) "
        "ORDER BY tr_ag.TrackID)"
    ) if _table_exists(db, "Track") and _table_exists(db, "Tower") else "NULL"
    tower_parts.append(track_tower_lookup)
    tower_expr = "COALESCE(" + ",".join(tower_parts) + ",'Unknown')"
    scope = f"(:tower IS NULL OR {tower_expr}=:tower) AND (:track IS NULL OR {track_expr}=:track)"
    return cols, joins, tower_expr, track_expr, scope


def _alert_context(db, alias: str = "a"):
    cols = _columns(db, "Alert")
    joins = ""
    has_tower = "TowerID" in cols and _table_exists(db, "Tower")
    has_track = "TrackID" in cols and _table_exists(db, "Track")
    has_tt = "TowerTrackID" in cols and _table_exists(db, "TowerTrack")
    if has_tower:
        joins += f" LEFT JOIN qbr.Tower t ON t.TowerID={alias}.TowerID"
    if has_track:
        joins += f" LEFT JOIN qbr.Track tr ON tr.TrackID={alias}.TrackID"
    if has_tt:
        joins += f" LEFT JOIN qbr.TowerTrack tt ON tt.TowerTrackID={alias}.TowerTrackID"
    assignment = f"NULLIF(LTRIM(RTRIM({alias}.AssignmentGroup)),'')" if "AssignmentGroup" in cols else "NULL"
    mapped_track = _assignment_track_case(assignment)
    catalog_track = _catalog_track_case(db, assignment)
    track_parts = []
    if "TrackName" in cols:
        track_parts.append(f"NULLIF(NULLIF(LTRIM(RTRIM({alias}.TrackName)),''),'Unknown')")
    if has_track:
        track_parts.append("NULLIF(NULLIF(LTRIM(RTRIM(tr.TrackName)),''),'Unknown')")
    if has_tt:
        track_parts.append("NULLIF(NULLIF(LTRIM(RTRIM(tt.TrackName)),''),'Unknown')")
    track_parts.extend([f"NULLIF({mapped_track},'Unknown')", f"NULLIF({catalog_track},'Unknown')"])
    track_expr = "COALESCE(" + ",".join(track_parts) + ",'Unknown')"
    tower_parts = []
    if "ProjectName" in cols:
        tower_parts.append(f"NULLIF(NULLIF(LTRIM(RTRIM({alias}.ProjectName)),''),'Unknown')")
    if has_tower:
        tower_parts.append("NULLIF(NULLIF(LTRIM(RTRIM(t.TowerName)),''),'Unknown')")
    if has_tt:
        tower_parts.append("NULLIF(NULLIF(LTRIM(RTRIM(tt.TowerName)),''),'Unknown')")
    tower_parts.append(f"CASE WHEN {track_expr} IN ('SFNOC','THD Data','HSBC Data') THEN 'Foundation' ELSE NULL END")
    tower_parts.append(
        "(SELECT TOP 1 t_ag.TowerName FROM qbr.Track tr_ag "
        "JOIN qbr.Tower t_ag ON t_ag.TowerID=tr_ag.TowerID "
        "WHERE ISNULL(tr_ag.IsActive,1)=1 AND ISNULL(t_ag.IsActive,1)=1 "
        f"AND UPPER(LTRIM(RTRIM(tr_ag.TrackName)))=UPPER({track_expr}) ORDER BY tr_ag.TrackID)"
        if _table_exists(db, "Track") and _table_exists(db, "Tower") else "NULL"
    )
    tower_expr = "COALESCE(" + ",".join(tower_parts) + ",'Unknown')"
    scope = f"(:tower IS NULL OR {tower_expr}=:tower) AND (:track IS NULL OR {track_expr}=:track)"
    return cols, joins, tower_expr, track_expr, scope


def get_tower_track_hierarchy():
    db = SessionLocal()
    try:
        out = {}
        if _table_exists(db, "TowerTrack"):
            rows = db.execute(text("SELECT TowerTrackID,TowerName,TrackName FROM qbr.TowerTrack WHERE ISNULL(IsActive,1)=1 ORDER BY TowerName,TrackName")).fetchall()
            for r in rows:
                out.setdefault(str(r.TowerName), {})[str(r.TrackName)] = {"TowerTrackID": r.TowerTrackID, "TrackName": str(r.TrackName)}
        if _table_exists(db, "Tower") and _table_exists(db, "Track"):
            rows = db.execute(text("SELECT t.TowerID,tr.TrackID,t.TowerName,tr.TrackName FROM qbr.Tower t JOIN qbr.Track tr ON tr.TowerID=t.TowerID WHERE ISNULL(t.IsActive,1)=1 AND ISNULL(tr.IsActive,1)=1 ORDER BY t.TowerName,tr.TrackName")).fetchall()
            for r in rows:
                tower = str(r.TowerName); track = str(r.TrackName)
                display_track = "THD Data" if track.upper() in ("THD", "DATA FOUNDATION", "THD DATA") and tower.upper() == "FOUNDATION" else track
                out.setdefault(tower, {}).setdefault(display_track, {"TowerTrackID": r.TrackID, "TrackName": display_track})
        result = {tower: list(tracks.values()) for tower, tracks in out.items()}
        # Foundation must always present the three business tracks in this order.
        if "Foundation" in result:
            wanted = ["SFNOC", "THD Data", "HSBC Data"]
            found = {str(x["TrackName"]): x for x in result["Foundation"]}
            result["Foundation"] = [found[name] for name in wanted if name in found]
            if "THD Data" not in found and _table_exists(db, "ProjectTrack"):
                row = db.execute(text("SELECT TOP 1 ProjectTrackID FROM qbr.ProjectTrack WHERE ISNULL(IsActive,1)=1 AND UPPER(LTRIM(RTRIM(ProjectName)))='THD' ORDER BY ProjectTrackID")).first()
                result["Foundation"].insert(1, {"TowerTrackID": row[0] if row else 0, "TrackName": "THD Data"})
        return result
    finally:
        db.close()


def get_executive_kpis(start_date=None, end_date=None, tower=None, track=None):
    db = SessionLocal()
    try:
        cols, joins, _tower, _track, scope = _ticket_context(db, "tk")
        date_col = "OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        parent = "CASE WHEN UPPER(ISNULL(tk.TicketType,''))='PARENT' THEN 1 ELSE 0 END" if "TicketType" in cols else "0"
        child = "CASE WHEN UPPER(ISNULL(tk.TicketType,''))='CHILD' THEN 1 ELSE 0 END" if "TicketType" in cols else "0"
        closed = "CASE WHEN tk.ClosedAt IS NOT NULL THEN 1 ELSE 0 END" if "ClosedAt" in cols else "CASE WHEN LOWER(ISNULL(tk.State,''))='closed' THEN 1 ELSE 0 END"
        priority = "ISNULL(tk.Priority,'')" if "Priority" in cols else "''"
        q = f"SELECT COUNT(*) Total,SUM({parent}) Parents,SUM({child}) Children,SUM({closed}) Closed,SUM(CASE WHEN {priority} IN ('1 - Critical','Critical','1') THEN 1 ELSE 0 END) Critical,SUM(CASE WHEN {priority} IN ('2 - High','High','2') THEN 1 ELSE 0 END) High,SUM(CASE WHEN {priority} IN ('3 - Moderate','Moderate','3','Medium') THEN 1 ELSE 0 END) Moderate FROM qbr.Ticket tk {joins} WHERE {_date_filter('tk',date_col)} AND {scope}"
        r = db.execute(text(q), _params(start_date, end_date, tower, track)).fetchone()
        return {"total": _safe_int(r.Total), "parents": _safe_int(r.Parents), "children": _safe_int(r.Children), "closed": _safe_int(r.Closed), "critical": _safe_int(r.Critical), "high": _safe_int(r.High), "moderate": _safe_int(r.Moderate)}
    finally:
        db.close()


def get_alert_total(start_date=None, end_date=None, tower=None, track=None):
    db = SessionLocal()
    try:
        _cols, joins, _tower, _track, scope = _alert_context(db, "a")
        return _safe_int(db.execute(text(f"SELECT COUNT(*) FROM qbr.Alert a {joins} WHERE {_date_filter('a','AlertTime')} AND {scope}"), _params(start_date, end_date, tower, track)).scalar())
    finally:
        db.close()


def get_tower_track_volume(start_date=None, end_date=None, tower=None, track=None):
    db = SessionLocal()
    try:
        cols, joins, tower_expr, track_expr, _scope = _ticket_context(db, "tk")
        date_col = "OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        q = f"""
        SELECT b.Tower,b.Track,COUNT(*) AS Total,
               SUM(CASE WHEN UPPER(ISNULL(b.TicketType,''))='PARENT' THEN 1 ELSE 0 END) AS Parents,
               SUM(CASE WHEN UPPER(ISNULL(b.TicketType,''))='CHILD' THEN 1 ELSE 0 END) AS Children
        FROM (
            SELECT {tower_expr} AS Tower,{track_expr} AS Track,tk.TicketType
            FROM qbr.Ticket tk {joins}
            WHERE {_date_filter('tk',date_col)}
        ) b
        WHERE (:tower IS NULL OR b.Tower=:tower) AND (:track IS NULL OR b.Track=:track)
        GROUP BY b.Tower,b.Track ORDER BY Total DESC
        """
        rows = db.execute(text(q), _params(start_date, end_date, tower, track)).fetchall()
        return pd.DataFrame([{"Tower": r.Tower, "Track": r.Track, "Total": _safe_int(r.Total), "Parents": _safe_int(r.Parents), "Children": _safe_int(r.Children)} for r in rows])
    finally:
        db.close()


def _trend(start_date, end_date, tower, track, period):
    db = SessionLocal()
    try:
        cols, joins, _tower, _track, scope = _ticket_context(db, "tk")
        date_col = "OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        if period == "day":
            bucket = f"CAST(tk.{date_col} AS date)"; label = "Date"; group = bucket
        elif period == "week":
            bucket = f"DATEADD(week,DATEDIFF(week,0,tk.{date_col}),0)"; label = "Week"; group = bucket
        elif period == "month":
            bucket = f"DATEFROMPARTS(YEAR(tk.{date_col}),MONTH(tk.{date_col}),1)"; label = "Month"; group = f"YEAR(tk.{date_col}),MONTH(tk.{date_col})"
        else:
            bucket = f"DATEFROMPARTS(YEAR(tk.{date_col}),((DATEPART(quarter,tk.{date_col})-1)*3)+1,1)"; label = "Quarter"; group = f"YEAR(tk.{date_col}),DATEPART(quarter,tk.{date_col})"
        q = f"SELECT {bucket} Bucket,COUNT(*) Total,SUM(CASE WHEN UPPER(ISNULL(tk.TicketType,''))='PARENT' THEN 1 ELSE 0 END) Parents,SUM(CASE WHEN UPPER(ISNULL(tk.TicketType,''))='CHILD' THEN 1 ELSE 0 END) Children FROM qbr.Ticket tk {joins} WHERE tk.{date_col} IS NOT NULL AND {_date_filter('tk',date_col)} AND {scope} GROUP BY {group} ORDER BY Bucket"
        rows = db.execute(text(q), _params(start_date, end_date, tower, track)).fetchall()
        data=[]
        for r in rows:
            b=r.Bucket
            x=b.strftime("%d %b %Y") if period=="day" else b.strftime("%d %b") if period=="week" else b.strftime("%b %Y") if period=="month" else f"Q{((b.month-1)//3)+1} {b.year}"
            data.append({label:x,"Total":_safe_int(r.Total),"Parents":_safe_int(r.Parents),"Children":_safe_int(r.Children)})
        return pd.DataFrame(data)
    finally:
        db.close()


def get_daily_trend(*args): return _trend(*args,"day")
def get_weekly_trend(*args): return _trend(*args,"week")
def get_monthly_trend(*args): return _trend(*args,"month")
def get_quarterly_trend(*args): return _trend(*args,"quarter")


def get_alert_frequency(start_date=None, end_date=None, tower=None, track=None):
    db=SessionLocal()
    try:
        cols,joins,_tower,_track,scope=_alert_context(db,"a")
        device_expr="ISNULL(a.Device,'Unknown')" if "Device" in cols else ("ISNULL(a.Part,'Unknown')" if "Part" in cols else "'Unknown'")
        q=f"SELECT {device_expr} Device,ISNULL(a.AlertType,'Unknown') AlertType,ISNULL(a.Severity,'Unknown') Severity,COUNT(*) AlertCount FROM qbr.Alert a {joins} WHERE {_date_filter('a','AlertTime')} AND {scope} GROUP BY {device_expr},ISNULL(a.AlertType,'Unknown'),ISNULL(a.Severity,'Unknown') ORDER BY AlertCount DESC,Device"
        rows=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchall()
        return pd.DataFrame([{"Device":r.Device,"AlertType":r.AlertType,"Severity":r.Severity,"Count":_safe_int(r.AlertCount)} for r in rows])
    finally: db.close()


def get_parent_child_relation(start_date=None,end_date=None,tower=None,track=None):
    db=SessionLocal()
    try:
        cols,joins,tower_expr,track_expr,_scope=_ticket_context(db,"c")
        date_col="OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        if "ParentTicketNumber" not in cols or "TicketType" not in cols:return pd.DataFrame(),pd.DataFrame()
        ticket_id="CAST(c.TicketNumber AS nvarchar(100))" if "TicketNumber" in cols else ("CAST(c.TicketKey AS nvarchar(100))" if "TicketKey" in cols else "CAST(c.ID AS nvarchar(100))")
        q=f"""SELECT b.ParentTicket,b.Tower,b.Track,COUNT(*) ChildCount,MAX(b.Priority) Priority,MAX(b.State) State
        FROM (SELECT CAST(c.ParentTicketNumber AS nvarchar(255)) ParentTicket,{tower_expr} Tower,{track_expr} Track,c.Priority,c.State
              FROM qbr.Ticket c {joins} WHERE UPPER(ISNULL(c.TicketType,''))='CHILD' AND c.ParentTicketNumber IS NOT NULL AND {_date_filter('c',date_col)}) b
        WHERE (:tower IS NULL OR b.Tower=:tower) AND (:track IS NULL OR b.Track=:track)
        GROUP BY b.ParentTicket,b.Tower,b.Track ORDER BY ChildCount DESC"""
        rows=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchall()
        parents=pd.DataFrame([{"ParentTicket":r.ParentTicket,"Tower":r.Tower,"Track":r.Track,"ChildCount":_safe_int(r.ChildCount),"Priority":r.Priority,"State":r.State} for r in rows])
        q2=f"""SELECT b.ChildTicket,b.ParentTicket,b.Tower,b.Track,b.Priority,b.State
        FROM (SELECT {ticket_id} ChildTicket,CAST(c.ParentTicketNumber AS nvarchar(255)) ParentTicket,{tower_expr} Tower,{track_expr} Track,c.Priority,c.State
              FROM qbr.Ticket c {joins} WHERE UPPER(ISNULL(c.TicketType,''))='CHILD' AND c.ParentTicketNumber IS NOT NULL AND {_date_filter('c',date_col)}) b
        WHERE (:tower IS NULL OR b.Tower=:tower) AND (:track IS NULL OR b.Track=:track)
        ORDER BY b.ParentTicket,b.ChildTicket"""
        rows2=db.execute(text(q2),_params(start_date,end_date,tower,track)).fetchall()
        children=pd.DataFrame([{"ChildTicket":r.ChildTicket,"ParentTicket":r.ParentTicket,"Tower":r.Tower,"Track":r.Track,"Priority":r.Priority,"State":r.State} for r in rows2])
        return parents,children
    finally: db.close()


def get_volume_stats(start_date=None,end_date=None,tower=None,track=None):
    db=SessionLocal()
    try:
        cols,joins,_tower,_track,scope=_ticket_context(db,"tk")
        date_col="OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        q=f"WITH d AS (SELECT CAST(tk.{date_col} AS date) TicketDate,COUNT(*) DailyTotal FROM qbr.Ticket tk {joins} WHERE tk.{date_col} IS NOT NULL AND {_date_filter('tk',date_col)} AND {scope} GROUP BY CAST(tk.{date_col} AS date)) SELECT MAX(DailyTotal) MaxCount,MIN(DailyTotal) MinCount,AVG(CAST(DailyTotal AS float)) AvgCount,(SELECT TOP 1 TicketDate FROM d ORDER BY DailyTotal DESC,TicketDate) MaxDate,(SELECT TOP 1 TicketDate FROM d ORDER BY DailyTotal ASC,TicketDate) MinDate FROM d"
        r=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchone()
        if not r or r.MaxCount is None:return None
        return {"max_count":_safe_int(r.MaxCount),"min_count":_safe_int(r.MinCount),"avg_count":round(float(r.AvgCount),1),"max_date":r.MaxDate,"min_date":r.MinDate}
    finally: db.close()


def get_tower_track_alerts(start_date=None,end_date=None,tower=None,track=None):
    db=SessionLocal()
    try:
        _cols,joins,tower_expr,track_expr,_scope=_alert_context(db,"a")
        q=f"""SELECT b.Tower,b.Track,COUNT(*) TotalAlerts,
        SUM(CASE WHEN UPPER(ISNULL(b.Severity,'')) LIKE '%CRITICAL%' THEN 1 ELSE 0 END) Critical,
        SUM(CASE WHEN UPPER(ISNULL(b.Severity,'')) LIKE '%HIGH%' THEN 1 ELSE 0 END) High,
        SUM(CASE WHEN UPPER(ISNULL(b.Severity,'')) LIKE '%MODERATE%' OR UPPER(ISNULL(b.Severity,'')) LIKE '%MEDIUM%' THEN 1 ELSE 0 END) Moderate
        FROM (SELECT {tower_expr} Tower,{track_expr} Track,a.Severity FROM qbr.Alert a {joins} WHERE {_date_filter('a','AlertTime')}) b
        WHERE (:tower IS NULL OR b.Tower=:tower) AND (:track IS NULL OR b.Track=:track)
        GROUP BY b.Tower,b.Track ORDER BY TotalAlerts DESC,b.Tower,b.Track"""
        rows=db.execute(text(q),_params(start_date,end_date,tower,track)).fetchall()
        return pd.DataFrame([{"Tower":r.Tower,"Track":r.Track,"TotalAlerts":_safe_int(r.TotalAlerts),"Critical":_safe_int(r.Critical),"High":_safe_int(r.High),"Moderate":_safe_int(r.Moderate)} for r in rows])
    finally: db.close()
