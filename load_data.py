"""
QBR Dashboard - Data Loader
============================
Loads data from Excel (.xlsx), CSV (.csv), and text (.txt) files 
in the app/dataset folder into the database.

Usage:
    python load_data.py                    # Load all files in dataset folder
    python load_data.py --file created_tickets.xlsx
    python load_data.py --show-summary      # Show data summary
    python load_data.py --clear             # Clear all data before loading
"""

import sys
import os
from pathlib import Path
from datetime import datetime

import pandas as pd
from sqlalchemy import text

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import SessionLocal
from app.config import DATABASE_URL


def get_tower_track_map(db):
    """Get mapping of Tower/Track names to IDs."""
    towers = db.execute(text("SELECT TowerID, TowerName FROM qbr.Tower")).fetchall()
    tracks = db.execute(text("SELECT TrackID, TowerID, TrackName FROM qbr.Track")).fetchall()
    
    tower_map = {row[1]: row[0] for row in towers}
    track_map = {row[2]: (row[0], row[1]) for row in tracks}  # TrackName -> (TrackID, TowerID)
    
    return tower_map, track_map


def get_customer_map(db):
    """Get mapping of Customer names to IDs."""
    customers = db.execute(text("SELECT CustomerID, CustomerName FROM qbr.Customer")).fetchall()
    return {row[1]: row[0] for row in customers}


def map_assignment_to_track(assignment_group, track_map):
    """Map ServiceNow assignment group to a Track."""
    if not assignment_group or str(assignment_group).lower() == 'nan':
        return None, None
    
    assignment_group = str(assignment_group).strip()
    
    # Common mappings - extend as needed
    mapping = {
        'BOA-EV': 'BOA EV',
        'BOA-EV-L1': 'BOA EV',
        'BOA-EV-L2': 'BOA EV',
        'HSBC-COL': 'HSBC Collab',
        'HSBC-COL-L1': 'HSBC Collab',
        'HSBC-COL-L2': 'HSBC Collab',
        'PM': 'Problem Management',
        'PM-L1': 'Problem Management',
        'BOA-TP': 'BOA TP',
        'GTM-TP': 'GTM TP',
        'HD-VOICE': 'HD Voice (Bgl)',
        'SCNOC': 'SCNOC',
        'SEC-CYB': 'Cybersecurity',
        'SEC-CYB-L1': 'Cybersecurity',
        'SEC-CYB-L2': 'Cybersecurity',
        'DC-ACI': 'DC-ACI',
        'INFRA': 'Infra',
        'SOC': 'SOC',
        'FN-SFNOC': 'SFNOC',
        'FN-SFNOC-L1': 'SFNOC',
        'FN-SFNOC-L2': 'SFNOC',
        'FN-THD': 'THD Data',
        'FN-THD-L1': 'THD Data',
        'FN-THD-L2': 'THD Data',
        'HSBC-DATA': 'HSBC Data',
        'NC-RIL': 'RIL',
        'NC-RIL-L1': 'RIL',
        'NC-RIL-L2': 'RIL',
        'JLK-WIRELESS': 'THD Data',
        'JLK-R&S': 'THD Data',
        'JLK': 'THD Data',
    }
    
    # Try direct lookup first
    if assignment_group in mapping:
        track_name = mapping[assignment_group]
        if track_name in track_map:
            return track_map[track_name]
    
    # Try partial match
    for key, track_name in mapping.items():
        if key in assignment_group or assignment_group in key:
            if track_name in track_map:
                return track_map[track_name]
    
    return None, None


def load_dataframe(db, df, filename):
    """Load tickets from a DataFrame."""
    print(f"  Columns found: {list(df.columns)}")
    
    tower_map, track_map = get_tower_track_map(db)
    customer_map = get_customer_map(db)
    
    batch_id = db.execute(text("SELECT NEWID()")).scalar()
    loaded = 0
    errors = 0
    skipped = 0
    
    for idx, row in df.iterrows():
        try:
            # Get ticket number from various possible column names
            ticket_number = None
            for col in ['Number', 'TicketNumber', 'Ticket_Number', 'Incident_Number', 'IncidentNumber']:
                if col in df.columns and pd.notna(row.get(col)):
                    ticket_number = str(row[col]).strip()
                    break
            
            if not ticket_number:
                skipped += 1
                continue
            
            # Get parent ticket
            parent = None
            for col in ['Parent Incident', 'ParentIncident', 'Parent_Incident', 'ParentTicketNumber', 'Parent']:
                if col in df.columns and pd.notna(row.get(col)):
                    parent_val = str(row[col]).strip()
                    if parent_val and parent_val.lower() != 'nan' and parent_val != '':
                        parent = parent_val
                        break
            
            ticket_type = 'Child' if parent else 'Parent'
            
            # Map customer
            company = None
            for col in ['Company account', 'CompanyAccount', 'Company', 'Customer']:
                if col in df.columns and pd.notna(row.get(col)):
                    company = str(row[col]).strip()
                    if company.lower() == 'nan':
                        company = None
                    break
            
            customer_id = customer_map.get(company) if company else None
            
            # Map tower/track
            assignment = None
            for col in ['Assignment group', 'AssignmentGroup', 'Assignment_Group', 'Track', 'TrackName']:
                if col in df.columns and pd.notna(row.get(col)):
                    assignment = str(row[col]).strip()
                    if assignment.lower() == 'nan':
                        assignment = None
                    break
            
            track_id, tower_id = map_assignment_to_track(assignment, track_map) if assignment else (None, None)
            
            # Parse dates
            def parse_date(row, col_names):
                for col in col_names:
                    if col in df.columns and pd.notna(row.get(col)):
                        try:
                            return pd.to_datetime(row[col])
                        except:
                            pass
                return None
            
            opened = parse_date(row, ['Opened', 'OpenedAt', 'Opened_At', 'Created', 'CreatedDate'])
            created = parse_date(row, ['Created', 'CreatedAt', 'Created_Date'])
            updated = parse_date(row, ['Updated', 'UpdatedAt', 'Updated_Date'])
            closed = parse_date(row, ['Closed', 'ClosedAt', 'Closed_At', 'Resolved', 'ResolvedAt'])
            
            # Other fields
            priority = None
            for col in ['Priority', 'priority']:
                if col in df.columns and pd.notna(row.get(col)):
                    priority = str(row[col]).strip()
                    if priority.lower() == 'nan':
                        priority = None
                    break
            
            state = None
            for col in ['State', 'Status', 'state', 'status']:
                if col in df.columns and pd.notna(row.get(col)):
                    state = str(row[col]).strip()
                    if state.lower() == 'nan':
                        state = None
                    break
            
            impact = None
            for col in ['Impact', 'impact']:
                if col in df.columns and pd.notna(row.get(col)):
                    impact = str(row[col]).strip()
                    if impact.lower() == 'nan':
                        impact = None
                    break
            
            ci = None
            for col in ['Configuration item', 'ConfigurationItem', 'Configuration_Item', 'CI']:
                if col in df.columns and pd.notna(row.get(col)):
                    ci = str(row[col]).strip()
                    if ci.lower() == 'nan':
                        ci = None
                    break
            
            short_desc = None
            for col in ['Short description', 'ShortDescription', 'Short_Description', 'Description']:
                if col in df.columns and pd.notna(row.get(col)):
                    desc = str(row[col]).strip()
                    if desc.lower() != 'nan':
                        short_desc = desc[:500]
                    break
            
            resolution = None
            for col in ['Resolution code', 'ResolutionCode', 'Resolution_Code', 'Resolution']:
                if col in df.columns and pd.notna(row.get(col)):
                    resolution = str(row[col]).strip()
                    if resolution.lower() == 'nan':
                        resolution = None
                    break
            
            cause = None
            for col in ['Cause code', 'CauseCode', 'Cause_Code', 'Cause']:
                if col in df.columns and pd.notna(row.get(col)):
                    cause = str(row[col]).strip()
                    if cause.lower() == 'nan':
                        cause = None
                    break
            
            # Insert ticket (skip if exists)
            db.execute(text("""
                IF NOT EXISTS (SELECT 1 FROM qbr.Ticket WHERE TicketNumber = :tn)
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
            """), {
                'tn': ticket_number,
                'parent': parent,
                'tt': ticket_type,
                'cid': customer_id,
                'tid': tower_id,
                'trid': track_id,
                'ag': assignment,
                'ca': company,
                'ci': ci,
                'pri': priority,
                'st': state,
                'imp': impact,
                'sd': short_desc,
                'opened': opened,
                'created': created,
                'updated': updated,
                'closed': closed,
                'res': resolution,
                'cause': cause,
                'sf': filename,
                'batch': batch_id
            })
            
            loaded += 1
            
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"    Error on row {idx + 1}: {e}")
    
    db.commit()
    print(f"  Loaded: {loaded}, Skipped: {skipped}, Errors: {errors}")
    return loaded, errors


def load_file(db, filepath):
    """Load data from a file based on its extension."""
    filepath = Path(filepath)
    ext = filepath.suffix.lower()
    
    print(f"\nLoading: {filepath.name}")
    
    try:
        if ext == '.xlsx' or ext == '.xls':
            df = pd.read_excel(filepath)
        elif ext == '.csv':
            df = pd.read_csv(filepath)
        elif ext == '.txt':
            # Try tab-separated first, then comma
            try:
                df = pd.read_csv(filepath, sep='\t')
            except:
                df = pd.read_csv(filepath)
        else:
            print(f"  Unsupported file type: {ext}")
            return 0, 0
        
        return load_dataframe(db, df, filepath.name)
        
    except Exception as e:
        print(f"  Error reading file: {e}")
        return 0, 0


def clear_all_data():
    """Clear all ticket and alert data."""
    db = SessionLocal()
    try:
        print("Clearing all ticket and alert data...")
        db.execute(text("DELETE FROM qbr.TicketAlert"))
        db.execute(text("DELETE FROM qbr.Ticket"))
        db.execute(text("DELETE FROM qbr.Alert"))
        db.commit()
        print("  Data cleared!")
    finally:
        db.close()


def show_summary(db):
    """Show database summary."""
    print("\n" + "=" * 50)
    print("QBR DASHBOARD DATA SUMMARY")
    print("=" * 50)
    
    # Ticket counts
    total = db.execute(text("SELECT COUNT(*) FROM qbr.Ticket")).scalar()
    parents = db.execute(text("SELECT COUNT(*) FROM qbr.Ticket WHERE TicketType = 'Parent'")).scalar()
    children = db.execute(text("SELECT COUNT(*) FROM qbr.Ticket WHERE TicketType = 'Child'")).scalar()
    open_tk = db.execute(text("SELECT COUNT(*) FROM qbr.Ticket WHERE State = 'Open' OR ClosedAt IS NULL")).scalar()
    closed_tk = db.execute(text("SELECT COUNT(*) FROM qbr.Ticket WHERE State = 'Closed'")).scalar()
    
    print(f"\nTICKETS:")
    print(f"  Total: {total}")
    print(f"  Parents: {parents}")
    print(f"  Children: {children}")
    print(f"  Open: {open_tk}")
    print(f"  Closed: {closed_tk}")
    
    # Alert counts
    alerts = db.execute(text("SELECT COUNT(*) FROM qbr.Alert")).scalar()
    print(f"\nALERTS:")
    print(f"  Total: {alerts}")
    
    # By Tower
    print(f"\nBY TOWER:")
    towers = db.execute(text("""
        SELECT t.TowerName, COUNT(tk.TicketKey) as cnt
        FROM qbr.Tower t
        LEFT JOIN qbr.Ticket tk ON tk.TowerID = t.TowerID
        GROUP BY t.TowerName
        ORDER BY cnt DESC
    """)).fetchall()
    for tower_name, count in towers:
        print(f"  {tower_name}: {count}")
    
    # By Track
    print(f"\nBY TRACK:")
    tracks = db.execute(text("""
        SELECT t.TowerName, tr.TrackName, COUNT(tk.TicketKey) as cnt
        FROM qbr.Track tr
        JOIN qbr.Tower t ON t.TowerID = tr.TowerID
        LEFT JOIN qbr.Ticket tk ON tk.TrackID = tr.TrackID
        GROUP BY t.TowerName, tr.TrackName
        ORDER BY cnt DESC
    """)).fetchall()
    for tower_name, track_name, count in tracks:
        if count > 0:
            print(f"  {tower_name} > {track_name}: {count}")
    
    # Date range
    date_range = db.execute(text("""
        SELECT MIN(OpenedAt), MAX(OpenedAt) FROM qbr.Ticket WHERE OpenedAt IS NOT NULL
    """)).fetchone()
    if date_range[0]:
        print(f"\nDATE RANGE:")
        print(f"  From: {date_range[0]}")
        print(f"  To: {date_range[1]}")
    
    print("\n" + "=" * 50)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='QBR Dashboard Data Loader')
    parser.add_argument('--file', help='Specific file to load')
    parser.add_argument('--show-summary', action='store_true', help='Show data summary')
    parser.add_argument('--clear', action='store_true', help='Clear all data before loading')
    parser.add_argument('--dataset-folder', default='app/dataset', help='Dataset folder path')
    
    args = parser.parse_args()
    
    db = SessionLocal()
    
    try:
        if args.clear:
            clear_all_data()
        
        if args.show_summary:
            show_summary(db)
            return
        
        if args.file:
            # Load specific file
            filepath = Path(args.file)
            if not filepath.exists():
                filepath = Path(args.dataset_folder) / args.file
            if filepath.exists():
                load_file(db, filepath)
            else:
                print(f"File not found: {args.file}")
        else:
            # Load all supported files in dataset folder
            dataset_path = Path(args.dataset_folder)
            if dataset_path.exists():
                supported_extensions = ['.xlsx', '.xls', '.csv', '.txt']
                files = []
                for ext in supported_extensions:
                    files.extend(dataset_path.glob(f'*{ext}'))
                
                if files:
                    print(f"Found {len(files)} files in {args.dataset_folder}")
                    for filepath in sorted(files):
                        load_file(db, filepath)
                else:
                    print(f"No supported files found in {args.dataset_folder}")
                    print("Supported formats: .xlsx, .xls, .csv, .txt")
            else:
                print(f"Dataset folder not found: {args.dataset_folder}")
        
        # Show summary after loading
        show_summary(db)
        
    finally:
        db.close()


if __name__ == '__main__':
    main()
