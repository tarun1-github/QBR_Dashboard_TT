"""Add sample alerts for THD Data track."""
import pyodbc
import uuid
from app.config import DATABASE_SERVER, DATABASE_NAME, DATABASE_USER, DB_PASSWORD, DB_DRIVER

connection_string = (
    f"DRIVER={{{DB_DRIVER}}};"
    f"SERVER={DATABASE_SERVER};"
    f"DATABASE={DATABASE_NAME};"
    f"UID={DATABASE_USER};"
    f"PWD={DB_PASSWORD};"
    "TrustServerCertificate=yes;"
)

conn = pyodbc.connect(connection_string)
cursor = conn.cursor()

# Get THD Data track ID
cursor.execute("SELECT TrackID FROM qbr.Track WHERE TrackName = 'THD Data'")
track_id = cursor.fetchone()[0]

# Get Foundation tower ID
cursor.execute("SELECT TowerID FROM qbr.Tower WHERE TowerName = 'Foundation'")
tower_id = cursor.fetchone()[0]

# Get a customer ID
cursor.execute("SELECT TOP 1 CustomerID FROM qbr.Customer")
customer_id = cursor.fetchone()[0]

# Insert sample alerts for THD Data
alerts = [
    ('ALT-THD-001', 'WLC', 'AP_JOIN_DISJOIN', 'Moderate', '2026-07-30 22:46:00'),
    ('ALT-THD-002', 'WLC', 'DEVICE_UNREACHABLE', 'High', '2026-07-30 22:47:00'),
    ('ALT-THD-003', 'Access Point', 'AP_DISCONNECT', 'Moderate', '2026-07-30 22:48:00'),
    ('ALT-THD-004', 'Switch', 'CONFIG_CHANGE', 'Low', '2026-07-30 22:48:00'),
    ('ALT-THD-005', 'SDWAN', 'SITE_DOWN', 'Critical', '2026-07-30 22:20:00'),
    ('ALT-THD-006', 'Aggregator', 'LINK_DOWN', 'High', '2026-07-30 22:48:00'),
]

batch_id = str(uuid.uuid4())
for alert in alerts:
    alert_id, part, alert_type, severity, alert_time = alert
    try:
        cursor.execute('''
            INSERT INTO qbr.Alert (AlertID, TowerID, TrackID, Part, AlertType, Severity, AlertTime, 
                                   CustomerID, MonitoringTool, SourceFile, LoadBatchID, LoadedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'NZG2', 'sample', ?, SYSUTCDATETIME())
        ''', (alert_id, tower_id, track_id, part, alert_type, severity, alert_time, customer_id, batch_id))
        print(f"  Added: {alert_id}")
    except Exception as e:
        print(f"  Error: {e}")

conn.commit()

# Verify
cursor.execute('SELECT COUNT(*) FROM qbr.Alert WHERE TrackID = ?', (track_id,))
print(f'\nAlerts for THD Data: {cursor.fetchone()[0]}')

cursor.close()
conn.close()
