# QBR Executive Dashboard - System Architecture

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    DATA SOURCES                                         │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│   │  Excel Files │    │  CSV Files   │    │  Text Files  │    │  ServiceNow  │          │
│   │   (.xlsx)    │    │   (.csv)     │    │   (.txt)     │    │    (API)     │          │
│   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘    └──────┬───────┘          │
│          │                   │                   │                   │                   │
│          └───────────────────┴───────────────────┴───────────────────┘                   │
│                                      │                                                   │
│                                      ▼                                                   │
│                          ┌───────────────────────┐                                       │
│                          │   app/dataset/        │                                       │
│                          │   (Data Storage)      │                                       │
│                          └───────────────────────┘                                       │
│                                      │                                                   │
└──────────────────────────────────────┼───────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              DATA LOADING LAYER                                         │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│   │                              load_data.py                                       │   │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │   │
│   │  │ File Reader │→ │  Column     │→ │  Data       │→ │  Tower/Track            │ │   │
│   │  │ (xlsx/csv)  │  │  Mapper     │  │  Validator  │  │  Mapper                 │ │   │
│   │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────────┘ │   │
│   └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                                   │
│                                      ▼                                                   │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│   │                              setup_db.py                                        │   │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │   │
│   │  │ Schema      │→ │  Reference  │→ │  Analytics  │→ │  Sample                 │ │   │
│   │  │ Creator     │  │  Data       │  │  Views      │  │  Data                   │ │   │
│   │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────────┘ │   │
│   └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                                   │
└──────────────────────────────────────┼───────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              DATABASE LAYER (SQL Server)                                │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│   │                              qbr Schema                                         │   │
│   │                                                                                 │   │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │   │
│   │  │   Tower     │  │   Track     │  │  Customer   │  │  AppUser                │ │   │
│   │  │   (Ref)     │  │   (Ref)     │  │  (Ref)      │  │  (Auth)                 │ │   │
│   │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────────┘ │   │
│   │                                                                                 │   │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │   │
│   │  │   Ticket    │  │   Alert     │  │ TicketAlert │  │  UserTrackAccess        │ │   │
│   │  │   (Trans)   │  │   (Trans)   │  │  (Ref)      │  │  (Auth)                 │ │   │
│   │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────────┘ │   │
│   │                                                                                 │   │
│   │  ┌─────────────────────────────────────────────────────────────────────────────┐ │   │
│   │  │                         Analytics Views                                      │ │   │
│   │  │  vw_ExecutiveKPI │ vw_TowerTrackVolume │ vw_DailyVolume │ vw_AlertFrequency  │ │   │
│   │  │  vw_WeeklyVolume │ vw_MonthlyVolume    │ vw_Quarterly   │ vw_ParentChild     │ │   │
│   │  └─────────────────────────────────────────────────────────────────────────────┘ │   │
│   └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                                   │
└──────────────────────────────────────┼───────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              APPLICATION LAYER (Python)                                 │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│   │                              app/db.py                                          │   │
│   │                         SQLAlchemy Engine                                       │   │
│   │                    (Connection Pooling + ORM)                                    │   │
│   └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                                   │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│   │                           app/dashboard_data.py                                 │   │
│   │  ┌──────────────────────────────────────────────────────────────────────────┐   │   │
│   │  │                        Data Access Functions                               │   │   │
│   │  │  get_executive_kpis() │ get_tower_track_volume() │ get_daily_trend()       │   │   │
│   │  │  get_weekly_trend()   │ get_monthly_trend()      │ get_quarterly_trend()   │   │   │
│   │  │  get_alert_frequency()│ get_parent_child()       │ get_volume_stats()      │   │   │
│   │  └──────────────────────────────────────────────────────────────────────────┘   │   │
│   └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                                   │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│   │                           app/auth.py                                           │   │
│   │  ┌──────────────────────────────────────────────────────────────────────────┐   │   │
│   │  │                        Authentication Functions                            │   │   │
│   │  │  get_user() │ verify_password() │ hash_password() │ set_password()        │   │   │
│   │  │  change_password() │ reset_password() │ record_failed_login()             │   │   │
│   │  └──────────────────────────────────────────────────────────────────────────┘   │   │
│   └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                                   │
└──────────────────────────────────────┼───────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              PRESENTATION LAYER (Streamlit)                             │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│   │                           app/dashboard.py                                      │   │
│   │                                                                                 │   │
│   │  ┌──────────────────────────────────────────────────────────────────────────┐   │   │
│   │  │                        Sidebar Navigation                                 │   │   │
│   │  │  [Tower Selection] → [Track Selection] → [Time View] → [Date Range]       │   │   │
│   │  └──────────────────────────────────────────────────────────────────────────┘   │   │
│   │                                                                                 │   │
│   │  ┌──────────────────────────────────────────────────────────────────────────┐   │   │
│   │  │                        Dashboard Sections                                 │   │   │
│   │  │  ┌────────────────────────────────────────────────────────────────────┐  │   │   │
│   │  │  │ 📈 Executive KPIs (3D Cards)                                       │  │   │   │
│   │  │  │ Total │ Parents │ Children │ Alerts │ Max/Min │ Avg │ Open │ Closed│  │   │   │
│   │  │  └────────────────────────────────────────────────────────────────────┘  │   │   │
│   │  │  ┌────────────────────────────────────────────────────────────────────┐  │   │   │
│   │  │  │ 📊 Trend Analysis (Plotly Charts)                                  │  │   │   │
│   │  │  │ Ticket Volume Trend │ Tower/Track Volume                          │  │   │   │
│   │  │  └────────────────────────────────────────────────────────────────────┘  │   │   │   │
│   │  │  ┌────────────────────────────────────────────────────────────────────┐  │   │   │
│   │  │  │ 👑 Parent-Child Analysis │ ⚡ Alert Frequency                     │  │   │   │
│   │  │  └────────────────────────────────────────────────────────────────────┘  │   │   │   │
│   │  │  ┌────────────────────────────────────────────────────────────────────┐  │   │   │
│   │  │  │ 📋 Tower/Track Alert Summary                                       │  │   │   │
│   │  │  └────────────────────────────────────────────────────────────────────┘  │   │   │   │
│   │  │  ┌────────────────────────────────────────────────────────────────────┐  │   │   │
│   │  │  │ 📥 Customer Report (CSV/Excel Download)                            │  │   │   │
│   │  │  └────────────────────────────────────────────────────────────────────┘  │   │   │   │
│   │  └──────────────────────────────────────────────────────────────────────────┘   │   │
│   └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                                   │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│   │                           app/login_block.py                                    │   │
│   │  ┌──────────────────────────────────────────────────────────────────────────┐   │   │
│   │  │                        Authentication UI                                   │   │   │
│   │  │  Login │ Set Password │ Forgot Password │ Change Password                 │   │   │
│   │  └──────────────────────────────────────────────────────────────────────────┘   │   │
│   └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

## Component Descriptions

### 1. Data Sources Layer
| Component | Description |
|-----------|-------------|
| Excel Files | Primary data format (.xlsx) from ServiceNow exports |
| CSV Files | Alternative format for ticket data |
| Text Files | Tab or comma-separated data files |
| ServiceNow API | Future integration point for direct data fetch |

### 2. Data Loading Layer
| Component | Description |
|-----------|-------------|
| load_data.py | Main data ingestion script |
| File Reader | Supports xlsx, csv, txt formats |
| Column Mapper | Flexible column name detection |
| Data Validator | Validates and cleans data |
| Tower/Track Mapper | Maps assignment groups to tracks |

### 3. Database Layer
| Component | Description |
|-----------|-------------|
| qbr.Tower | Tower reference data |
| qbr.Track | Track reference data |
| qbr.Customer | Customer reference data |
| qbr.Ticket | Transactional ticket data |
| qbr.Alert | Transactional alert data |
| qbr.AppUser | User authentication data |
| Analytics Views | Pre-built views for dashboard queries |

### 4. Application Layer
| Component | Description |
|-----------|-------------|
| app/db.py | Database connection and session management |
| app/dashboard_data.py | Data access layer for dashboard |
| app/auth.py | Authentication and authorization logic |

### 5. Presentation Layer
| Component | Description |
|-----------|-------------|
| app/dashboard.py | Main Streamlit dashboard application |
| app/login_block.py | Authentication UI components |

## Data Flow

```
1. Data Ingestion:
   Files → load_data.py → Data Validation → SQL Server

2. Dashboard Query:
   User Filter → dashboard.py → dashboard_data.py → SQL Server → Results

3. Authentication:
   Login → login_block.py → auth.py → SQL User Table → Session

4. Report Generation:
   Dashboard → User Click → Excel/CSV Export → Download
```

## Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | Streamlit, Plotly, HTML/CSS |
| Backend | Python 3.13, SQLAlchemy, Pandas |
| Database | SQL Server (pyodbc) |
| Authentication | PBKDF2-SHA256, Session-based |
| Data Format | Excel, CSV, TXT |

## Security Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Security Layers                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Network: SQL Server with TrustServerCertificate         │
│  2. Authentication: PBKDF2-SHA256 password hashing          │
│  3. Session: Streamlit session state management             │
│  4. Authorization: Role-based access (SUPERUSER/MANAGER)    │
│  5. Audit: Login attempts tracking, password audit          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Deployment Options                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Local:                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │  Streamlit  │───▶│   Python    │───▶│ SQL Server  │     │
│  │   Server    │    │   Backend   │    │  (Local)    │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│                                                             │
│  Cloud (Future):                                            │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   Azure     │───▶│  Container  │───▶│  Azure SQL  │     │
│  │   Web App   │    │   Instance  │    │  Database   │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```
