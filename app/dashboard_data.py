"""QBR Executive Dashboard data/analytics layer.

Live SQL Server schema is the source of truth.  Analytics deliberately avoids
columns that are not present in the deployed CPDB schema (for example,
TicketNumber/ResolvedAt on qbr.Ticket).
"""
import pandas as pd
from sqlalchemy import text
from app.db import SessionLocal


def _params(start_date=None, end_date=None, tower_id=None, track_id=None):
    return {"start_date": start_date, "end_date": end_date,
            "tower_id": tower_id, "track_id": track_id}


def _ticket_filter(alias="tk"):
    return f"""(:start_date IS NULL OR {alias}.OpenedAt >= :start_date)
              AND (:end_date IS NULL OR {alias}.OpenedAt < DATEADD(day, 1, :end_date))
              AND (:tower_id IS NULL OR {alias}.TowerID = :tower_id)
              AND (:track_id IS NULL OR {alias}.TrackID = :track_id)"""


def _alert_filter(alias="a"):
    return f"""(:start_date IS NULL OR {alias}.AlertTime >= :start_date)
              AND (:end_date IS NULL OR {alias}.AlertTime < DATEADD(day, 1, :end_date))
              AND (:tower_id IS NULL OR {alias}.TowerID = :tower_id)
              AND (:track_id IS NULL OR {alias}.TrackID = :track_id)"""


def get_tower_track_hierarchy():
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT t.TowerID,t.TowerName,tr.TrackID,tr.TrackName
            FROM qbr.Tower t JOIN qbr.Track tr ON tr.TowerID=t.TowerID
            WHERE ISNULL(t.IsActive,1)=1 AND ISNULL(tr.IsActive,1)=1
            ORDER BY ISNULL(t.DisplayOrder,9999),t.TowerName,
                     ISNULL(tr.DisplayOrder,9999),tr.TrackName
        """)).fetchall()
        result = {}
        for r in rows:
            result.setdefault(r.TowerName, []).append({"TrackID":r.TrackID,"TrackName":r.TrackName})
        return result
    finally:
        db.close()


def get_executive_kpis(start_date=None,end_date=None,tower_id=None,track_id=None):
    db=SessionLocal()
    try:
        q=f"""
        SELECT COUNT(*) Total,
          SUM(CASE WHEN tk.TicketType='Parent' THEN 1 ELSE 0 END) Parents,
          SUM(CASE WHEN tk.TicketType='Child' THEN 1 ELSE 0 END) Children,
          SUM(CASE WHEN tk.State='Closed' THEN 1 ELSE 0 END) Closed,
          SUM(CASE WHEN tk.Priority IN ('1 - Critical','Critical','1') THEN 1 ELSE 0 END) Critical,
          SUM(CASE WHEN tk.Priority IN ('2 - High','High','2') THEN 1 ELSE 0 END) High
        FROM qbr.Ticket tk WHERE {_ticket_filter()}"""
        r=db.execute(text(q),_params(start_date,end_date,tower_id,track_id)).fetchone()
        return {"total":int(r.Total or 0),"parents":int(r.Parents or 0),
                "children":int(r.Children or 0),"closed":int(r.Closed or 0),
                "critical":int(r.Critical or 0),"high":int(r.High or 0)}
    finally: db.close()


def get_alert_total(start_date=None,end_date=None,tower_id=None,track_id=None):
    db=SessionLocal()
    try:
        q=f"SELECT COUNT(*) FROM qbr.Alert a WHERE {_alert_filter()}"
        return int(db.execute(text(q),_params(start_date,end_date,tower_id,track_id)).scalar() or 0)
    finally: db.close()


def get_tower_track_volume(start_date=None,end_date=None,tower_id=None,track_id=None):
    db=SessionLocal()
    try:
        q=f"""
        SELECT t.TowerName Tower,tr.TrackName Track,COUNT(tk.TicketKey) Total,
          SUM(CASE WHEN tk.TicketType='Parent' THEN 1 ELSE 0 END) Parents,
          SUM(CASE WHEN tk.TicketType='Child' THEN 1 ELSE 0 END) Children
        FROM qbr.Tower t JOIN qbr.Track tr ON tr.TowerID=t.TowerID
        LEFT JOIN qbr.Ticket tk ON tk.TowerID=t.TowerID AND tk.TrackID=tr.TrackID
          AND {_ticket_filter('tk')}
        WHERE ISNULL(t.IsActive,1)=1 AND ISNULL(tr.IsActive,1)=1
        GROUP BY t.TowerName,tr.TrackName ORDER BY Total DESC,tr.TrackName"""
        rows=db.execute(text(q),_params(start_date,end_date,tower_id,track_id)).fetchall()
        return pd.DataFrame([{"Tower":r.Tower,"Track":r.Track,"Total":int(r.Total or 0),
                              "Parents":int(r.Parents or 0),"Children":int(r.Children or 0)} for r in rows])
    finally: db.close()


def _trend(start_date,end_date,tower_id,track_id,period):
    db=SessionLocal()
    try:
        if period=='day': bucket='CAST(tk.OpenedAt AS date)'; label='Date'; group=bucket
        elif period=='week': bucket="DATEADD(week,DATEDIFF(week,0,tk.OpenedAt),0)"; label='Week'; group=bucket
        elif period=='month': bucket="DATEFROMPARTS(YEAR(tk.OpenedAt),MONTH(tk.OpenedAt),1)"; label='Month'; group='YEAR(tk.OpenedAt),MONTH(tk.OpenedAt)'
        else: bucket="DATEFROMPARTS(YEAR(tk.OpenedAt),((DATEPART(quarter,tk.OpenedAt)-1)*3)+1,1)"; label='Quarter'; group='YEAR(tk.OpenedAt),DATEPART(quarter,tk.OpenedAt)'
        q=f"""SELECT {bucket} Bucket,COUNT(*) Total,
          SUM(CASE WHEN tk.TicketType='Parent' THEN 1 ELSE 0 END) Parents,
          SUM(CASE WHEN tk.TicketType='Child' THEN 1 ELSE 0 END) Children
          FROM qbr.Ticket tk WHERE tk.OpenedAt IS NOT NULL AND {_ticket_filter('tk')}
          GROUP BY {group} ORDER BY Bucket"""
        rows=db.execute(text(q),_params(start_date,end_date,tower_id,track_id)).fetchall()
        data=[]
        for r in rows:
            b=r.Bucket
            x=(b.strftime('%d %b %Y') if period=='day' else
               b.strftime('%d %b') if period=='week' else
               b.strftime('%b %Y') if period=='month' else f"Q{((b.month-1)//3)+1} {b.year}")
            data.append({label:x,"Total":int(r.Total or 0),"Parents":int(r.Parents or 0),"Children":int(r.Children or 0)})
        return pd.DataFrame(data)
    finally: db.close()


def get_daily_trend(start_date=None,end_date=None,tower_id=None,track_id=None): return _trend(start_date,end_date,tower_id,track_id,'day')
def get_weekly_trend(start_date=None,end_date=None,tower_id=None,track_id=None): return _trend(start_date,end_date,tower_id,track_id,'week')
def get_monthly_trend(start_date=None,end_date=None,tower_id=None,track_id=None): return _trend(start_date,end_date,tower_id,track_id,'month')
def get_quarterly_trend(start_date=None,end_date=None,tower_id=None,track_id=None): return _trend(start_date,end_date,tower_id,track_id,'quarter')


def get_alert_frequency(start_date=None,end_date=None,tower_id=None,track_id=None):
    db=SessionLocal()
    try:
        q=f"""SELECT ISNULL(a.Part,'Unknown') Part,ISNULL(a.AlertType,'Unknown') AlertType,
          ISNULL(a.Severity,'Unknown') Severity,COUNT(*) AlertCount
          FROM qbr.Alert a WHERE {_alert_filter('a')}
          GROUP BY ISNULL(a.Part,'Unknown'),ISNULL(a.AlertType,'Unknown'),ISNULL(a.Severity,'Unknown')
          ORDER BY AlertCount DESC,Part"""
        rows=db.execute(text(q),_params(start_date,end_date,tower_id,track_id)).fetchall()
        return pd.DataFrame([{"Part":r.Part,"AlertType":r.AlertType,"Severity":r.Severity,"Count":int(r.AlertCount or 0)} for r in rows])
    finally: db.close()


def get_parent_child_relation(start_date=None,end_date=None,tower_id=None,track_id=None):
    db=SessionLocal()
    try:
        q=f"""SELECT CAST(c.ParentTicketNumber AS nvarchar(255)) ParentTicket,
          t.TowerName Tower,tr.TrackName Track,COUNT(*) ChildCount,
          MAX(c.Priority) Priority,MAX(c.State) State
          FROM qbr.Ticket c LEFT JOIN qbr.Tower t ON t.TowerID=c.TowerID
          LEFT JOIN qbr.Track tr ON tr.TrackID=c.TrackID
          WHERE c.TicketType='Child' AND c.ParentTicketNumber IS NOT NULL
          AND {_ticket_filter('c')}
          GROUP BY CAST(c.ParentTicketNumber AS nvarchar(255)),t.TowerName,tr.TrackName
          ORDER BY ChildCount DESC"""
        rows=db.execute(text(q),_params(start_date,end_date,tower_id,track_id)).fetchall()
        parent_df=pd.DataFrame([{"ParentTicket":r.ParentTicket,"Tower":r.Tower,"Track":r.Track,
                                 "ChildCount":int(r.ChildCount or 0),"Priority":r.Priority,"State":r.State} for r in rows])
        q2=f"""SELECT CAST(c.TicketKey AS nvarchar(100)) ChildTicket,
          CAST(c.ParentTicketNumber AS nvarchar(255)) ParentTicket,t.TowerName Tower,
          tr.TrackName Track,c.Priority,c.State
          FROM qbr.Ticket c LEFT JOIN qbr.Tower t ON t.TowerID=c.TowerID
          LEFT JOIN qbr.Track tr ON tr.TrackID=c.TrackID
          WHERE c.TicketType='Child' AND {_ticket_filter('c')}
          ORDER BY c.ParentTicketNumber,c.TicketKey"""
        rows2=db.execute(text(q2),_params(start_date,end_date,tower_id,track_id)).fetchall()
        child_df=pd.DataFrame([{"ChildTicket":r.ChildTicket,"ParentTicket":r.ParentTicket,"Tower":r.Tower,
                                "Track":r.Track,"Priority":r.Priority,"State":r.State} for r in rows2])
        return parent_df,child_df
    finally: db.close()


def get_volume_stats(start_date=None,end_date=None,tower_id=None,track_id=None):
    db=SessionLocal()
    try:
        q=f"""WITH d AS (
          SELECT CAST(tk.OpenedAt AS date) TicketDate,COUNT(*) DailyTotal
          FROM qbr.Ticket tk WHERE tk.OpenedAt IS NOT NULL AND {_ticket_filter('tk')}
          GROUP BY CAST(tk.OpenedAt AS date))
          SELECT MAX(DailyTotal) MaxCount,MIN(DailyTotal) MinCount,AVG(CAST(DailyTotal AS float)) AvgCount,
          (SELECT TOP 1 TicketDate FROM d ORDER BY DailyTotal DESC,TicketDate) MaxDate,
          (SELECT TOP 1 TicketDate FROM d ORDER BY DailyTotal ASC,TicketDate) MinDate FROM d"""
        r=db.execute(text(q),_params(start_date,end_date,tower_id,track_id)).fetchone()
        if not r or r.MaxCount is None:return None
        return {"max_count":int(r.MaxCount),"min_count":int(r.MinCount),"avg_count":round(float(r.AvgCount),1),"max_date":r.MaxDate,"min_date":r.MinDate}
    finally: db.close()


def get_tower_track_alerts(start_date=None,end_date=None,tower_id=None,track_id=None):
    db=SessionLocal()
    try:
        q=f"""SELECT t.TowerName Tower,tr.TrackName Track,COUNT(a.AlertKey) TotalAlerts,
          SUM(CASE WHEN a.Severity='Critical' THEN 1 ELSE 0 END) Critical,
          SUM(CASE WHEN a.Severity='High' THEN 1 ELSE 0 END) High,
          SUM(CASE WHEN a.Severity='Moderate' THEN 1 ELSE 0 END) Moderate
          FROM qbr.Tower t JOIN qbr.Track tr ON tr.TowerID=t.TowerID
          LEFT JOIN qbr.Alert a ON a.TowerID=t.TowerID AND a.TrackID=tr.TrackID
            AND {_alert_filter('a')}
          WHERE ISNULL(t.IsActive,1)=1 AND ISNULL(tr.IsActive,1)=1
          GROUP BY t.TowerName,tr.TrackName HAVING COUNT(a.AlertKey)>0
          ORDER BY TotalAlerts DESC,t.TowerName,tr.TrackName"""
        rows=db.execute(text(q),_params(start_date,end_date,tower_id,track_id)).fetchall()
        return pd.DataFrame([{"Tower":r.Tower,"Track":r.Track,"TotalAlerts":int(r.TotalAlerts or 0),
                              "Critical":int(r.Critical or 0),"High":int(r.High or 0),"Moderate":int(r.Moderate or 0)} for r in rows])
    finally: db.close()
