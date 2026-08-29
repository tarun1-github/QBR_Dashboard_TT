"""
QBR Dashboard - Database Migration (Python) - Fixed Version
============================================================
Handles schema migration from old to new structure.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import pyodbc
from app.config import DATABASE_SERVER, DATABASE_NAME, DATABASE_USER, DB_PASSWORD, DB_DRIVER


def get_connection():
    connection_string = (
        f"DRIVER={{{DB_DRIVER}}};"
        f"SERVER={DATABASE_SERVER};"
        f"DATABASE={DATABASE_NAME};"
        f"UID={DATABASE_USER};"
        f"PWD={DB_PASSWORD};"
        "TrustServerCertificate=yes;"
    )
    return pyodbc.connect(connection_string)


def execute_sql(cursor, sql, description=""):
    """Execute SQL, ignoring common errors."""
    if description:
        print(f"  {description}")
    try:
        cursor.execute(sql)
        cursor.commit()
        return True
    except pyodbc.ProgrammingError as e:
        err_str = str(e)
        if 'already' in err_str.lower() or 'exists' in err_str.lower():
            return True
        print(f"    WARNING: {e}")
        return False
    except Exception as e:
        print(f"    ERROR: {e}")
        return False


def check_table_exists(cursor, table_name):
    """Check if table exists."""
    cursor.execute(f"""
        SELECT COUNT(*) FROM sys.tables 
        WHERE name = '{table_name}' AND schema_id = SCHEMA_ID('qbr')
    """)
    return cursor.fetchone()[0] > 0


def check_table_has_data(cursor, table_name):
    """Check if table has data."""
    cursor.execute(f"SELECT COUNT(*) FROM qbr.{table_name}")
    return cursor.fetchone()[0] > 0


def main():
    print()
    print("=" * 50)
    print("QBR Dashboard - Database Migration")
    print("=" * 50)
    print()
    print(f"Server: {DATABASE_SERVER}")
    print(f"Database: {DATABASE_NAME}")
    print()

    conn = get_connection()
    cursor = conn.cursor()

    # ============================================================
    # Step 1: Create Tower table
    # ============================================================
    print("[1/8] Setting up Tower table...")
    
    if not check_table_exists(cursor, 'Tower'):
        execute_sql(cursor, """
            CREATE TABLE qbr.Tower(
                TowerID INT IDENTITY PRIMARY KEY,
                TowerName NVARCHAR(100) NOT NULL UNIQUE,
                TowerDescription NVARCHAR(500) NULL,
                DisplayOrder INT NOT NULL DEFAULT 0,
                IsActive BIT NOT NULL DEFAULT 1,
                CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
            )
        """, "Creating Tower table")
    else:
        print("  Tower table already exists")
    
    # Insert towers if empty
    if not check_table_has_data(cursor, 'Tower'):
        towers = [
            ('Collaboration', 'Collaboration Services Tower', 1),
            ('Security', 'Security Operations Tower', 2),
            ('Foundation', 'Foundation & Data Tower', 3),
            ('Non-CMS', 'Non-CMS Services Tower', 4),
        ]
        for name, desc, order in towers:
            execute_sql(cursor,
                f"INSERT INTO qbr.Tower (TowerName, TowerDescription, DisplayOrder, IsActive) "
                f"VALUES (N'{name}', N'{desc}', {order}, 1)",
                f"  Tower: {name}"
            )
    else:
        print("  Tower table already has data")

    # ============================================================
    # Step 2: Create Track table (without FK first)
    # ============================================================
    print("\n[2/8] Setting up Track table...")
    
    if not check_table_exists(cursor, 'Track'):
        print("  Creating Track table...")
        try:
            # Drop old constraint if exists
            cursor.execute("""
                IF EXISTS (SELECT 1 FROM sys.key_constraints WHERE name = 'UQ_TowerTrack' AND parent_object_id = OBJECT_ID('qbr.TowerTrack'))
                ALTER TABLE qbr.TowerTrack DROP CONSTRAINT UQ_TowerTrack
            """)
            cursor.commit()
            
            cursor.execute("""
                CREATE TABLE qbr.Track(
                    TrackID INT IDENTITY PRIMARY KEY,
                    TowerID INT NOT NULL,
                    TrackName NVARCHAR(100) NOT NULL,
                    TrackDescription NVARCHAR(500) NULL,
                    DisplayOrder INT NOT NULL DEFAULT 0,
                    IsActive BIT NOT NULL DEFAULT 1,
                    CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
                    CONSTRAINT UQ_Track_TowerTrack UNIQUE(TowerID, TrackName)
                )
            """)
            cursor.commit()
            print("  Track table created")
        except Exception as e:
            print(f"  Track table creation: {e}")
    else:
        print("  Track table already exists")
    
    # Insert tracks if empty
    if not check_table_has_data(cursor, 'Track'):
        tracks = [
            (1, 'BOA EV', 'BOA EV Services', 1),
            (1, 'HSBC Collab', 'HSBC Collaboration', 2),
            (1, 'Problem Management', 'Problem Management', 3),
            (1, 'BOA TP', 'BOA TP Services', 4),
            (1, 'GTM TP', 'GTM TP Services', 5),
            (1, 'HD Voice (Bgl)', 'HD Voice Bangalore', 6),
            (1, 'SCNOC', 'SCNOC Services', 7),
            (2, 'Cybersecurity', 'Cybersecurity Operations', 1),
            (2, 'DC-ACI', 'Data Center ACI', 2),
            (2, 'Infra', 'Infrastructure Security', 3),
            (2, 'SOC', 'Security Operations Center', 4),
            (3, 'SFNOC', 'SFNOC Operations', 1),
            (3, 'THD Data', 'THD Data Services', 2),
            (3, 'HSBC Data', 'HSBC Data Services', 3),
            (4, 'RIL', 'RIL Services', 1),
        ]
        for tower_id, name, desc, order in tracks:
            execute_sql(cursor,
                f"INSERT INTO qbr.Track (TowerID, TrackName, TrackDescription, DisplayOrder, IsActive) "
                f"VALUES ({tower_id}, N'{name}', N'{desc}', {order}, 1)",
                f"  Track: {name}"
            )
    else:
        print("  Track table already has data")

    # Add foreign key to Track
    execute_sql(cursor,
        "IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_Track_Tower') "
        "ALTER TABLE qbr.Track ADD CONSTRAINT FK_Track_Tower FOREIGN KEY (TowerID) REFERENCES qbr.Tower(TowerID)",
        "Adding Track->Tower foreign key"
    )

    # ============================================================
    # Step 3: Create Customer table
    # ============================================================
    print("\n[3/8] Setting up Customer table...")
    
    if not check_table_exists(cursor, 'Customer'):
        execute_sql(cursor, """
            CREATE TABLE qbr.Customer(
                CustomerID INT IDENTITY PRIMARY KEY,
                CustomerName NVARCHAR(200) NOT NULL UNIQUE,
                CustomerCode NVARCHAR(50) NULL,
                IsActive BIT NOT NULL DEFAULT 1,
                CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
            )
        """, "Creating Customer table")
    else:
        print("  Customer table already exists")
    
    if not check_table_has_data(cursor, 'Customer'):
        customers = [
            ('Dome Depot', 'DOME'),
            ('Jio Platforms', 'JIO'),
            ('HSBC', 'HSBC'),
            ('Bank of America', 'BOA'),
            ('Reliance', 'RIL'),
        ]
        for name, code in customers:
            execute_sql(cursor,
                f"INSERT INTO qbr.Customer (CustomerName, CustomerCode, IsActive) "
                f"VALUES (N'{name}', N'{code}', 1)",
                f"  Customer: {name}"
            )
    else:
        print("  Customer table already has data")

    # ============================================================
    # Step 4: Add columns to Ticket table
    # ============================================================
    print("\n[4/8] Adding columns to Ticket table...")
    ticket_cols = [
        ('CustomerID', 'INT NULL'),
        ('TowerID', 'INT NULL'),
        ('TrackID', 'INT NULL'),
        ('Impact', 'NVARCHAR(50) NULL'),
        ('ShortDescription', 'NVARCHAR(500) NULL'),
        ('ResolutionCode', 'NVARCHAR(200) NULL'),
        ('CauseCode', 'NVARCHAR(200) NULL'),
    ]
    for col_name, col_type in ticket_cols:
        execute_sql(cursor,
            f"IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE name = '{col_name}' AND object_id = OBJECT_ID('qbr.Ticket')) "
            f"ALTER TABLE qbr.Ticket ADD {col_name} {col_type}",
            f"  Column: {col_name}"
        )

    # ============================================================
    # Step 5: Add columns to Alert table
    # ============================================================
    print("\n[5/8] Adding columns to Alert table...")
    alert_cols = [
        ('CustomerID', 'INT NULL'),
        ('TowerID', 'INT NULL'),
        ('TrackID', 'INT NULL'),
        ('AlertDescription', 'NVARCHAR(500) NULL'),
    ]
    for col_name, col_type in alert_cols:
        execute_sql(cursor,
            f"IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE name = '{col_name}' AND object_id = OBJECT_ID('qbr.Alert')) "
            f"ALTER TABLE qbr.Alert ADD {col_name} {col_type}",
            f"  Column: {col_name}"
        )

    # ============================================================
    # Step 6: Create DashboardKPI table
    # ============================================================
    print("\n[6/8] Setting up DashboardKPI table...")
    
    if not check_table_exists(cursor, 'DashboardKPI'):
        execute_sql(cursor, """
            CREATE TABLE qbr.DashboardKPI(
                KPIID INT IDENTITY PRIMARY KEY,
                KPIName NVARCHAR(100) NOT NULL,
                KPICategory NVARCHAR(50) NOT NULL,
                DisplayOrder INT NOT NULL DEFAULT 0,
                Icon NVARCHAR(10) NULL,
                ColorCode NVARCHAR(20) NULL,
                IsActive BIT NOT NULL DEFAULT 1,
                CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
            )
        """, "Creating DashboardKPI table")
    else:
        print("  DashboardKPI table already exists")
    
    if not check_table_has_data(cursor, 'DashboardKPI'):
        kpis = [
            ('Total Tickets', 'executive', 1, '🎫', '#19708b'),
            ('Parent Tickets', 'executive', 2, '👑', '#5b8f3b'),
            ('Child Tickets', 'executive', 3, '↳', '#ee8233'),
            ('Alerts', 'executive', 4, '⚡', '#c91414'),
            ('Max/Min Per Day', 'executive', 5, '📊', '#8a6b09'),
            ('Avg Tickets/Day', 'executive', 6, '📈', '#2d7d9a'),
            ('Open Tickets', 'status', 7, '🔵', '#1e88e5'),
            ('Closed Tickets', 'status', 8, '✅', '#43a047'),
            ('Critical Priority', 'priority', 10, '🔴', '#d32f2f'),
            ('High Priority', 'priority', 11, '🟠', '#f57c00'),
        ]
        for name, cat, order, icon, color in kpis:
            execute_sql(cursor,
                f"INSERT INTO qbr.DashboardKPI (KPIName, KPICategory, DisplayOrder, Icon, ColorCode, IsActive) "
                f"VALUES (N'{name}', N'{cat}', {order}, N'{icon}', N'{color}', 1)",
                f"  KPI: {name}"
            )
    else:
        print("  DashboardKPI table already has data")

    # ============================================================
    # Step 7: Insert sample tickets
    # ============================================================
    print("\n[7/8] Inserting sample tickets...")
    
    # Check if sample tickets already exist
    cursor.execute("SELECT COUNT(*) FROM qbr.Ticket WHERE TicketNumber LIKE 'INC-2026-%'")
    if cursor.fetchone()[0] == 0:
        sample_tickets = [
            ('INC-2026-00001', None, 1, 1, '1 - Critical', 'Closed', '2026-07-01 08:30:00', '2026-07-01 11:45:00'),
            ('INC-2026-00002', 'INC-2026-00001', 1, 1, '2 - High', 'Closed', '2026-07-01 08:35:00', '2026-07-01 11:45:00'),
            ('INC-2026-00003', None, 1, 1, '2 - High', 'Closed', '2026-07-05 14:20:00', '2026-07-05 17:30:00'),
            ('INC-2026-00004', None, 1, 1, '3 - Moderate', 'Closed', '2026-07-10 09:15:00', '2026-07-10 14:30:00'),
            ('INC-2026-00005', 'INC-2026-00004', 1, 1, '3 - Moderate', 'Closed', '2026-07-10 09:20:00', '2026-07-10 14:30:00'),
            ('INC-2026-00006', None, 1, 2, '1 - Critical', 'Closed', '2026-07-02 07:00:00', '2026-07-02 11:30:00'),
            ('INC-2026-00007', 'INC-2026-00006', 1, 2, '2 - High', 'Closed', '2026-07-02 07:10:00', '2026-07-02 11:30:00'),
            ('INC-2026-00008', None, 1, 2, '2 - High', 'Closed', '2026-07-08 16:45:00', '2026-07-08 19:30:00'),
            ('INC-2026-00009', None, 1, 2, '3 - Moderate', 'Closed', '2026-07-15 10:30:00', '2026-07-15 15:00:00'),
            ('INC-2026-00010', None, 1, 2, '2 - High', 'Closed', '2026-07-20 11:00:00', '2026-07-20 17:00:00'),
            ('INC-2026-00011', None, 2, 8, '1 - Critical', 'Closed', '2026-07-01 03:00:00', '2026-07-01 07:30:00'),
            ('INC-2026-00012', 'INC-2026-00011', 2, 8, '1 - Critical', 'Closed', '2026-07-01 03:05:00', '2026-07-01 07:30:00'),
            ('INC-2026-00013', None, 2, 8, '2 - High', 'Closed', '2026-07-07 22:15:00', '2026-07-08 01:30:00'),
            ('INC-2026-00014', None, 2, 8, '3 - Moderate', 'Closed', '2026-07-12 13:45:00', '2026-07-12 16:30:00'),
            ('INC-2026-00015', 'INC-2026-00014', 2, 8, '3 - Moderate', 'Closed', '2026-07-12 13:50:00', '2026-07-12 16:30:00'),
            ('INC-2026-00016', None, 3, 12, '1 - Critical', 'Closed', '2026-07-03 06:00:00', '2026-07-03 13:00:00'),
            ('INC-2026-00017', 'INC-2026-00016', 3, 12, '2 - High', 'Closed', '2026-07-03 06:15:00', '2026-07-03 13:00:00'),
            ('INC-2026-00018', None, 3, 12, '2 - High', 'Closed', '2026-07-09 19:30:00', '2026-07-09 23:30:00'),
            ('INC-2026-00019', None, 3, 12, '3 - Moderate', 'Closed', '2026-07-16 08:00:00', '2026-07-16 11:00:00'),
            ('INC-2026-00020', None, 3, 12, '2 - High', 'Closed', '2026-07-22 14:00:00', '2026-07-22 17:00:00'),
            ('INC-2026-00021', None, 3, 13, '2 - High', 'Closed', '2026-07-04 10:00:00', '2026-07-04 15:00:00'),
            ('INC-2026-00022', 'INC-2026-00021', 3, 13, '3 - Moderate', 'Closed', '2026-07-04 10:05:00', '2026-07-04 15:00:00'),
            ('INC-2026-00023', None, 3, 13, '3 - Moderate', 'Closed', '2026-07-11 20:00:00', '2026-07-11 22:30:00'),
            ('INC-2026-00024', None, 3, 13, '2 - High', 'Closed', '2026-07-18 07:30:00', '2026-07-18 11:00:00'),
            ('INC-2026-00025', 'INC-2026-00024', 3, 13, '2 - High', 'Closed', '2026-07-18 07:35:00', '2026-07-18 11:00:00'),
            ('INC-2026-00026', None, 4, 15, '2 - High', 'Closed', '2026-07-06 09:00:00', '2026-07-06 14:00:00'),
            ('INC-2026-00027', None, 4, 15, '3 - Moderate', 'Closed', '2026-07-13 15:30:00', '2026-07-13 18:00:00'),
            ('INC-2026-00028', None, 4, 15, '2 - High', 'Closed', '2026-07-19 11:00:00', '2026-07-19 16:00:00'),
            ('INC-2026-00029', 'INC-2026-00028', 4, 15, '3 - Moderate', 'Closed', '2026-07-19 11:10:00', '2026-07-19 16:00:00'),
            ('INC-2026-00030', None, 4, 15, '1 - Critical', 'Closed', '2026-07-25 08:00:00', '2026-07-25 13:00:00'),
        ]
        
        for ticket in sample_tickets:
            ticket_num, parent, tower_id, track_id, priority, state, opened, closed = ticket
            parent_val = f"N'{parent}'" if parent else "NULL"
            execute_sql(cursor,
                f"INSERT INTO qbr.Ticket (TicketNumber, ParentTicketNumber, TicketType, TowerID, TrackID, "
                f"Priority, State, OpenedAt, ClosedAt, SourceFile, LoadBatchID, LoadedAt) "
                f"VALUES (N'{ticket_num}', {parent_val}, N'{'Child' if parent else 'Parent'}', {tower_id}, {track_id}, "
                f"N'{priority}', N'{state}', '{opened}', '{closed}', 'sample_data', NEWID(), SYSUTCDATETIME())",
                f"  Ticket: {ticket_num}"
            )
    else:
        print("  Sample tickets already exist")

    # ============================================================
    # Step 8: Insert sample alerts
    # ============================================================
    print("\n[8/8] Inserting sample alerts...")
    
    cursor.execute("SELECT COUNT(*) FROM qbr.Alert WHERE AlertID LIKE 'ALT-2026-%'")
    if cursor.fetchone()[0] == 0:
        sample_alerts = [
            ('ALT-2026-001', 1, 1, 'Server', 'CPU_HIGH', 'Critical', '2026-07-01 08:25:00'),
            ('ALT-2026-002', 1, 1, 'Server', 'MEMORY_HIGH', 'Critical', '2026-07-01 08:28:00'),
            ('ALT-2026-003', 1, 1, 'Switch', 'LINK_DOWN', 'High', '2026-07-05 14:15:00'),
            ('ALT-2026-004', 1, 1, 'Middleware', 'RESPONSE_SLOW', 'Moderate', '2026-07-10 09:10:00'),
            ('ALT-2026-005', 1, 2, 'Server', 'SERVICE_DOWN', 'Critical', '2026-07-02 06:55:00'),
            ('ALT-2026-006', 1, 2, 'Server', 'QUEUE_HIGH', 'High', '2026-07-02 06:58:00'),
            ('ALT-2026-007', 1, 2, 'Firewall', 'RULE_VIOLATION', 'High', '2026-07-08 16:40:00'),
            ('ALT-2026-008', 1, 2, 'Web Portal', 'AUTH_FAILURE', 'Moderate', '2026-07-15 10:25:00'),
            ('ALT-2026-009', 2, 8, 'Firewall', 'DDOS_DETECTED', 'Critical', '2026-07-01 02:50:00'),
            ('ALT-2026-010', 2, 8, 'IDS/IPS', 'TRAFFIC_SPIKE', 'Critical', '2026-07-01 02:55:00'),
            ('ALT-2026-011', 2, 8, 'IDS/IPS', 'INTRUSION_ATTEMPT', 'High', '2026-07-07 22:10:00'),
            ('ALT-2026-012', 2, 8, 'Antivirus', 'MALWARE_DETECTED', 'Moderate', '2026-07-12 13:40:00'),
            ('ALT-2026-013', 3, 12, 'SAN', 'DISK_FAILURE', 'Critical', '2026-07-03 05:50:00'),
            ('ALT-2026-014', 3, 12, 'SAN', 'CAPACITY_LOW', 'High', '2026-07-03 05:55:00'),
            ('ALT-2026-015', 3, 12, 'Core Switch', 'REDUNDANCY_LOST', 'High', '2026-07-09 19:25:00'),
            ('ALT-2026-016', 3, 13, 'WLC', 'DEVICE_UNREACHABLE', 'High', '2026-07-04 09:50:00'),
            ('ALT-2026-017', 3, 13, 'Access Point', 'AP_DISCONNECT', 'Moderate', '2026-07-04 09:55:00'),
            ('ALT-2026-018', 3, 13, 'Edge Device', 'SITE_DOWN', 'High', '2026-07-18 07:25:00'),
            ('ALT-2026-019', 4, 15, 'Server', 'CPU_HIGH', 'High', '2026-07-06 08:50:00'),
            ('ALT-2026-020', 4, 15, 'API Gateway', 'TIMEOUT', 'High', '2026-07-19 10:50:00'),
            ('ALT-2026-021', 4, 15, 'Oracle', 'SLOW_QUERY', 'Critical', '2026-07-25 07:50:00'),
            ('ALT-2026-022', 4, 15, 'Router', 'INTERFACE_FLAP', 'Moderate', '2026-07-13 15:25:00'),
        ]
        
        for alert in sample_alerts:
            alert_id, tower_id, track_id, part, alert_type, severity, alert_time = alert
            execute_sql(cursor,
                f"INSERT INTO qbr.Alert (AlertID, TowerID, TrackID, Part, AlertType, Severity, AlertTime, "
                f"MonitoringTool, SourceFile, LoadBatchID, LoadedAt) "
                f"VALUES (N'{alert_id}', {tower_id}, {track_id}, N'{part}', N'{alert_type}', N'{severity}', "
                f"'{alert_time}', 'NZG2', 'sample_data', NEWID(), SYSUTCDATETIME())",
                f"  Alert: {alert_id}"
            )
    else:
        print("  Sample alerts already exist")

    # ============================================================
    # Step 9: Create Analytics Views
    # ============================================================
    print("\n[9/9] Creating analytics views...")
    
    views = [
        ("vw_ExecutiveKPI", """
            SELECT
                (SELECT COUNT(*) FROM qbr.Ticket WHERE OpenedAt IS NOT NULL) AS TotalTickets,
                (SELECT COUNT(*) FROM qbr.Ticket WHERE TicketType = 'Parent') AS ParentTickets,
                (SELECT COUNT(*) FROM qbr.Ticket WHERE TicketType = 'Child') AS ChildTickets,
                (SELECT COUNT(*) FROM qbr.Alert) AS TotalAlerts,
                (SELECT COUNT(*) FROM qbr.Ticket WHERE State = 'Open' OR ClosedAt IS NULL) AS OpenTickets,
                (SELECT COUNT(*) FROM qbr.Ticket WHERE State = 'Closed' AND ClosedAt IS NOT NULL) AS ClosedTickets,
                (SELECT COUNT(*) FROM qbr.Ticket WHERE Priority = '1 - Critical') AS CriticalTickets,
                (SELECT COUNT(*) FROM qbr.Ticket WHERE Priority = '2 - High') AS HighTickets,
                (SELECT COUNT(*) FROM qbr.Ticket WHERE Priority = '3 - Moderate') AS ModerateTickets
        """),
        ("vw_TowerTrackVolume", """
            SELECT
                t.TowerID, t.TowerName, tr.TrackID, tr.TrackName,
                COUNT(tk.TicketKey) AS TotalTickets,
                SUM(CASE WHEN tk.TicketType = 'Parent' THEN 1 ELSE 0 END) AS ParentTickets,
                SUM(CASE WHEN tk.TicketType = 'Child' THEN 1 ELSE 0 END) AS ChildTickets,
                SUM(CASE WHEN tk.Priority = '1 - Critical' THEN 1 ELSE 0 END) AS CriticalTickets,
                SUM(CASE WHEN tk.Priority = '2 - High' THEN 1 ELSE 0 END) AS HighTickets,
                SUM(CASE WHEN tk.State = 'Closed' THEN 1 ELSE 0 END) AS ClosedTickets,
                SUM(CASE WHEN tk.State = 'Open' OR tk.ClosedAt IS NULL THEN 1 ELSE 0 END) AS OpenTickets
            FROM qbr.Tower t
            JOIN qbr.Track tr ON tr.TowerID = t.TowerID
            LEFT JOIN qbr.Ticket tk ON tk.TrackID = tr.TrackID
            GROUP BY t.TowerID, t.TowerName, tr.TrackID, tr.TrackName
        """),
        ("vw_DailyVolume", """
            SELECT
                CAST(tk.OpenedAt AS DATE) AS TicketDate,
                DATENAME(WEEKDAY, tk.OpenedAt) AS DayOfWeek,
                t.TowerName, tr.TrackName,
                COUNT(*) AS TotalTickets,
                SUM(CASE WHEN tk.TicketType = 'Parent' THEN 1 ELSE 0 END) AS Parents,
                SUM(CASE WHEN tk.TicketType = 'Child' THEN 1 ELSE 0 END) AS Children
            FROM qbr.Ticket tk
            LEFT JOIN qbr.Tower t ON t.TowerID = tk.TowerID
            LEFT JOIN qbr.Track tr ON tr.TrackID = tk.TrackID
            WHERE tk.OpenedAt IS NOT NULL
            GROUP BY CAST(tk.OpenedAt AS DATE), DATENAME(WEEKDAY, tk.OpenedAt), t.TowerName, tr.TrackName
        """),
        ("vw_WeeklyVolume", """
            SELECT
                DATEPART(YEAR, OpenedAt) AS Year,
                DATEPART(WEEK, OpenedAt) AS Week,
                DATEADD(WEEK, DATEDIFF(WEEK, 0, OpenedAt), 0) AS WeekStart,
                COUNT(*) AS TotalTickets,
                SUM(CASE WHEN TicketType = 'Parent' THEN 1 ELSE 0 END) AS Parents,
                SUM(CASE WHEN TicketType = 'Child' THEN 1 ELSE 0 END) AS Children
            FROM qbr.Ticket
            WHERE OpenedAt IS NOT NULL
            GROUP BY DATEPART(YEAR, OpenedAt), DATEPART(WEEK, OpenedAt), DATEADD(WEEK, DATEDIFF(WEEK, 0, OpenedAt), 0)
        """),
        ("vw_MonthlyVolume", """
            SELECT
                YEAR(OpenedAt) AS Year,
                MONTH(OpenedAt) AS Month,
                DATENAME(MONTH, OpenedAt) AS MonthName,
                COUNT(*) AS TotalTickets,
                SUM(CASE WHEN TicketType = 'Parent' THEN 1 ELSE 0 END) AS Parents,
                SUM(CASE WHEN TicketType = 'Child' THEN 1 ELSE 0 END) AS Children
            FROM qbr.Ticket
            WHERE OpenedAt IS NOT NULL
            GROUP BY YEAR(OpenedAt), MONTH(OpenedAt), DATENAME(MONTH, OpenedAt)
        """),
        ("vw_QuarterlyVolume", """
            SELECT
                YEAR(OpenedAt) AS Year,
                DATEPART(QUARTER, OpenedAt) AS Quarter,
                COUNT(*) AS TotalTickets,
                SUM(CASE WHEN TicketType = 'Parent' THEN 1 ELSE 0 END) AS Parents,
                SUM(CASE WHEN TicketType = 'Child' THEN 1 ELSE 0 END) AS Children
            FROM qbr.Ticket
            WHERE OpenedAt IS NOT NULL
            GROUP BY YEAR(OpenedAt), DATEPART(QUARTER, OpenedAt)
        """),
        ("vw_AlertFrequency", """
            SELECT
                a.Part, a.AlertType, a.Severity,
                t.TowerName, tr.TrackName,
                COUNT(*) AS AlertCount
            FROM qbr.Alert a
            LEFT JOIN qbr.Tower t ON t.TowerID = a.TowerID
            LEFT JOIN qbr.Track tr ON tr.TrackID = a.TrackID
            GROUP BY a.Part, a.AlertType, a.Severity, t.TowerName, tr.TrackName
        """),
        ("vw_ParentChildRelation", """
            SELECT
                p.TicketNumber AS ParentTicketNumber,
                t.TowerName, tr.TrackName,
                p.Priority AS ParentPriority,
                p.OpenedAt AS ParentOpened,
                COUNT(c.TicketKey) AS ChildCount
            FROM qbr.Ticket p
            LEFT JOIN qbr.Tower t ON t.TowerID = p.TowerID
            LEFT JOIN qbr.Track tr ON tr.TrackID = p.TrackID
            LEFT JOIN qbr.Ticket c ON c.ParentTicketNumber = p.TicketNumber AND c.TicketType = 'Child'
            WHERE p.TicketType = 'Parent'
            GROUP BY p.TicketNumber, t.TowerName, tr.TrackName, p.Priority, p.OpenedAt
        """),
        ("vw_TowerTrackAlerts", """
            SELECT
                t.TowerName, tr.TrackName,
                COUNT(a.AlertKey) AS TotalAlerts,
                SUM(CASE WHEN a.Severity = 'Critical' THEN 1 ELSE 0 END) AS CriticalAlerts,
                SUM(CASE WHEN a.Severity = 'High' THEN 1 ELSE 0 END) AS HighAlerts,
                SUM(CASE WHEN a.Severity = 'Moderate' THEN 1 ELSE 0 END) AS ModerateAlerts
            FROM qbr.Tower t
            JOIN qbr.Track tr ON tr.TowerID = t.TowerID
            LEFT JOIN qbr.Alert a ON a.TrackID = tr.TrackID
            GROUP BY t.TowerName, tr.TrackName
        """),
    ]
    
    for view_name, view_sql in views:
        try:
            # Drop view if exists
            cursor.execute(f"DROP VIEW IF EXISTS qbr.{view_name}")
            cursor.commit()
            # Create view
            cursor.execute(f"CREATE VIEW qbr.{view_name} AS {view_sql}")
            cursor.commit()
            print(f"  View: {view_name}")
        except Exception as e:
            print(f"  View {view_name}: {e}")

    print("  Analytics views created")
    print()
    print("=" * 50)
    print("DATA SUMMARY")
    print("=" * 50)
    
    tables = [
        ('Towers', 'qbr.Tower'),
        ('Tracks', 'qbr.Track'),
        ('Customers', 'qbr.Customer'),
        ('Tickets', 'qbr.Ticket'),
        ('Alerts', 'qbr.Alert'),
        ('KPIs', 'qbr.DashboardKPI'),
    ]
    
    for name, table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  {name}: {count}")
        except:
            print(f"  {name}: (table not found)")
    
    print("=" * 50)
    print()
    print("Migration completed successfully!")
    print()
    print("Next steps:")
    print("  1. Run: streamlit run app/dashboard.py")
    print("  2. Or load more data: python load_data.py")
    print()

    cursor.close()
    conn.close()


if __name__ == '__main__':
    main()
