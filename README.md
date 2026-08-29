# QBR Executive Dashboard - DB-Driven Setup Guide

## Overview
This dashboard is designed to be **database-driven**, meaning you can make most changes by updating data in SQL Server rather than modifying Python code.

## Quick Start

### 1. Database Setup
Run the batch file to set up the database:
```
setup_db.bat
```

Or run SQL scripts manually in order:
1. `sql/01_create_qbr_schema_v2.sql` - Creates tables and schema
2. `sql/02_seed_reference_data.sql` - Inserts Towers, Tracks, Customers
3. `sql/03_insert_sample_data.sql` - Inserts sample tickets and alerts
4. `sql/05_analytics_views.sql` - Creates views and stored procedures

### 2. Load Your Own Data
Place Excel files in `app/dataset/` and run:
```
python load_data.py
```

Or use SQL Server Import Wizard with templates in `sql/04_bulk_upload_templates.sql`

### 3. Run the Dashboard
```
streamlit run app/dashboard.py
```

## Database Schema

### Hierarchy
```
Customer
   │
   └── Tower (Collaboration, Security, Foundation, Non-CMS)
         │
         └── Track (BOA EV, HSBC Collab, SFNOC, etc.)
               │
               └── Tickets / Alerts
```

### Key Tables

| Table | Purpose | How to Modify |
|-------|---------|---------------|
| `qbr.Tower` | Tower configuration | INSERT/UPDATE towers |
| `qbr.Track` | Track configuration | INSERT/UPDATE tracks |
| `qbr.Customer` | Customer list | INSERT/UPDATE customers |
| `qbr.Ticket` | Ticket data | Bulk upload from Excel |
| `qbr.Alert` | Alert data | Bulk upload from Excel |
| `qbr.DashboardKPI` | KPI card configuration | INSERT/UPDATE KPIs |
| `qbr.DashboardFilter` | Filter configuration | INSERT/UPDATE filters |

### Analytics Views

| View | Purpose |
|------|---------|
| `qbr.vw_ExecutiveKPI` | Executive KPI summary |
| `qbr.vw_TowerTrackVolume` | Volume by Tower/Track |
| `qbr.vw_DailyVolume` | Daily ticket counts |
| `qbr.vw_WeeklyVolume` | Weekly ticket counts |
| `qbr.vw_MonthlyVolume` | Monthly ticket counts |
| `qbr.vw_QuarterlyVolume` | Quarterly ticket counts |
| `qbr.vw_AlertFrequency` | Alerts by Part/Type |
| `qbr.vw_ParentChildRelation` | Parent-child relationships |
| `qbr.vw_TicketVolumeStats` | Max/min volume statistics |
| `qbr.vw_TowerTrackAlerts` | Alert summary by Tower/Track |

## Making Changes (No Code Required)

### Add a New Tower
```sql
INSERT INTO qbr.Tower (TowerName, TowerDescription, DisplayOrder, IsActive)
VALUES ('New Tower', 'Description', 5, 1);
```

### Add a New Track
```sql
INSERT INTO qbr.Track (TowerID, TrackName, TrackDescription, DisplayOrder, IsActive)
VALUES (5, 'New Track', 'Description', 1, 1);
```

### Add a New Customer
```sql
INSERT INTO qbr.Customer (CustomerName, CustomerCode, IsActive)
VALUES ('New Customer', 'CODE', 1);
```

### Bulk Upload Tickets
Use the Python loader:
```
python load_data.py --file your_tickets.xlsx
```

Or use SQL templates in `sql/04_bulk_upload_templates.sql`

### Modify KPI Cards
```sql
-- Add new KPI
INSERT INTO qbr.DashboardKPI (KPIName, KPICategory, DisplayOrder, Icon, ColorCode, IsActive)
VALUES ('New KPI', 'executive', 13, '🎯', '#FF5733', 1);

-- Deactivate a KPI
UPDATE qbr.DashboardKPI SET IsActive = 0 WHERE KPIName = 'Old KPI';
```

## Dashboard Features

### KPI Cards
- Total Tickets
- Parent/Child Tickets
- Alerts Count
- Max/Min per Day
- Average per Day
- Open/Closed Tickets
- Critical/High Priority

### Trend Analysis
- Daily/Weekly/Monthly/Quarterly views
- Parent vs Child breakdown
- Tower/Track comparison

### Analysis Sections
- Parent-Child relationships
- Alert frequency by Part
- Tower/Track alert summary
- Volume statistics (max/min dates)

### Reports
- CSV download
- Excel download with multiple sheets

## File Structure

```
QBR_Ticket_Alert_Dashboard/
├── app/
│   ├── dashboard.py          # Main Streamlit app
│   ├── dashboard_data.py     # DB data access layer
│   ├── login_block.py        # Authentication UI
│   ├── auth.py               # Authentication logic
│   ├── db.py                 # Database connection
│   ├── config.py             # Configuration
│   └── dataset/              # Excel files for upload
├── sql/
│   ├── 01_create_qbr_schema_v2.sql    # Schema creation
│   ├── 02_seed_reference_data.sql     # Reference data
│   ├── 03_insert_sample_data.sql      # Sample data
│   ├── 04_bulk_upload_templates.sql   # Upload templates
│   └── 05_analytics_views.sql         # Analytics views
├── load_data.py              # Python data loader
├── setup_db.bat              # Database setup batch file
└── requirements.txt          # Python dependencies
```

## Data Flow

```
Excel/CSV Files
      │
      ▼
load_data.py (Python) ──────► qbr.Ticket, qbr.Alert (SQL Server)
                                     │
                                     ▼
                              Analytics Views (SQL Server)
                                     │
                                     ▼
                              dashboard_data.py (Python)
                                     │
                                     ▼
                              dashboard.py (Streamlit)
```

## Support

For issues or questions, check:
1. Database connection in `.env` file
2. SQL Server is accessible
3. All SQL scripts ran successfully
4. Python dependencies installed (`pip install -r requirements.txt`)
