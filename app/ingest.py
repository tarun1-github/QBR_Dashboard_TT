from pathlib import Path
import pandas as pd
from sqlalchemy import delete
from .db import SessionLocal
from .models import Project, Ticket, Alert, TicketAlert
from .init_db import init_db

INPUT = Path("data/input")

def pick_file(names):
    for name in names:
        p = INPUT / name
        if p.exists():
            return p
    return None

def normalize_columns(df):
    df.columns = [str(c).strip().lower().replace(" ", "_").replace("-", "_") for c in df.columns]
    return df

def ingest_servicenow(path):
    df = normalize_columns(pd.read_excel(path))
    # Expected target names. Real mapping will be adjusted after actual extract is supplied.
    rename = {
        "number":"ticket_id",
        "parent":"parent_ticket",
        "parent_ticket_number":"parent_ticket",
        "type":"ticket_type",
        "project_name":"project",
        "track_name":"track",
        "created":"created_date",
        "opened_at":"created_date",
        "closed":"closed_date",
    }
    df = df.rename(columns=rename)
    required = ["ticket_id","project","track","created_date"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"ServiceNow file missing columns: {missing}")
    if "parent_ticket" not in df: df["parent_ticket"] = df["ticket_id"]
    if "ticket_type" not in df:
        df["ticket_type"] = df.apply(lambda r: "Child" if r["parent_ticket"] != r["ticket_id"] else "Parent", axis=1)
    for c in ["service","part","priority","status"]:
        if c not in df: df[c] = ""
    if "closed_date" not in df: df["closed_date"] = pd.NaT
    df["created_date"] = pd.to_datetime(df["created_date"], errors="coerce")
    df["closed_date"] = pd.to_datetime(df["closed_date"], errors="coerce")
    df = df.dropna(subset=["ticket_id","created_date"]).drop_duplicates("ticket_id")
    return df

def ingest_nzg2(path):
    df = normalize_columns(pd.read_excel(path))
    rename = {
        "id":"alert_id", "timestamp":"alert_time", "time":"alert_time",
        "project_name":"project", "track_name":"track",
        "event":"alert_type", "severity_level":"severity"
    }
    df = df.rename(columns=rename)
    required = ["alert_id","alert_time","project","track"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"NZG2 file missing columns: {missing}")
    for c in ["service","part","alert_type","severity","monitoring_tool"]:
        if c not in df: df[c] = "NZG2" if c=="monitoring_tool" else ""
    df["alert_time"] = pd.to_datetime(df["alert_time"], errors="coerce")
    return df.dropna(subset=["alert_id","alert_time"]).drop_duplicates("alert_id")

def run():
    init_db()
    sn = pick_file(["ServiceNow.xlsx","servicenow.xlsx","ServiceNow.xls"])
    nz = pick_file(["NZG2.xlsx","nzg2.xlsx","NZG2.xls"])
    if not sn or not nz:
        print("Place ServiceNow.xlsx and NZG2.xlsx in data/input/ before ingestion.")
        return
    tickets = ingest_servicenow(sn)
    alerts = ingest_nzg2(nz)
    db = SessionLocal()
    try:
        db.execute(delete(TicketAlert)); db.execute(delete(Alert)); db.execute(delete(Ticket)); db.commit()
        for _,r in tickets.iterrows():
            db.add(Ticket(
                ticket_id=str(r.ticket_id), parent_ticket=str(r.parent_ticket),
                ticket_type=str(r.ticket_type), project=str(r.project), track=str(r.track),
                service=str(r.service), part=str(r.part), priority=str(r.priority),
                status=str(r.status), created_date=r.created_date.to_pydatetime(),
                closed_date=r.closed_date.to_pydatetime() if pd.notna(r.closed_date) else None
            ))
        for _,r in alerts.iterrows():
            db.add(Alert(
                alert_id=str(r.alert_id), alert_time=r.alert_time.to_pydatetime(),
                project=str(r.project), track=str(r.track), service=str(r.service),
                part=str(r.part), alert_type=str(r.alert_type), severity=str(r.severity),
                monitoring_tool=str(r.monitoring_tool)
            ))
        db.commit()
        print(f"Ingested {len(tickets)} tickets and {len(alerts)} alerts.")
    finally:
        db.close()

if __name__ == "__main__":
    run()
