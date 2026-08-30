"""QBR ServiceNow ticket loader.

Single-fact model:
  * qbr.Ticket stores every ticket.
  * Caller EMS/CMSP => IsMonitoringGenerated=1 (monitoring/alert-origin ticket).
  * qbr.Customer maps normalized CompanyAccount -> Tower -> Track.
  * Duplicate TicketNumber rows are written to _duplicate_records.xlsx and only
    one merged row is loaded.
  * Source files and generated reports are moved to app/dataset/processed/<batch>
    only after the DB transaction commits successfully.

There is deliberately NO qbr.Alert insert. Monitoring/alert analytics are
calculated directly from qbr.Ticket.
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from app.db import SessionLocal

ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "app" / "dataset"
EXT = {".xlsx", ".xls", ".csv", ".txt"}
GENERATED = {"_merged_input.xlsx", "_duplicate_records.xlsx"}


def norm(v):
    if v is None or pd.isna(v):
        return ""
    s = str(v).strip()
    return "" if s.lower() in {"", "nan", "none", "null", "nat"} else s


def key(v):
    s = norm(v)
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s.upper()


def is_monitoring_caller(value):
    """Return True when ServiceNow Caller identifies EMS/CMSP monitoring."""
    caller_key = key(value)
    return "EMS" in caller_key or "CMSP" in caller_key


def first(row, names):
    cols = {str(c).strip().lower(): c for c in row.index}
    for name in names:
        col = cols.get(name.lower())
        if col is not None:
            value = norm(row.get(col))
            if value:
                return value
    return None


def dt(row, names):
    value = first(row, names)
    if not value:
        return None
    try:
        return pd.to_datetime(value).to_pydatetime()
    except Exception:
        return None


def company(value):
    """Normalize account names used by the Customer mapping table."""
    s = norm(value)
    return "Home Depot" if "home" in s.lower() else s


def read_file(path):
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        df = pd.read_excel(path, dtype=object)
    elif suffix == ".csv":
        df = pd.read_csv(path, dtype=object)
    else:
        try:
            df = pd.read_csv(path, sep="\t", dtype=object)
        except Exception:
            df = pd.read_csv(path, dtype=object)
    df.columns = [str(c).replace("\ufeff", "").strip() for c in df.columns]
    return df


def discover(folder, single=None):
    if single:
        path = Path(single)
        if not path.exists():
            path = folder / path.name
        if not path.exists():
            raise FileNotFoundError(single)
        return [path]
    return sorted(
        [
            p
            for p in folder.iterdir()
            if p.is_file()
            and p.suffix.lower() in EXT
            and p.name not in GENERATED
            and not p.name.startswith("_")
        ],
        key=lambda p: p.name.lower(),
    )


def ticket_col(columns):
    aliases = [
        "TicketNumber", "Number", "Incident Number", "IncidentNumber",
        "Ticket Number", "Ticket_Number", "Incident_Number",
    ]
    lookup = {str(c).strip().lower(): c for c in columns}
    return next((lookup[a.lower()] for a in aliases if a.lower() in lookup), None)


def merge_inputs(files, folder):
    frames = []
    for path in files:
        df = read_file(path)
        if df.empty:
            continue
        tc = ticket_col(df.columns)
        if not tc:
            raise RuntimeError(f"{path.name}: TicketNumber/Number column not found")
        df["SourceFile"] = path.name
        df["_TicketKey"] = df[tc].map(key)
        frames.append(df)

    if not frames:
        return None, None, 0, 0

    all_df = pd.concat(frames, ignore_index=True, sort=False)
    valid = all_df["_TicketKey"].ne("")
    counts = all_df.loc[valid, "_TicketKey"].value_counts()
    duplicate_keys = set(counts[counts > 1].index)
    duplicates = all_df[all_df["_TicketKey"].isin(duplicate_keys)].copy()

    if not duplicates.empty:
        duplicates["DuplicateCount"] = duplicates.groupby("_TicketKey")["_TicketKey"].transform("size")
        duplicates["DuplicateSources"] = duplicates.groupby("_TicketKey")["SourceFile"].transform("nunique")
        duplicates["DuplicateType"] = duplicates["DuplicateSources"].map(
            lambda n: "Across files" if n > 1 else "Within file"
        )

    duplicate_path = folder / "_duplicate_records.xlsx"
    with pd.ExcelWriter(duplicate_path, engine="openpyxl") as writer:
        duplicates.to_excel(writer, sheet_name="Duplicates", index=False)
        summary = (
            duplicates.groupby("_TicketKey", as_index=False)
            .agg(
                Occurrences=("_TicketKey", "size"),
                SourceFiles=("SourceFile", lambda s: " | ".join(dict.fromkeys(s))),
            )
            if not duplicates.empty
            else pd.DataFrame(columns=["_TicketKey", "Occurrences", "SourceFiles"])
        )
        summary.to_excel(writer, sheet_name="Summary", index=False)

    rows = []
    for _, group in all_df[valid].groupby("_TicketKey", sort=False):
        if len(group) == 1:
            rows.append(group.iloc[0].drop(labels=["_TicketKey"]).to_dict())
            continue

        group = group.copy()
        group["_priority"] = group.SourceFile.map(
            lambda s: 30
            if any(x in str(s).lower() for x in ("closed", "resolved", "complete"))
            else 20
            if any(x in str(s).lower() for x in ("updated", "update", "current"))
            else 10
        )
        group = group.sort_values("_priority", ascending=False)
        out = {}
        for col in group.columns:
            if col in {"_TicketKey", "_priority"}:
                continue
            values = [v for v in group[col].tolist() if norm(v)]
            out[col] = values[0] if values else None
        out["SourceFile"] = " | ".join(dict.fromkeys(str(x) for x in group.SourceFile.tolist()))
        rows.append(out)

    merged = pd.DataFrame(rows)
    tc = ticket_col(merged.columns)
    if tc is None or merged[tc].map(key).duplicated().any():
        raise RuntimeError("Duplicate TicketNumber remains after merge")

    merged_path = folder / "_merged_input.xlsx"
    merged.to_excel(merged_path, index=False)
    print(
        f"Input rows: {len(all_df):,}; unique load rows: {len(merged):,}; "
        f"duplicate occurrences: {len(duplicates):,}"
    )
    return merged, duplicate_path, len(duplicates), len(merged)


def mappings(db):
    rows = db.execute(
        text(
            """
            SELECT c.CustomerID,c.CompanyAccountName,c.CustomerName,c.TowerID,c.TrackID,
                   tw.TowerName,tr.TrackName
            FROM qbr.Customer c
            LEFT JOIN qbr.Tower tw ON tw.TowerID=c.TowerID
            LEFT JOIN qbr.Track tr ON tr.TrackID=c.TrackID
            WHERE ISNULL(c.IsActive,1)=1
            """
        )
    ).mappings().all()
    customers = {key(r["CompanyAccountName"] or r["CustomerName"]): r for r in rows}

    tracks = {
        key(r["TrackName"]): r
        for r in db.execute(
            text(
                """
                SELECT tr.TrackID,tr.TowerID,tr.TrackName,tw.TowerName
                FROM qbr.Track tr
                JOIN qbr.Tower tw ON tw.TowerID=tr.TowerID
                WHERE ISNULL(tr.IsActive,1)=1
                """
            )
        ).mappings().all()
    }
    return customers, tracks


def resolve(row, customers, tracks):
    account = company(first(row, ["Company account", "CompanyAccount", "Company", "Customer"]))
    customer = customers.get(key(account)) if account else None
    if customer:
        return (
            account,
            customer["CustomerID"],
            customer["TowerID"],
            customer["TrackID"],
            customer["TowerName"],
            customer["TrackName"],
        )

    track_name = first(row, ["TrackName", "Track"])
    track = tracks.get(key(track_name)) if track_name else None
    if track:
        return account, None, track["TowerID"], track["TrackID"], track["TowerName"], track["TrackName"]

    return account, None, None, None, None, None


def load(merged, db, replace):
    customers, tracks = mappings(db)
    batch = db.execute(text("SELECT NEWID()")).scalar()
    seen = set()
    loaded = skipped = 0
    errors = []
    unmapped = []

    ticket_sql = text(
        """
        INSERT INTO qbr.Ticket(
            TicketNumber,ParentTicketNumber,TicketType,CustomerID,TowerID,TrackID,
            AssignmentGroup,CompanyAccount,ConfigurationItem,Service,Device,Caller,
            Priority,State,Impact,ShortDescription,OpenedAt,CreatedAt,UpdatedAt,ClosedAt,
            CandidateForVE,VETimeSavedMinutes,ResolutionCode,CauseCode,SourceFile,
            LoadBatchID,LoadedAt,IsMonitoringGenerated
        )
        VALUES(
            :tn,:parent,:type,:cid,:tower,:track,:ag,:company,:ci,:service,:device,:caller,
            :priority,:state,:impact,:short_desc,:opened,:created,:updated,:closed,
            :ve,:ve_minutes,:resolution,:cause,:source,:batch,SYSUTCDATETIME(),:monitoring
        )
        """
    )

    for i, row in merged.iterrows():
        try:
            ticket_number = first(
                row,
                ["Number", "TicketNumber", "Ticket_Number", "Incident Number", "IncidentNumber", "Ticket Number"],
            )
            ticket_key = key(ticket_number)
            if not ticket_key or ticket_key in seen:
                skipped += 1
                continue
            seen.add(ticket_key)

            account, customer_id, tower_id, track_id, tower_name, track_name = resolve(
                row, customers, tracks
            )
            if account and (tower_id is None or track_id is None):
                unmapped.append(
                    {
                        "TicketNumber": ticket_number,
                        "CompanyAccount": account,
                        "SourceFile": row.get("SourceFile", ""),
                        "Reason": "CompanyAccount has no qbr.Customer mapping",
                    }
                )

            parent = first(row, ["Parent Incident", "ParentIncident", "Parent_Incident", "ParentTicketNumber", "Parent"])
            caller = first(row, ["Caller", "caller"])
            monitoring = is_monitoring_caller(caller)
            opened = dt(row, ["Opened", "OpenedAt", "Opened_At"])
            created = dt(row, ["Created", "CreatedAt", "Created_Date"]) or opened
            updated = dt(row, ["Updated", "UpdatedAt", "Updated_Date"])
            closed = dt(row, ["Closed", "ClosedAt", "Closed_At", "Resolved", "ResolvedAt"])
            device = first(row, ["Device", "device", "Part", "part"])
            service = first(row, ["Service", "service"])
            assignment = first(row, ["Assignment group", "AssignmentGroup", "Assignment_Group"])
            short = first(row, ["Short description", "ShortDescription", "Short_Description", "Description"])
            short = short[:500] if short else None

            exists = db.execute(
                text("SELECT 1 FROM qbr.Ticket WHERE UPPER(LTRIM(RTRIM(TicketNumber)))=:tn_key"), {"tn_key": ticket_key}
            ).first()
            if exists and not replace:
                skipped += 1
                continue

            db.execute(
                ticket_sql,
                {
                    "tn": ticket_number,
                    "parent": parent,
                    "type": "Child" if parent else "Parent",
                    "cid": customer_id,
                    "tower": tower_id,
                    "track": track_id,
                    "ag": assignment,
                    "company": account,
                    "ci": first(row, ["Configuration item", "ConfigurationItem", "Configuration_Item", "CI"]),
                    "service": service,
                    "device": device,
                    "caller": caller,
                    "priority": first(row, ["Priority", "priority"]),
                    "state": first(row, ["State", "Status", "state", "status"]),
                    "impact": first(row, ["Impact", "impact"]),
                    "short_desc": short,
                    "opened": opened,
                    "created": created,
                    "updated": updated,
                    "closed": closed,
                    "ve": first(row, ["Candidate for VE", "CandidateForVE"]),
                    "ve_minutes": None,
                    "resolution": first(row, ["Resolution code", "ResolutionCode", "Resolution"]),
                    "cause": first(row, ["Cause code", "CauseCode", "Cause"]),
                    "source": str(row.get("SourceFile") or ""),
                    "batch": batch,
                    "monitoring": monitoring,
                },
            )
            loaded += 1
        except Exception as exc:
            errors.append(f"row {i + 1}: {exc}")

    if errors:
        db.rollback()
        return 0, 0, len(errors), skipped, unmapped

    duplicate_in_batch = db.execute(
        text(
            """
            SELECT TOP 1 TicketNumber
            FROM qbr.Ticket
            WHERE LoadBatchID=:b
            GROUP BY TicketNumber
            HAVING COUNT(*)>1
            """
        ),
        {"b": batch},
    ).first()
    if duplicate_in_batch:
        db.rollback()
        return 0, 0, 1, skipped, unmapped

    db.commit()
    return loaded, 0, 0, skipped, unmapped


def archive(paths, folder):
    destination = folder / "processed" / datetime.now().strftime("%Y%m%d_%H%M%S")
    destination.mkdir(parents=True, exist_ok=True)
    moved = []
    for path in paths:
        path = Path(path)
        if path.exists():
            shutil.move(str(path), str(destination / path.name))
            moved.append(path.name)
    return destination, moved


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--file")
    parser.add_argument("--replace-tickets", "--clear", dest="replace", action="store_true")
    parser.add_argument("--dataset-folder", default=str(DATASET))
    args = parser.parse_args()

    folder = Path(args.dataset_folder)
    folder.mkdir(parents=True, exist_ok=True)
    files = discover(folder, args.file)
    if not files:
        print(f"No source files found in {folder}")
        return

    merged, duplicate_path, duplicate_rows, merged_rows = merge_inputs(files, folder)
    if merged is None:
        return

    unmapped_path = folder / "_unmapped_records.xlsx"
    db = SessionLocal()
    try:
        if args.replace:
            db.execute(text("DELETE FROM qbr.Ticket"))

        loaded, _, errors, skipped, unmapped = load(merged, db, args.replace)
        if errors:
            print(f"LOAD FAILED; transaction rolled back. Errors: {errors}")
            return

        if unmapped:
            pd.DataFrame(unmapped).to_excel(unmapped_path, index=False)
        elif unmapped_path.exists():
            unmapped_path.unlink()

        destination, moved = archive(
            [*files, duplicate_path, folder / "_merged_input.xlsx", unmapped_path], folder
        )

        print("\nPOST-LOAD FILE CLEANUP")
        for name in moved:
            print(f"  {name} moved successfully")
        print(f"Moved location: {destination}")
        print(f"Tickets loaded: {loaded:,}")
        monitoring_rows = sum(1 for x in merged.to_dict("records") if is_monitoring_caller(first(pd.Series(x), ["Caller", "caller"])))
        print(f"Monitoring-generated tickets (Caller EMS/CMSP): {monitoring_rows:,}")
        print(f"Duplicate occurrences recorded: {duplicate_rows:,}")
        print(f"Unique merged rows: {merged_rows:,}")
        print(f"Existing/skipped tickets: {skipped:,}")
        print(f"Unmapped CompanyAccount rows: {len(unmapped):,}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
