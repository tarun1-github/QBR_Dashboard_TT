import pandas as pd
from sqlalchemy import text

def load_ticket_df(db):
    return pd.read_sql(text("""
        SELECT TicketNumber, ParentTicketNumber, TicketType, ProjectName, TrackName,
               Priority, State, OpenedAt, ClosedAt
        FROM qbr.Ticket
    """), db.bind)

def load_alert_df(db):
    return pd.read_sql(text("""
        SELECT AlertID, ProjectName, TrackName, Part, AlertType, AlertTime
        FROM qbr.Alert
    """), db.bind)

def overview(db):
    tickets = load_ticket_df(db)
    alerts = load_alert_df(db)
    total = len(tickets)
    parents = int((tickets["TicketType"].astype(str).str.lower() == "parent").sum()) if total else 0
    children = int((tickets["TicketType"].astype(str).str.lower() == "child").sum()) if total else 0
    alert_count = len(alerts)
    return {
        "total_tickets": total,
        "parent_tickets": parents,
        "child_tickets": children,
        "alerts": alert_count,
        "alerts_per_ticket": round(alert_count / total, 2) if total else 0,
    }

def monthly_trend(db):
    tickets = load_ticket_df(db)
    alerts = load_alert_df(db)
    if tickets.empty:
        return pd.DataFrame(columns=["month","tickets","parents","children","alerts"])
    tickets["OpenedAt"] = pd.to_datetime(tickets["OpenedAt"])
    alerts["AlertTime"] = pd.to_datetime(alerts["AlertTime"])
    t = tickets.assign(month=tickets["OpenedAt"].dt.to_period("M").astype(str))
    a = alerts.assign(month=alerts["AlertTime"].dt.to_period("M").astype(str))
    base = t.groupby("month").size().rename("tickets").to_frame()
    base["parents"] = t[t.TicketType.astype(str).str.lower()=="parent"].groupby("month").size()
    base["children"] = t[t.TicketType.astype(str).str.lower()=="child"].groupby("month").size()
    base["alerts"] = a.groupby("month").size()
    return base.fillna(0).reset_index()

def project_summary(db):
    tickets = load_ticket_df(db)
    alerts = load_alert_df(db)
    if tickets.empty:
        return pd.DataFrame()
    x = tickets.groupby(["ProjectName","TrackName"]).agg(
        tickets=("TicketNumber","count"),
        parents=("TicketType", lambda s: (s.astype(str).str.lower()=="parent").sum()),
        children=("TicketType", lambda s: (s.astype(str).str.lower()=="child").sum())
    ).reset_index()
    a = alerts.groupby("ProjectName").size().rename("alerts")
    return x.merge(a, on="ProjectName", how="left").fillna({"alerts":0})
