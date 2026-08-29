"""Check THD Data in database."""
import pyodbc
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

print("=" * 60)
print("THD DATA TICKET DETAILS")
print("=" * 60)

cursor.execute('''
    SELECT 
        TicketNumber, 
        ParentTicketNumber,
        TicketType,
        Priority,
        State,
        OpenedAt,
        ClosedAt,
        AssignmentGroup,
        CompanyAccount,
        ConfigurationItem
    FROM qbr.Ticket 
    WHERE TrackID = (SELECT TrackID FROM qbr.Track WHERE TrackName = 'THD Data')
    ORDER BY OpenedAt
''')

tickets = cursor.fetchall()
print(f"\nTotal THD Data Tickets: {len(tickets)}")
print()

for i, row in enumerate(tickets, 1):
    ci = row[9][:50] if row[9] else "N/A"
    print(f"{i}. {row[0]}")
    print(f"   Type: {row[2]} | Priority: {row[3]} | State: {row[4]}")
    print(f"   Opened: {row[5]} | Closed: {row[6]}")
    print(f"   Assignment: {row[7]} | Company: {row[8]}")
    print(f"   CI: {ci}...")
    print()

print("=" * 60)
print("THD DATA ALERT DETAILS")
print("=" * 60)

cursor.execute('''
    SELECT 
        AlertID,
        Part,
        AlertType,
        Severity,
        AlertTime
    FROM qbr.Alert 
    WHERE TrackID = (SELECT TrackID FROM qbr.Track WHERE TrackName = 'THD Data')
    ORDER BY AlertTime
''')

alerts = cursor.fetchall()
print(f"\nTotal THD Data Alerts: {len(alerts)}")
print()

for i, row in enumerate(alerts, 1):
    print(f"{i}. {row[0]}")
    print(f"   Part: {row[1]} | Type: {row[2]} | Severity: {row[3]}")
    print(f"   Time: {row[4]}")
    print()

cursor.close()
conn.close()
