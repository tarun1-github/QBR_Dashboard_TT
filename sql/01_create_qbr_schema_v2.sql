/*
 ============================================================
 QBR Executive Dashboard - Complete Database Schema
 ============================================================
 This script creates the complete schema for the QBR Ticket
 & Alert Analytics dashboard. Run this once to set up the DB.
 
 Hierarchy: Customer > Tower > Track > Tickets/Alerts
 ============================================================
*/

-- Create schema if not exists
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name='qbr') EXEC('CREATE SCHEMA qbr');
GO

-- ============================================================
-- 1. TOWER & TRACK CONFIGURATION
--    Modify this table to add/change towers and tracks
-- ============================================================
IF OBJECT_ID('qbr.Tower','U') IS NULL
CREATE TABLE qbr.Tower(
    TowerID INT IDENTITY PRIMARY KEY,
    TowerName NVARCHAR(100) NOT NULL UNIQUE,
    TowerDescription NVARCHAR(500) NULL,
    DisplayOrder INT NOT NULL DEFAULT 0,
    IsActive BIT NOT NULL DEFAULT 1,
    CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

IF OBJECT_ID('qbr.Track','U') IS NULL
CREATE TABLE qbr.Track(
    TrackID INT IDENTITY PRIMARY KEY,
    TowerID INT NOT NULL FOREIGN KEY REFERENCES qbr.Tower(TowerID),
    TrackName NVARCHAR(100) NOT NULL,
    TrackDescription NVARCHAR(500) NULL,
    DisplayOrder INT NOT NULL DEFAULT 0,
    IsActive BIT NOT NULL DEFAULT 1,
    CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT UQ_TowerTrack UNIQUE(TowerID, TrackName)
);
GO

-- ============================================================
-- 2. CUSTOMER CONFIGURATION
-- ============================================================
IF OBJECT_ID('qbr.Customer','U') IS NULL
CREATE TABLE qbr.Customer(
    CustomerID INT IDENTITY PRIMARY KEY,
    CustomerName NVARCHAR(200) NOT NULL UNIQUE,
    CustomerCode NVARCHAR(50) NULL,
    IsActive BIT NOT NULL DEFAULT 1,
    CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

-- ============================================================
-- 3. TICKET DATA (from ServiceNow)
-- ============================================================
IF OBJECT_ID('qbr.Ticket','U') IS NULL
CREATE TABLE qbr.Ticket(
    TicketKey BIGINT IDENTITY PRIMARY KEY,
    TicketNumber NVARCHAR(50) NOT NULL UNIQUE,
    ParentTicketNumber NVARCHAR(50) NULL,
    TicketType NVARCHAR(20) NULL,  -- 'Parent' or 'Child'
    
    -- Hierarchy
    CustomerID INT NULL FOREIGN KEY REFERENCES qbr.Customer(CustomerID),
    TowerID INT NULL FOREIGN KEY REFERENCES qbr.Tower(TowerID),
    TrackID INT NULL FOREIGN KEY REFERENCES qbr.Track(TrackID),
    
    -- ServiceNow Fields
    AssignmentGroup NVARCHAR(150) NULL,
    CompanyAccount NVARCHAR(150) NULL,
    ConfigurationItem NVARCHAR(255) NULL,
    Service NVARCHAR(150) NULL,
    Part NVARCHAR(150) NULL,
    Priority NVARCHAR(50) NULL,
    State NVARCHAR(100) NULL,
    Impact NVARCHAR(50) NULL,
    ShortDescription NVARCHAR(500) NULL,
    
    -- Timestamps
    OpenedAt DATETIME2 NULL,
    CreatedAt DATETIME2 NULL,
    UpdatedAt DATETIME2 NULL,
    ClosedAt DATETIME2 NULL,
    
    -- Metrics
    CandidateForVE NVARCHAR(50) NULL,
    VETimeSavedMinutes DECIMAL(18,2) NULL,
    ResolutionCode NVARCHAR(200) NULL,
    CauseCode NVARCHAR(200) NULL,
    
    -- Audit
    SourceFile NVARCHAR(260) NULL,
    LoadBatchID UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID(),
    LoadedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

-- ============================================================
-- 4. ALERT DATA (from Monitoring Tools)
-- ============================================================
IF OBJECT_ID('qbr.Alert','U') IS NULL
CREATE TABLE qbr.Alert(
    AlertKey BIGINT IDENTITY PRIMARY KEY,
    AlertID NVARCHAR(100) NOT NULL UNIQUE,
    TicketNumber NVARCHAR(50) NULL,  -- Linked ticket if any
    
    -- Hierarchy
    CustomerID INT NULL FOREIGN KEY REFERENCES qbr.Customer(CustomerID),
    TowerID INT NULL FOREIGN KEY REFERENCES qbr.Tower(TowerID),
    TrackID INT NULL FOREIGN KEY REFERENCES qbr.Track(TrackID),
    
    -- Alert Details
    AlertTime DATETIME2 NOT NULL,
    Service NVARCHAR(150) NULL,
    Part NVARCHAR(150) NULL,
    AlertType NVARCHAR(200) NULL,
    Severity NVARCHAR(50) NULL,
    MonitoringTool NVARCHAR(100) NOT NULL DEFAULT 'NZG2',
    AlertDescription NVARCHAR(500) NULL,
    
    -- Audit
    SourceFile NVARCHAR(260) NULL,
    LoadBatchID UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID(),
    LoadedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

-- ============================================================
-- 5. TICKET-ALERT CORRELATION
-- ============================================================
IF OBJECT_ID('qbr.TicketAlert','U') IS NULL
CREATE TABLE qbr.TicketAlert(
    TicketAlertKey BIGINT IDENTITY PRIMARY KEY,
    TicketNumber NVARCHAR(50) NOT NULL,
    AlertID NVARCHAR(100) NOT NULL,
    RelationshipType NVARCHAR(100) NULL,
    CorrelationMethod NVARCHAR(100) NULL,
    CorrelationConfidence DECIMAL(5,2) NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT UQ_TicketAlert UNIQUE(TicketNumber,AlertID)
);
GO

-- ============================================================
-- 6. USER MANAGEMENT
-- ============================================================
IF OBJECT_ID('qbr.AppUser','U') IS NULL
CREATE TABLE qbr.AppUser(
    UserID INT IDENTITY PRIMARY KEY,
    Username NVARCHAR(150) NOT NULL UNIQUE,
    DisplayName NVARCHAR(200),
    PasswordHash NVARCHAR(500) NOT NULL,
    RoleName NVARCHAR(50) NOT NULL,  -- SUPERUSER, SUPERVISOR, MANAGER
    MustSetPassword BIT NOT NULL DEFAULT 1,
    IsActive BIT NOT NULL DEFAULT 1,
    FailedLoginCount INT NOT NULL DEFAULT 0,
    LockedUntil DATETIME2 NULL,
    ManagerUserID INT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

IF OBJECT_ID('qbr.UserTrackAccess','U') IS NULL
CREATE TABLE qbr.UserTrackAccess(
    UserTrackAccessID INT IDENTITY PRIMARY KEY,
    UserID INT NOT NULL FOREIGN KEY REFERENCES qbr.AppUser(UserID),
    TrackID INT NOT NULL FOREIGN KEY REFERENCES qbr.Track(TrackID),
    CanView BIT NOT NULL DEFAULT 1,
    CanExport BIT NOT NULL DEFAULT 0,
    CanManage BIT NOT NULL DEFAULT 0,
    CONSTRAINT UQ_UserTrack UNIQUE(UserID,TrackID)
);
GO

-- ============================================================
-- 7. DASHBOARD CONFIGURATION (DB-Driven)
--    Modify these tables to change dashboard behavior
-- ============================================================
IF OBJECT_ID('qbr.DashboardKPI','U') IS NULL
CREATE TABLE qbr.DashboardKPI(
    KPIID INT IDENTITY PRIMARY KEY,
    KPIName NVARCHAR(100) NOT NULL,
    KPICategory NVARCHAR(50) NOT NULL,  -- 'executive', 'tower', 'track', 'alert'
    DisplayOrder INT NOT NULL DEFAULT 0,
    Icon NVARCHAR(10) NULL,
    ColorCode NVARCHAR(20) NULL,
    IsActive BIT NOT NULL DEFAULT 1,
    CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

IF OBJECT_ID('qbr.DashboardFilter','U') IS NULL
CREATE TABLE qbr.DashboardFilter(
    FilterID INT IDENTITY PRIMARY KEY,
    FilterName NVARCHAR(100) NOT NULL,
    FilterType NVARCHAR(50) NOT NULL,  -- 'date', 'tower', 'track', 'priority', 'state'
    DefaultValue NVARCHAR(200) NULL,
    IsActive BIT NOT NULL DEFAULT 1,
    CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

-- ============================================================
-- 8. DATA LOAD AUDIT
-- ============================================================
IF OBJECT_ID('qbr.RefreshLog','U') IS NULL
CREATE TABLE qbr.RefreshLog(
    RefreshID BIGINT IDENTITY PRIMARY KEY,
    LoadBatchID UNIQUEIDENTIFIER NOT NULL,
    SourceName NVARCHAR(100) NOT NULL,
    StartedAt DATETIME2 NOT NULL,
    FinishedAt DATETIME2 NULL,
    RowsRead INT NULL,
    RowsLoaded INT NULL,
    Status NVARCHAR(30) NOT NULL,
    ErrorMessage NVARCHAR(MAX) NULL
);
GO

-- ============================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================
CREATE INDEX IX_Ticket_TowerTrackDate ON qbr.Ticket(TowerID, TrackID, OpenedAt);
CREATE INDEX IX_Ticket_Parent ON qbr.Ticket(ParentTicketNumber);
CREATE INDEX IX_Ticket_OpenedAt ON qbr.Ticket(OpenedAt);
CREATE INDEX IX_Ticket_ClosedAt ON qbr.Ticket(ClosedAt);
CREATE INDEX IX_Ticket_Customer ON qbr.Ticket(CustomerID);
CREATE INDEX IX_Alert_TowerTrackTime ON qbr.Alert(TowerID, TrackID, AlertTime);
CREATE INDEX IX_Alert_Ticket ON qbr.Alert(TicketNumber);
CREATE INDEX IX_TicketAlert_Ticket ON qbr.TicketAlert(TicketNumber);
CREATE INDEX IX_TicketAlert_Alert ON qbr.TicketAlert(AlertID);
GO

PRINT 'QBR Dashboard schema created successfully!';
GO
