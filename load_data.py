"""
QBR Dashboard - Data Loader
============================
Loads .xlsx/.xls/.csv/.txt files from app/dataset.

SAFE LOAD FLOW
--------------
1. Discover all source files (generated files beginning with '_' are ignored).
2. Read and normalize the ticket-number key.
3. Detect duplicate ticket records within/across source files.
4. Write every duplicate occurrence to _duplicate_records.xlsx.
5. Merge duplicate occurrences into ONE load-ready record per TicketNumber.
6. Optionally replace the existing qbr.Ticket data (--replace-tickets).
7. Load only the deduplicated/merged records in ONE database transaction.
8. If any row fails, ROLLBACK the whole batch; source files remain for retry.
9. Only after a successful zero-error commit, move source/audit files to:
      app/dataset/processed/<timestamp>/

Duplicate records are NEVER inserted as separate Ticket rows.
"""

import sys
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import text

ROOT = Path(__file__).resolve().parent
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))

from app.db import SessionLocal

SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".txt"}
GENERATED_PREFIX = "_"
MERGED_OUTPUT = "_merged_input.xlsx"
DUPLICATE_OUTPUT = "_duplicate_records.xlsx"
PROCESSED_FOLDER = "processed"


# Explicit business fallback confirmed for the current ServiceNow ticket feed.
# It is used only when Ticket.TowerID/TrackID and source TrackName are missing.
COMPANY_TRACK_MAPPING = {
    "home depot": "THD Data",
}


def _is_generated_file(path: Path) -> bool:
    return path.name.startswith(GENERATED_PREFIX)


def discover_source_files(dataset_path: Path, single_file=None):
    if single_file:
        path = Path(single_file)
        if not path.exists():
            path = dataset_path / path.name
        if not path.exists():
            raise FileNotFoundError(f"File not found: {single_file}")
        return [path]

    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset folder not found: {dataset_path}")

    return sorted(
        [
            p for p in dataset_path.iterdir()
            if p.is_file()
            and p.suffix.lower() in SUPPORTED_EXTENSIONS
            and not _is_generated_file(p)
        ],
        key=lambda p: p.name.lower(),
    )


def read_source_file(filepath: Path) -> pd.DataFrame:
    ext = filepath.suffix.lower()
    if ext in {".xlsx", ".xls"}:
        df = pd.read_excel(filepath, dtype=object)
    elif ext == ".csv":
        df = pd.read_csv(filepath, dtype=object)
    elif ext == ".txt":
        try:
            df = pd.read_csv(filepath, sep="\t", dtype=object)
        except Exception:
            df = pd.read_csv(filepath, dtype=object)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    df.columns = [str(c).replace("\ufeff", "").strip() for c in df.columns]
    return df


def find_ticket_column(columns):
    candidates = [
        "TicketNumber", "Ticket_Number", "Number", "Incident_Number",
        "IncidentNumber", "Incident Number", "Ticket Number",
    ]
    lookup = {str(c).strip().lower(): c for c in columns}
    for candidate in candidates:
        actual = lookup.get(candidate.lower())
        if actual is not None:
            return actual
    return None


def normalize_ticket_key(value):
    if pd.isna(value):
        return ""
    value = str(value).strip()
    if not value or value.lower() in {"nan", "none", "null", "nat"}:
        return ""
    if value.endswith(".0") and value[:-2].isdigit():
        value = value[:-2]
    return value.upper()


def normalize_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip().lower()


def _not_blank(value) -> bool:
    return normalize_text(value) not in {"", "nan", "none", "null", "nat"}


def source_priority(filename: str) -> int:
    name = filename.lower()
    if any(x in name for x in ("closed", "resolved", "complete", "completed")):
        return 30
    if any(x in name for x in ("updated", "update", "current")):
        return 20
    return 10


def consolidate_duplicate_rows(group: pd.DataFrame) -> dict:
    """Merge duplicate occurrences into one record without loading duplicates."""
    work = group.copy()
    work["_Priority"] = work["SourceFile"].map(source_priority)
    work["_Order"] = range(len(work))
    work = work.sort_values(["_Priority", "_Order"], ascending=[False, True])

    result = {}
    for col in work.columns:
        if col in {"_Priority", "_Order", "TicketKey"}:
            continue
        values = [v for v in work[col].tolist() if _not_blank(v)]
        result[col] = values[0] if values else None

    result["SourceFile"] = " | ".join(
        dict.fromkeys(str(x) for x in group["SourceFile"].tolist())
    )
    return result


def compare_and_merge_files(files, dataset_path: Path):
    if not files:
        print("No supported source files found.")
        return None, None, 0, 0

    print("\n" + "=" * 70)
    print("PRE-LOAD DATA QUALITY CHECK")
    print("=" * 70)
    print(f"Source files found: {len(files)}")
    for f in files:
        print(f"  - {f.name}")

    frames = []
    read_errors = []
    for filepath in files:
        try:
            df = read_source_file(filepath)
            if df.empty:
                print(f"  WARNING: {filepath.name} is empty")
                continue

            df["SourceFile"] = filepath.name
            ticket_col = find_ticket_column(df.columns)
            if not ticket_col:
                read_errors.append(
                    f"{filepath.name}: no recognizable ticket-number column"
                )
                print(f"  ERROR: {read_errors[-1]}")
                continue

            df["TicketKey"] = df[ticket_col].map(normalize_ticket_key)
            missing_keys = int(df["TicketKey"].eq("").sum())
            if missing_keys:
                print(f"  WARNING: {filepath.name}: {missing_keys:,} row(s) have no ticket number")
            frames.append(df)
            print(f"  {filepath.name}: {len(df):,} records")
        except Exception as exc:
            read_errors.append(f"{filepath.name}: {exc}")
            print(f"  ERROR reading {filepath.name}: {exc}")

    if not frames:
        return None, None, 0, 0

    if read_errors:
        raise RuntimeError("Source file validation failed:\n" + "\n".join(read_errors))

    combined = pd.concat(frames, ignore_index=True, sort=False)
    valid_keys = combined["TicketKey"].ne("")
    key_counts = combined.loc[valid_keys, "TicketKey"].value_counts()
    duplicate_keys = set(key_counts[key_counts > 1].index)
    duplicate_mask = combined["TicketKey"].isin(duplicate_keys)

    duplicates = combined.loc[duplicate_mask].copy()
    if not duplicates.empty:
        source_count = duplicates.groupby("TicketKey")["SourceFile"].transform("nunique")
        row_count = duplicates.groupby("TicketKey")["TicketKey"].transform("size")
        duplicates["DuplicateCount"] = row_count
        duplicates["DuplicateSources"] = source_count
        duplicates["DuplicateType"] = duplicates.apply(
            lambda r: "Across files" if r["DuplicateSources"] > 1 else "Within file",
            axis=1,
        )
        duplicates = duplicates.sort_values(["TicketKey", "SourceFile"])
    else:
        duplicates = pd.DataFrame(
            columns=list(combined.columns)
            + ["DuplicateCount", "DuplicateSources", "DuplicateType"]
        )

    duplicate_path = dataset_path / DUPLICATE_OUTPUT
    if duplicate_path.exists():
        duplicate_path.unlink()

    # Keep the duplicate audit easy to inspect: detailed records + summary sheet.
    with pd.ExcelWriter(duplicate_path, engine="openpyxl") as writer:
        duplicates.to_excel(writer, sheet_name="Duplicates", index=False)
        if duplicate_keys:
            summary = (
                duplicates.groupby("TicketKey", as_index=False)
                .agg(
                    Occurrences=("TicketKey", "size"),
                    SourceFiles=("SourceFile", lambda s: " | ".join(dict.fromkeys(s))),
                )
                .sort_values("Occurrences", ascending=False)
            )
        else:
            summary = pd.DataFrame(columns=["TicketKey", "Occurrences", "SourceFiles"])
        summary.to_excel(writer, sheet_name="Summary", index=False)

    # Exactly one load-ready row per ticket key.
    merged_records = []
    grouped = combined[valid_keys].groupby("TicketKey", sort=False)
    for _, group in grouped:
        if len(group) == 1:
            record = group.iloc[0].to_dict()
            record.pop("TicketKey", None)
            merged_records.append(record)
        else:
            merged_records.append(consolidate_duplicate_rows(group))

    # Rows without ticket numbers are not safe to load as ticket records.
    missing_key_rows = int((~valid_keys).sum())
    if missing_key_rows:
        print(f"  SKIPPED from load-ready merge: {missing_key_rows:,} row(s) without TicketNumber")

    merged = pd.DataFrame(merged_records)
    if "SourceFile" in merged.columns:
        merged["SourceFile"] = merged["SourceFile"].fillna("").astype(str)

    merged_path = dataset_path / MERGED_OUTPUT
    if merged_path.exists():
        merged_path.unlink()
    merged.to_excel(merged_path, index=False)

    cross_file = 0
    within_file = 0
    if not duplicates.empty:
        cross_file = int((duplicates["DuplicateType"] == "Across files").sum())
        within_file = int((duplicates["DuplicateType"] == "Within file").sum())

    print("\nDATA QUALITY RESULT")
    print(f"  Total input records:         {len(combined):,}")
    print(f"  Unique ticket records:       {len(merged):,}")
    print(f"  Duplicate occurrences:       {len(duplicates):,}")
    print(f"  Duplicate ticket keys:       {len(duplicate_keys):,}")
    print(f"  Cross-file duplicate rows:   {cross_file:,}")
    print(f"  Within-file duplicate rows:  {within_file:,}")
    print(f"  Rows without ticket number:  {missing_key_rows:,}")
    print(f"\n  Duplicate report: {duplicate_path}")
    print(f"  Load-ready merge:  {merged_path}")
    print("=" * 70)
    return merged_path, duplicate_path, len(duplicates), len(merged)


def get_tower_track_map(db):
    towers = db.execute(text("SELECT TowerID, TowerName FROM qbr.Tower")).fetchall()
    tracks = db.execute(text("SELECT TrackID, TowerID, TrackName FROM qbr.Track")).fetchall()
    tower_by_name = {normalize_text(r[1]): r[0] for r in towers}
    track_by_name = {normalize_text(r[2]): (r[0], r[1]) for r in tracks}
    return tower_by_name, track_by_name


def get_customer_map(db):
    rows = db.execute(text("SELECT CustomerID, CustomerName FROM qbr.Customer")).fetchall()
    return {normalize_text(r[1]): r[0] for r in rows}


def map_assignment_to_track(assignment_group, track_map):
    if not _not_blank(assignment_group):
        return None, None

    assignment_group = str(assignment_group).strip()
    mapping = {
        "boa-ev": "BOA EV", "boa-ev-l1": "BOA EV", "boa-ev-l2": "BOA EV",
        "hsbc-col": "HSBC Collab", "hsbc-col-l1": "HSBC Collab", "hsbc-col-l2": "HSBC Collab",
        "pm": "Problem Management", "pm-l1": "Problem Management",
        "boa-tp": "BOA TP", "gtm-tp": "GTM TP", "hd-voice": "HD Voice (Bgl)",
        "scnoc": "SCNOC", "sec-cyb": "Cybersecurity", "sec-cyb-l1": "Cybersecurity", "sec-cyb-l2": "Cybersecurity",
        "dc-aci": "DC-ACI", "infra": "Infra", "soc": "SOC",
        "fn-sfnoc": "SFNOC", "fn-sfnoc-l1": "SFNOC", "fn-sfnoc-l2": "SFNOC",
        "fn-thd": "THD Data", "fn-thd-l1": "THD Data", "fn-thd-l2": "THD Data",
        "hsbc-data": "HSBC Data", "nc-ril": "RIL", "nc-ril-l1": "RIL", "nc-ril-l2": "RIL",
        "jlk-wireless": "THD Data", "jlk-r&s": "THD Data", "jlk": "THD Data",
    }

    normalized = normalize_text(assignment_group)
    target = mapping.get(normalized)
    if target and normalize_text(target) in track_map:
        return track_map[normalize_text(target)]

    upper = normalized
    for key, track_name in mapping.items():
        if key in upper or upper in key:
            if normalize_text(track_name) in track_map:
                return track_map[normalize_text(track_name)]

    if normalized in track_map:
        return track_map[normalized]

    return None, None


def map_company_to_track(company, track_map):
    """Map a company account to a track when relational IDs are absent."""
    target = COMPANY_TRACK_MAPPING.get(normalize_text(company))
    if target and normalize_text(target) in track_map:
        return track_map[normalize_text(target)]
    return None, None


def first_value(row, columns):
    for col in columns:
        if col in row.index and _not_blank(row.get(col)):
            return str(row.get(col)).strip()
    return None


def parse_date(row, columns):
    for col in columns:
        if col in row.index and _not_blank(row.get(col)):
            try:
                return pd.to_datetime(row.get(col))
            except Exception:
                continue
    return None


def clear_all_data(db=None):
    """Explicitly replace qbr.Ticket data. Other dashboard data is preserved."""
    own_session = db is None
    session = db or SessionLocal()
    try:
        session.execute(text("DELETE FROM qbr.Ticket"))
        session.commit()
        print("Existing qbr.Ticket data cleared successfully.")
    except Exception:
        session.rollback()
        raise
    finally:
        if own_session:
            session.close()


def load_dataframe(db, df, filename):
    print(f"\nLoading merged data: {filename}")
    print(f"  Load-ready records: {len(df):,}")

    _, track_map = get_tower_track_map(db)
    customer_map = get_customer_map(db)
    batch_id = db.execute(text("SELECT NEWID()")).scalar()

    insert_sql = text("""
        INSERT INTO qbr.Ticket (
            TicketNumber, ParentTicketNumber, TicketType,
            CustomerID, TowerID, TrackID,
            AssignmentGroup, CompanyAccount, ConfigurationItem,
            Priority, State, Impact, ShortDescription,
            OpenedAt, CreatedAt, UpdatedAt, ClosedAt,
            ResolutionCode, CauseCode, SourceFile, LoadBatchID, LoadedAt
        ) VALUES (
            :tn, :parent, :tt,
            :cid, :tid, :trid,
            :ag, :ca, :ci,
            :pri, :st, :imp, :sd,
            :opened, :created, :updated, :closed,
            :res, :cause, :sf, :batch, SYSUTCDATETIME()
        )
    """)

    loaded = 0
    skipped = 0
    errors = []
    seen_in_batch = set()

    try:
        for idx, row in df.iterrows():
            try:
                ticket_number = first_value(row, [
                    "Number", "TicketNumber", "Ticket_Number", "Incident_Number", "IncidentNumber",
                    "Incident Number", "Ticket Number"
                ])
                ticket_key = normalize_ticket_key(ticket_number)
                if not ticket_key:
                    skipped += 1
                    continue

                # Second safety gate: never insert the same TicketNumber twice in this batch.
                if ticket_key in seen_in_batch:
                    skipped += 1
                    continue
                seen_in_batch.add(ticket_key)

                parent = first_value(row, [
                    "Parent Incident", "ParentIncident", "Parent_Incident", "ParentTicketNumber", "Parent"
                ])
                ticket_type = "Child" if parent else "Parent"

                company = first_value(row, ["Company account", "CompanyAccount", "Company", "Customer"])
                customer_id = customer_map.get(normalize_text(company)) if company else None

                # Prefer explicit source IDs, then source TrackName, then assignment group,
                # and finally the confirmed CompanyAccount mapping.
                track_id = first_value(row, ["TrackID"])
                tower_id = first_value(row, ["TowerID"])
                source_track = first_value(row, ["TrackName", "Track"])

                if track_id and str(track_id).isdigit():
                    track_id = int(track_id)
                    row_track = db.execute(
                        text("SELECT TowerID FROM qbr.Track WHERE TrackID = :tid"),
                        {"tid": track_id},
                    ).scalar()
                    tower_id = int(row_track) if row_track is not None else None
                else:
                    track_id = None
                    tower_id = None

                if track_id is None and source_track:
                    ids = track_map.get(normalize_text(source_track))
                    if ids:
                        track_id, tower_id = ids

                if track_id is None:
                    assignment = first_value(row, [
                        "Assignment group", "AssignmentGroup", "Assignment_Group"
                    ])
                    track_id, tower_id = map_assignment_to_track(assignment, track_map)
                else:
                    assignment = first_value(row, [
                        "Assignment group", "AssignmentGroup", "Assignment_Group"
                    ])

                if track_id is None and company:
                    track_id, tower_id = map_company_to_track(company, track_map)

                opened = parse_date(row, ["Opened", "OpenedAt", "Opened_At", "Created", "CreatedDate"])
                created = parse_date(row, ["Created", "CreatedAt", "Created_Date"])
                updated = parse_date(row, ["Updated", "UpdatedAt", "Updated_Date"])
                closed = parse_date(row, ["Closed", "ClosedAt", "Closed_At", "Resolved", "ResolvedAt"])

                priority = first_value(row, ["Priority", "priority"])
                state = first_value(row, ["State", "Status", "state", "status"])
                impact = first_value(row, ["Impact", "impact"])
                ci = first_value(row, ["Configuration item", "ConfigurationItem", "Configuration_Item", "CI"])
                short_desc = first_value(row, ["Short description", "ShortDescription", "Short_Description", "Description"])
                if short_desc:
                    short_desc = short_desc[:500]
                resolution = first_value(row, ["Resolution code", "ResolutionCode", "Resolution_Code", "Resolution"])
                cause = first_value(row, ["Cause code", "CauseCode", "Cause_Code", "Cause"])

                # Existing DB records are skipped safely. Use --replace-tickets for a clean reload.
                exists = db.execute(
                    text("SELECT 1 FROM qbr.Ticket WHERE TicketNumber = :tn"),
                    {"tn": ticket_number},
                ).first()
                if exists:
                    skipped += 1
                    continue

                db.execute(insert_sql, {
                    "tn": ticket_number,
                    "parent": parent,
                    "tt": ticket_type,
                    "cid": customer_id,
                    "tid": tower_id,
                    "trid": track_id,
                    "ag": assignment,
                    "ca": company,
                    "ci": ci,
                    "pri": priority,
                    "st": state,
                    "imp": impact,
                    "sd": short_desc,
                    "opened": opened,
                    "created": created,
                    "updated": updated,
                    "closed": closed,
                    "res": resolution,
                    "cause": cause,
                    "sf": filename,
                    "batch": batch_id,
                })
                loaded += 1

            except Exception as exc:
                errors.append(f"row {idx + 1}: {exc}")

        if errors:
            db.rollback()
            print(f"  LOAD FAILED - rolling back {loaded:,} inserted row(s).")
            for msg in errors[:10]:
                print(f"    {msg}")
            return 0, len(errors), skipped

        db.commit()
        print(f"  Loaded: {loaded:,}, Skipped/existing: {skipped:,}, Errors: 0")
        return loaded, 0, skipped

    except Exception:
        db.rollback()
        raise


def _archive_successful_inputs(source_files, generated_files, dataset_path: Path):
    """Move a successfully processed batch out of app/dataset."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_dir = dataset_path / PROCESSED_FOLDER / timestamp
    archive_dir.mkdir(parents=True, exist_ok=True)

    moved = []
    for path in [*source_files, *generated_files]:
        path = Path(path)
        if not path.exists():
            continue
        destination = archive_dir / path.name
        if destination.exists():
            destination.unlink()
        shutil.move(str(path), str(destination))
        moved.append(path.name)

    return archive_dir, moved


def show_summary(db):
    print("\n" + "=" * 50)
    print("QBR DASHBOARD DATA SUMMARY")
    print("=" * 50)

    total = db.execute(text("SELECT COUNT(*) FROM qbr.Ticket")).scalar()
    parents = db.execute(text("SELECT COUNT(*) FROM qbr.Ticket WHERE TicketType = 'Parent'")).scalar()
    children = db.execute(text("SELECT COUNT(*) FROM qbr.Ticket WHERE TicketType = 'Child'")).scalar()
    open_tk = db.execute(text("SELECT COUNT(*) FROM qbr.Ticket WHERE State = 'Open' OR ClosedAt IS NULL")).scalar()
    closed_tk = db.execute(text("SELECT COUNT(*) FROM qbr.Ticket WHERE State = 'Closed'")).scalar()
    alerts = db.execute(text("SELECT COUNT(*) FROM qbr.Alert")).scalar()

    print(f"\nTICKETS:\n  Total: {total}\n  Parents: {parents}\n  Children: {children}\n  Open: {open_tk}\n  Closed: {closed_tk}")
    print(f"\nALERTS:\n  Total: {alerts}")

    towers = db.execute(text("""
        SELECT t.TowerName, COUNT(tk.TicketKey) AS cnt
        FROM qbr.Tower t
        LEFT JOIN qbr.Ticket tk ON tk.TowerID = t.TowerID
        GROUP BY t.TowerName
        ORDER BY cnt DESC
    """)).fetchall()
    print("\nBY TOWER:")
    for tower_name, count in towers:
        print(f"  {tower_name}: {count}")

    tracks = db.execute(text("""
        SELECT t.TowerName, tr.TrackName, COUNT(tk.TicketKey) AS cnt
        FROM qbr.Track tr
        JOIN qbr.Tower t ON t.TowerID = tr.TowerID
        LEFT JOIN qbr.Ticket tk ON tk.TrackID = tr.TrackID
        GROUP BY t.TowerName, tr.TrackName
        ORDER BY cnt DESC
    """)).fetchall()
    print("\nBY TRACK:")
    for tower_name, track_name, count in tracks:
        if count > 0:
            print(f"  {tower_name} > {track_name}: {count}")

    date_range = db.execute(text("""
        SELECT MIN(OpenedAt), MAX(OpenedAt) FROM qbr.Ticket WHERE OpenedAt IS NOT NULL
    """)).fetchone()
    if date_range[0]:
        print(f"\nDATE RANGE:\n  From: {date_range[0]}\n  To: {date_range[1]}")

    print("\n" + "=" * 50)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="QBR Dashboard Data Loader")
    parser.add_argument("--file", help="Specific source file to load")
    parser.add_argument("--show-summary", action="store_true", help="Show data summary")
    parser.add_argument(
        "--replace-tickets", "--clear", dest="replace_tickets", action="store_true",
        help="Replace all existing qbr.Ticket rows after pre-load validation; use only for a full clean reload",
    )
    parser.add_argument("--dataset-folder", default="app/dataset", help="Dataset folder path")
    args = parser.parse_args()

    dataset_path = Path(args.dataset_folder)

    if args.show_summary:
        db = SessionLocal()
        try:
            show_summary(db)
        finally:
            db.close()
        return

    try:
        source_files = discover_source_files(dataset_path, args.file)
    except FileNotFoundError as exc:
        print(exc)
        return

    if not source_files:
        print("No source files found in app/dataset.")
        return

    try:
        merged_path, duplicate_path, duplicate_rows, merged_rows = compare_and_merge_files(
            source_files, dataset_path
        )
    except Exception as exc:
        print(f"\nPRE-LOAD VALIDATION FAILED: {exc}")
        print("Source files were NOT moved and NO database load was attempted.")
        return

    if merged_path is None:
        print("Nothing to load.")
        return

    db = SessionLocal()
    try:
        # Validation/merge is complete before any destructive DB operation.
        if args.replace_tickets:
            print("\nFULL CLEAN TICKET RELOAD REQUESTED")
            print("Existing qbr.Ticket rows will be deleted only now, after duplicate validation.")
            try:
                db.execute(text("DELETE FROM qbr.Ticket"))
                db.commit()
                print("Existing qbr.Ticket data cleared successfully.")
            except Exception as exc:
                db.rollback()
                print(f"ERROR clearing qbr.Ticket: {exc}")
                print("Source files were retained for retry.")
                return

        merged_df = read_source_file(merged_path)
        loaded, errors, skipped = load_dataframe(db, merged_df, merged_path.name)

        if errors == 0:
            show_summary(db)
            generated_files = [duplicate_path, merged_path]
            archive_dir, moved_files = _archive_successful_inputs(
                source_files, generated_files, dataset_path
            )

            print("\n" + "=" * 70)
            print("POST-LOAD FILE CLEANUP")
            print("=" * 70)
            print("Data upload completed successfully with 0 load errors.")
            if moved_files:
                print("Files moved successfully:")
                for filename in moved_files:
                    print(f"  - {filename}")
                print(f"\nMoved location: {archive_dir}")
            print("=" * 70)
        else:
            print("\nPOST-LOAD FILE CLEANUP SKIPPED")
            print(
                f"Database load reported {errors:,} error(s). "
                "The transaction was rolled back and source files were retained in app/dataset."
            )

        print("\nLOAD COMPLETE")
        print(f"  Source files checked : {len(source_files)}")
        print(f"  Duplicate rows saved : {duplicate_rows:,}")
        print(f"  Merged rows prepared : {merged_rows:,}")
        print(f"  Rows inserted        : {loaded:,}")
        print(f"  Rows skipped         : {skipped:,}")
        print(f"  Load errors          : {errors:,}")
        if errors == 0:
            print(f"  Archived batch       : {archive_dir}")
        else:
            print("  Original source files: RETAINED")

    finally:
        db.close()


if __name__ == "__main__":
    main()
