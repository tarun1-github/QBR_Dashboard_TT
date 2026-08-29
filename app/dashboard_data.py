"""CPDB-backed analytics for the QBR Executive Dashboard.

The live CPDB has more than one schema revision.  Queries therefore inspect
available columns and, where possible, resolve Ticket Tower/Track through the
canonical qbr.TowerTrack mapping instead of relying on nullable display fields.
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import text
from app.db import SessionLocal


def _columns(db, table: str) -> set[str]:
    rows = db.execute(text("""
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA='qbr' AND TABLE_NAME=:table
    """), {"table": table}).fetchall()
    return {str(r[0]) for r in rows}


def _table_exists(db, table: str) -> bool:
    return bool(db.execute(text("""
        SELECT 1
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA='qbr' AND TABLE_NAME=:table
    """), {"table": table}).first())


def _safe_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _params(start_date=None, end_date=None, tower=None, track=None):
    return {"start_date": start_date, "end_date": end_date, "tower": tower, "track": track}


def _date_filter(alias: str, date_col: str) -> str:
    return (
        f"(:start_date IS NULL OR {alias}.{date_col} >= :start_date) "
        f"AND (:end_date IS NULL OR {alias}.{date_col} < DATEADD(day,1,:end_date))"
    )


def _ticket_context(db, alias: str = "tk"):
    """Return FROM/JOIN/filter fragments for Ticket queries.

    Prefer canonical TowerTrack joins when Ticket has TowerID + TrackID.  This
    prevents the dashboard from producing an artificial 'Unknown' bucket when
    ProjectName/TrackName are null in imported CPDB rows.
    """
    cols = _columns(db, "Ticket")
    joins = ""
    tower_expr = f"ISNULL({alias}.ProjectName,'Unknown')"
    track_expr = f"ISNULL({alias}.TrackName,'Unknown')"
    scope = []

    if _table_exists(db, "TowerTrack") and {"TowerID", "TrackID"}.issubset(cols):
        joins = f" LEFT JOIN qbr.TowerTrack tt ON tt.TowerTrackID = (SELECT TOP 1 tt2.TowerTrackID FROM qbr.TowerTrack tt2 WHERE tt2.TowerName IS NOT NULL AND tt2.TowerTrackID IS NOT NULL AND tt2.TowerTrackID = (SELECT TOP 1 x.TowerTrackID FROM qbr.TowerTrack x WHERE x.TowerTrackID IN (SELECT TOP 1 x2.TowerTrackID FROM qbr.TowerTrack x2 WHERE x2.TowerTrackID IS NOT NULL) ORDER BY x.TowerTrackID))"
        # The expression above is intentionally replaced below with the
        # simpler canonical ID join when the physical Ticket schema supports it.
        joins = f" LEFT JOIN qbr.TowerTrack tt ON tt.TowerTrackID = {alias}.TrackID"
        # Some CPDB revisions store TrackID as the TowerTrackID; if not, the
        # fallback display columns are used by the COALESCE expressions.
        tower_expr = f"ISNULL(tt.TowerName, ISNULL({alias}.ProjectName,'Unknown'))"
        track_expr = f"ISNULL(tt.TrackName, ISNULL({alias}.TrackName,'Unknown'))"
        scope.extend(["(:tower IS NULL OR tt.TowerName=:tower)", "(:track IS NULL OR tt.TrackName=:track)"])
    else:
        if "ProjectName" in cols:
            scope.append(f"(:tower IS NULL OR {alias}.ProjectName=:tower)")
        if "TowerName" in cols:
            scope.append(f"(:tower IS NULL OR {alias}.TowerName=:tower)")
        if "TrackName" in cols:
            scope.append(f"(:track IS NULL OR {alias}.TrackName=:track)")

    return cols, joins, tower_expr, track_expr, (" AND ".join(scope) if scope else "1=1")


def _alert_scope(db, alias: str = "a"):
    cols = _columns(db, "Alert")
    parts = []
    if "ProjectName" in cols:
        parts.append(f"(:tower IS NULL OR {alias}.ProjectName=:tower)")
    elif "TowerName" in cols:
        parts.append(f"(:tower IS NULL OR {alias}.TowerName=:tower)")
    if "TrackName" in cols:
        parts.append(f"(:track IS NULL OR {alias}.TrackName=:track)")
    return cols, (" AND ".join(parts) if parts else "1=1")


def get_tower_track_hierarchy():
    db = SessionLocal()
    try:
        if _table_exists(db, "TowerTrack"):
            rows = db.execute(text("""
                SELECT TowerTrackID,TowerName,TrackName
                FROM qbr.TowerTrack
                WHERE ISNULL(IsActive,1)=1
                ORDER BY TowerName,TrackName
            """)).fetchall()
            out = {}
            for row in rows:
                out.setdefault(row.TowerName, []).append({
                    "TowerTrackID": row.TowerTrackID,
                    "TrackName": row.TrackName,
                })
            return out
        rows = db.execute(text("""
            SELECT t.TowerID,tr.TrackID,t.TowerName,tr.TrackName
            FROM qbr.Tower t
            JOIN qbr.Track tr ON tr.TowerID=t.TowerID
            WHERE ISNULL(t.IsActive,1)=1 AND ISNULL(tr.IsActive,1)=1
            ORDER BY t.TowerName,tr.TrackName
        """)).fetchall()
        out = {}
        for row in rows:
            out.setdefault(row.TowerName, []).append({
                "TowerTrackID": row.TrackID,
                "TrackName": row.TrackName,
            })
        return out
    finally:
        db.close()


def get_executive_kpis(start_date=None, end_date=None, tower=None, track=None):
    db = SessionLocal()
    try:
        cols, joins, _tower, _track, scope = _ticket_context(db, "tk")
        date_col = "OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        parent = "CASE WHEN tk.TicketType='Parent' THEN 1 ELSE 0 END" if "TicketType" in cols else "0"
        child = "CASE WHEN tk.TicketType='Child' THEN 1 ELSE 0 END" if "TicketType" in cols else "0"
        if "ClosedAt" in cols:
            closed = "CASE WHEN tk.ClosedAt IS NOT NULL THEN 1 ELSE 0 END"
        else:
            closed = "CASE WHEN LOWER(ISNULL(tk.State,''))='closed' THEN 1 ELSE 0 END"
        priority = "ISNULL(tk.Priority,'')" if "Priority" in cols else "''"
        q = f"""
            SELECT COUNT(*) Total,
                   SUM({parent}) Parents,
                   SUM({child}) Children,
                   SUM({closed}) Closed,
                   SUM(CASE WHEN {priority} IN ('1 - Critical','Critical','1') THEN 1 ELSE 0 END) Critical,
                   SUM(CASE WHEN {priority} IN ('2 - High','High','2') THEN 1 ELSE 0 END) High,
                   SUM(CASE WHEN {priority} IN ('3 - Moderate','Moderate','3','Medium') THEN 1 ELSE 0 END) Moderate
            FROM qbr.Ticket tk
            {joins}
            WHERE {_date_filter('tk', date_col)} AND {scope}
        """
        row = db.execute(text(q), _params(start_date, end_date, tower, track)).fetchone()
        return {
            "total": _safe_int(row.Total), "parents": _safe_int(row.Parents),
            "children": _safe_int(row.Children), "closed": _safe_int(row.Closed),
            "critical": _safe_int(row.Critical), "high": _safe_int(row.High),
            "moderate": _safe_int(row.Moderate),
        }
    finally:
        db.close()


def get_alert_total(start_date=None, end_date=None, tower=None, track=None):
    db = SessionLocal()
    try:
        cols, scope = _alert_scope(db, "a")
        q = f"SELECT COUNT(*) FROM qbr.Alert a WHERE {_date_filter('a','AlertTime')} AND {scope}"
        return _safe_int(db.execute(text(q), _params(start_date, end_date, tower, track)).scalar())
    finally:
        db.close()


def get_tower_track_volume(start_date=None, end_date=None, tower=None, track=None):
    db = SessionLocal()
    try:
        cols, joins, tower_expr, track_expr, scope = _ticket_context(db, "tk")
        date_col = "OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        q = f"""
            SELECT {tower_expr} Tower,
                   {track_expr} Track,
                   COUNT(*) Total,
                   SUM(CASE WHEN tk.TicketType='Parent' THEN 1 ELSE 0 END) Parents,
                   SUM(CASE WHEN tk.TicketType='Child' THEN 1 ELSE 0 END) Children
            FROM qbr.Ticket tk
            {joins}
            WHERE {_date_filter('tk',date_col)} AND {scope}
            GROUP BY {tower_expr},{track_expr}
            ORDER BY Total DESC
        """
        rows = db.execute(text(q), _params(start_date, end_date, tower, track)).fetchall()
        return pd.DataFrame([{
            "Tower": r.Tower, "Track": r.Track, "Total": _safe_int(r.Total),
            "Parents": _safe_int(r.Parents), "Children": _safe_int(r.Children)
        } for r in rows])
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
        q = f"""
            SELECT {bucket} Bucket,
                   COUNT(*) Total,
                   SUM(CASE WHEN tk.TicketType='Parent' THEN 1 ELSE 0 END) Parents,
                   SUM(CASE WHEN tk.TicketType='Child' THEN 1 ELSE 0 END) Children
            FROM qbr.Ticket tk {joins}
            WHERE tk.{date_col} IS NOT NULL AND {_date_filter('tk',date_col)} AND {scope}
            GROUP BY {group} ORDER BY Bucket
        """
        rows = db.execute(text(q), _params(start_date, end_date, tower, track)).fetchall()
        data = []
        for row in rows:
            b = row.Bucket
            if period == "day": x = b.strftime("%d %b %Y")
            elif period == "week": x = b.strftime("%d %b")
            elif period == "month": x = b.strftime("%b %Y")
            else: x = f"Q{((b.month-1)//3)+1} {b.year}"
            data.append({label: x, "Total": _safe_int(row.Total), "Parents": _safe_int(row.Parents), "Children": _safe_int(row.Children)})
        return pd.DataFrame(data)
    finally:
        db.close()


def get_daily_trend(*args): return _trend(*args, "day")
def get_weekly_trend(*args): return _trend(*args, "week")
def get_monthly_trend(*args): return _trend(*args, "month")
def get_quarterly_trend(*args): return _trend(*args, "quarter")


def get_alert_frequency(start_date=None, end_date=None, tower=None, track=None):
    db = SessionLocal()
    try:
        cols, scope = _alert_scope(db, "a")
        q = f"""
            SELECT ISNULL(a.Part,'Unknown') Part,
                   ISNULL(a.AlertType,'Unknown') AlertType,
                   ISNULL(a.Severity,'Unknown') Severity,
                   COUNT(*) AlertCount
            FROM qbr.Alert a
            WHERE {_date_filter('a','AlertTime')} AND {scope}
            GROUP BY ISNULL(a.Part,'Unknown'),ISNULL(a.AlertType,'Unknown'),ISNULL(a.Severity,'Unknown')
            ORDER BY AlertCount DESC,Part
        """
        rows = db.execute(text(q), _params(start_date, end_date, tower, track)).fetchall()
        return pd.DataFrame([{"Part":r.Part,"AlertType":r.AlertType,"Severity":r.Severity,"Count":_safe_int(r.AlertCount)} for r in rows])
    finally:
        db.close()


def get_parent_child_relation(start_date=None, end_date=None, tower=None, track=None):
    db = SessionLocal()
    try:
        cols, joins, tower_expr, track_expr, scope = _ticket_context(db, "c")
        date_col = "OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        if "ParentTicketNumber" not in cols or "TicketType" not in cols:
            return pd.DataFrame(), pd.DataFrame()
        ticket_id = "CAST(c.TicketKey AS nvarchar(100))" if "TicketKey" in cols else "CAST(c.ID AS nvarchar(100))"
        q = f"""
            SELECT CAST(c.ParentTicketNumber AS nvarchar(255)) ParentTicket,
                   {tower_expr} Tower,
                   {track_expr} Track,
                   COUNT(*) ChildCount,
                   MAX(c.Priority) Priority,
                   MAX(c.State) State
            FROM qbr.Ticket c {joins}
            WHERE c.TicketType='Child' AND c.ParentTicketNumber IS NOT NULL
              AND {_date_filter('c',date_col)} AND {scope}
            GROUP BY CAST(c.ParentTicketNumber AS nvarchar(255)),{tower_expr},{track_expr}
            ORDER BY ChildCount DESC
        """
        rows = db.execute(text(q), _params(start_date, end_date, tower, track)).fetchall()
        parents = pd.DataFrame([{"ParentTicket":r.ParentTicket,"Tower":r.Tower,"Track":r.Track,"ChildCount":_safe_int(r.ChildCount),"Priority":r.Priority,"State":r.State} for r in rows])
        q2 = f"""
            SELECT {ticket_id} ChildTicket,
                   CAST(c.ParentTicketNumber AS nvarchar(255)) ParentTicket,
                   {tower_expr} Tower,
                   {track_expr} Track,
                   c.Priority,c.State
            FROM qbr.Ticket c {joins}
            WHERE c.TicketType='Child' AND c.ParentTicketNumber IS NOT NULL
              AND {_date_filter('c',date_col)} AND {scope}
            ORDER BY c.ParentTicketNumber,{ticket_id}
        """
        rows2 = db.execute(text(q2), _params(start_date, end_date, tower, track)).fetchall()
        children = pd.DataFrame([{"ChildTicket":r.ChildTicket,"ParentTicket":r.ParentTicket,"Tower":r.Tower,"Track":r.Track,"Priority":r.Priority,"State":r.State} for r in rows2])
        return parents, children
    finally:
        db.close()


def get_volume_stats(start_date=None, end_date=None, tower=None, track=None):
    db = SessionLocal()
    try:
        cols, joins, _tower, _track, scope = _ticket_context(db, "tk")
        date_col = "OpenedAt" if "OpenedAt" in cols else "CreatedAt"
        q = f"""
            WITH d AS (
                SELECT CAST(tk.{date_col} AS date) TicketDate, COUNT(*) DailyTotal
                FROM qbr.Ticket tk {joins}
                WHERE tk.{date_col} IS NOT NULL AND {_date_filter('tk',date_col)} AND {scope}
                GROUP BY CAST(tk.{date_col} AS date)
            )
            SELECT MAX(DailyTotal) MaxCount,MIN(DailyTotal) MinCount,
                   AVG(CAST(DailyTotal AS float)) AvgCount,
                   (SELECT TOP 1 TicketDate FROM d ORDER BY DailyTotal DESC,TicketDate) MaxDate,
                   (SELECT TOP 1 TicketDate FROM d ORDER BY DailyTotal ASC,TicketDate) MinDate
            FROM d
        """
        row = db.execute(text(q), _params(start_date, end_date, tower, track)).fetchone()
        if not row or row.MaxCount is None:
            return None
        return {"max_count":_safe_int(row.MaxCount),"min_count":_safe_int(row.MinCount),"avg_count":round(float(row.AvgCount),1),"max_date":row.MaxDate,"min_date":row.MinDate}
    finally:
        db.close()


def get_tower_track_alerts(start_date=None, end_date=None, tower=None, track=None):
    db = SessionLocal()
    try:
        cols, scope = _alert_scope(db, "a")
        tower_expr = "ISNULL(a.ProjectName,'Unknown')" if "ProjectName" in cols else "ISNULL(a.TowerName,'Unknown')"
        track_expr = "ISNULL(a.TrackName,'Unknown')" if "TrackName" in cols else "'Unknown'"
        q = f"""
            SELECT {tower_expr} Tower,{track_expr} Track,
                   COUNT(*) TotalAlerts,
                   SUM(CASE WHEN a.Severity='Critical' THEN 1 ELSE 0 END) Critical,
                   SUM(CASE WHEN a.Severity='High' THEN 1 ELSE 0 END) High,
                   SUM(CASE WHEN a.Severity='Moderate' THEN 1 ELSE 0 END) Moderate
            FROM qbr.Alert a
            WHERE {_date_filter('a','AlertTime')} AND {scope}
            GROUP BY {tower_expr},{track_expr}
            ORDER BY TotalAlerts DESC,Tower,Track
        """
        rows = db.execute(text(q), _params(start_date, end_date, tower, track)).fetchall()
        return pd.DataFrame([{"Tower":r.Tower,"Track":r.Track,"TotalAlerts":_safe_int(r.TotalAlerts),"Critical":_safe_int(r.Critical),"High":_safe_int(r.High),"Moderate":_safe_int(r.Moderate)} for r in rows])
    finally:
        db.close()
