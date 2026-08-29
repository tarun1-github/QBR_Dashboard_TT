"""
QBR Dashboard - Data Loader
============================
Loads data from Excel (.xlsx), CSV (.csv), and text (.txt) files in app/dataset.

DATA QUALITY + ARCHIVE FLOW
---------------------------
Before database insert this loader:
  1. Discovers all supported source files in app/dataset.
  2. Compares records across files using the ticket-number field.
  3. Detects duplicate records within a file and across files.
  4. Saves ALL duplicate occurrences to _duplicate_records.xlsx.
  5. Builds one consolidated row per ticket in _merged_input.xlsx.
  6. Loads ONLY the consolidated data into qbr.Ticket.
  7. ONLY when the DB load completes with zero row errors, moves the original
     source files plus generated audit files into app/dataset/processed/<timestamp>/.
  8. If any DB error occurs, source files stay in app/dataset for retry/audit.

Generated files beginning with '_' are never treated as source inputs.
"""

import sys
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import text

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import SessionLocal

SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".txt"}
GENERATED_PREFIX = "_"
MERGED_OUTPUT = "_merged_input.xlsx"
DUPLICATE_OUTPUT = "_duplicate_records.xlsx"
PROCESSED_FOLDER = "processed"


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
        df = pd.read_excel(filepath)
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
    if not value or value.lower() in {"nan", "none", "null"}:
        return ""
    if value.endswith(".0") and value[:-2].isdigit():
        value = value[:-2]
    return value.upper()


def _not_blank(value):
    if pd.isna(value):
        return False
    return str(value).strip().lower() not in {"", "nan", "none", "null", "nat"}


def source_priority(filename: str) -> int:
    name = filename.lower()
    if any(x in name for x in ("closed", "resolved", "complete", "completed")):
        return 30
    if any(x in name for x in ("updated", "update", "current")):
        return 20
    return 10


def consolidate_duplicate_rows(group: pd.DataFrame) -> dict:
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
    for filepath in files:
        try:
            df = read_source_file(filepath)
            if df.empty:
                print(f"  WARNING: {filepath.name} is empty")
                continue
            df["SourceFile"] = filepath.name
            ticket_col = find_ticket_column(df.columns)
            if ticket_col:
                df["TicketKey"] = df[ticket_col].map(normalize_ticket_key)
            else:
                df["TicketKey"] = ""
                print(f"  WARNING: {filepath.name} has no recognizable ticket-number column")
            frames.append(df)
            print(f"  {filepath.name}: {len(df):,} records")
        except Exception as exc:
            print(f"  ERROR reading {filepath.name}: {exc}")

    if not frames:
        return None, None, 0, 0

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
            columns=list(combined.columns) + [
                "DuplicateCount", "DuplicateSources", "DuplicateType"
            ]
        )

    duplicate_path = dataset_path / DUPLICATE_OUTPUT
    if duplicate_path.exists():
        duplicate_path.unlink()
    duplicates.to_excel(duplicate_path, index=False)

    merged_records = []
    grouped = combined[valid_keys].groupby("TicketKey", sort=False)
    for _, group in grouped:
        if len(group) == 1:
            record = group.iloc[0].to_dict()
            record.pop("TicketKey", None)
            merged_records.append(record)
        else:
            merged_records.append(consolidate_duplicate_rows(group))

    for _, row in combined.loc[~valid_keys].iterrows():
        record = row.to_dict()
        record.pop("TicketKey", None)
        merged_records.append(record)

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
    print(f"  Total input records:        {len(combined):,}")
    print(f"  Unique ticket records:      {len(merged):,}")
    print(f"  Duplicate occurrences:      {len(duplicates):,}")
    print(f"  Duplicate ticket keys:      {len(duplicate_keys):,}")
    print(f"  Cross-file duplicate rows:   {cross_file:,}")
    print(f"  Within-file duplicate rows:  {within_file:,}")
    print(f"\n  Duplicate report: {duplicate_path}")
    print(f"  Load-ready merge:  {merged_path}")
    print("=" * 70)
    return merged_path, duplicate_path, len(duplicates), len(merged)


def get_tower_track_map(db):
    towers = db.execute(text("SELECT TowerID, TowerName FROM qbr.Tower")).fetchall()
    tracks = db.execute(text("SELECT TrackID, TowerID, TrackName FROM qbr.Track")).fetchall()
    return {r[1]: r[0] for r in towers}, {r[2]: (r[0], r[1]) for r in tracks}


def get_customer_map(db):
    rows = db.execute(text("SELECT CustomerID, CustomerName FROM qbr.Customer")).fetchall()
    return {r[1]: r[0] for r in rows}


def map_assignment_to_track(assignment_group, track_map):
    if not assignment_group or str(assignment_group).lower() == "nan":
        return None, None

    assignment_group = str(assignment_group).strip()
    mapping = {
        "BOA-EV": "BOA EV", "BOA-EV-L1": "BOA EV", "BOA-EV-L2": "BOA EV",
        "HSBC-COL": "HSBC Collab", "HSBC-COL-L1": "HSBC Collab", "HSBC-COL-L2": "HSBC Collab",
        "PM": "Problem Management", "PM-L1": "Problem Management",
        "BOA-TP": "BOA TP", "GTM-TP": "GTM TP", "HD-VOICE": "HD Voice (Bgl)",
        "SCNOC": "SCNOC", "SEC-CYB": "Cybersecurity", "SEC-CYB-L1": "Cybersecurity", "SEC-CYB-L2": "Cybersecurity",
        "DC-ACI": "DC-ACI", "INFRA": "Infra", "SOC": "SOC",
        "FN-SFNOC": "SFNOC", "FN-SFNOC-L1": "SFNOC", "FN-SFNOC-L2": "SFNOC",
        "FN-THD": "THD Data", "FN-THD-L1": "THD Data", "FN-THD-L2": "THD Data",
        "HSBC-DATA": "HSBC Data", "NC-RIL": "RIL", "NC-RIL-L1": "RIL", "NC-RIL-L2": "RIL",
        "JLK-WIRELESS": "THD Data", "JLK-R&S": "THD Data", "JLK": "THD Data",
    }

    if assignment_group in mapping and mapping[assignment_group] in track_map:
        return track_map[mapping[assignment_group]]

    upper = assignment_group.upper()
    for key, track_name in mapping.items():
        if key.upper() in upper or upper in key.upper():
            if track_name in track_map:
                return track_map[track_name]

    for track_name, ids in track_map.items():
        if str(track_name).strip().upper() == upper:
            return ids

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


def load_dataframe(db, df, filename):
    print(f"\nLoading merged data: {filename}")
    print(f"  Columns found: {list(df.columns)}")

    _, track_map = get_tower_track_map(db)
    customer_map = get_customer_map(db)
    batch_id = db.execute(text("SELECT NEWID()")).scalar()
    loaded = errors = skipped = existing = 0

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

    for idx, row in df.iterrows():
        try:
            ticket_number = first_value(row, [
                "Number", "TicketNumber", "Ticket_Number", "Incident_Number", "IncidentNumber",
                "Incident Number", "Ticket Number"
            ])
            if not ticket_number:
                skipped += 1
                continue

            parent = first_value(row, [
                "Parent Incident", "ParentIncident", "Parent_Incident", "ParentTicketNumber", "Parent"
            ])
            ticket_type = "Child" if parent else "Parent"

            company = first_value(row, ["Company account", "CompanyAccount", "Company", "Customer"])
            customer_id = customer_map.get(company) if company else None

            assignment = first_value(row, [
                "Assignment group", "AssignmentGroup", "Assignment_Group", "Track", "TrackName"
            ])
            track_id, tower_id = map_assignment_to_track(assignment, track_map) if assignment else (None, None)

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

            exists = db.execute(
                text("SELECT 1 FROM qbr.Ticket WHERE TicketNumber = :tn"),
                {"tn": ticket_number},
            ).first()
            if exists:
                existing += 1
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
            errors += 1
            if errors <= 5:
                print(f"    Error on row {idx + 1}: {exc}")

    db.commit()
    print(f"  Loaded: {loaded:,}, Existing DB: {existing:,}, Skipped: {skipped:,}, Errors: {errors:,}")
    return loaded, errors


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
    parser.add_argument("--clear", action="store_true", help="Clear all data before loading")
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

    if args.clear:
        clear_all_data()

    try:
        source_files = discover_source_files(dataset_path, args.file)
    except FileNotFoundError as exc:
        print(exc)
        return

    merged_path, duplicate_path, duplicate_rows, merged_rows = compare_and_merge_files(
        source_files, dataset_path
    )
    if merged_path is None:
        print("Nothing to load.")
        return

    db = SessionLocal()
    try:
        merged_df = read_source_file(merged_path)
        loaded, errors = load_dataframe(db, merged_df, merged_path.name)
        show_summary(db)

        if errors == 0:
            generated_files = [duplicate_path, merged_path]
            archive_dir, moved_files = _archive_successful_inputs(
                source_files, generated_files, dataset_path
            )

            print("\n" + "=" * 70)
            print("POST-LOAD FILE CLEANUP")
            print("=" * 70)
            print("Data upload completed successfully with 0 load errors.")
            if moved_files:
                print("Source/audit file(s) moved successfully:")
                for filename in moved_files:
                    print(f"  - {filename}")
                print(f"\nMoved location: {archive_dir}")
            else:
                print("No files required moving.")
            print("=" * 70)
        else:
            archive_dir = None
            print("\nPOST-LOAD FILE CLEANUP SKIPPED")
            print(
                f"Database load reported {errors:,} error(s). "
                "Source files were retained in app/dataset for retry/audit."
            )

        print("\nLOAD COMPLETE")
        print(f"  Source files checked : {len(source_files)}")
        print(f"  Duplicate rows saved : {duplicate_rows:,}")
        print(f"  Merged rows prepared  : {merged_rows:,}")
        print(f"  Rows inserted         : {loaded:,}")
        print(f"  Load errors           : {errors:,}")
        if errors == 0:
            print(f"  Archived batch        : {archive_dir}")
        else:
            print("  Original source files : RETAINED")
    finally:
        db.close()


if __name__ == "__main__":
    main()
