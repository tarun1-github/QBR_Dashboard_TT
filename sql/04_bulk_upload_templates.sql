/*
 ============================================================
 QBR Dashboard - Bulk Data Upload Helper
 ============================================================
 Use these templates to upload your own data from Excel/CSV.
 
 INSTRUCTIONS:
 1. Export your ServiceNow data to CSV
 2. Use SQL Server Import Wizard or BULK INSERT
 3. Or use the Python script provided (load_data.py)
 
 TEMPLATES BELOW:
 ============================================================
*/

-- ============================================================
-- TEMPLATE 1: Upload Tickets from Staging Table
-- ============================================================
/*
-- Step 1: Create staging table for bulk import
CREATE TABLE qbr.TicketStaging(
    TicketNumber NVARCHAR(50),
    ParentTicketNumber NVARCHAR(50),
    AssignmentGroup NVARCHAR(150),
    CompanyAccount NVARCHAR(150),
    ConfigurationItem NVARCHAR(255),
    Service NVARCHAR(150),
    Part NVARCHAR(150),
    Priority NVARCHAR(50),
    State NVARCHAR(100),
    Impact NVARCHAR(50),
    ShortDescription NVARCHAR(500),
    OpenedAt NVARCHAR(50),
    CreatedAt NVARCHAR(50),
    UpdatedAt NVARCHAR(50),
    ClosedAt NVARCHAR(50),
    CandidateForVE NVARCHAR(50),
    VETimeSavedMinutes NVARCHAR(50),
    ResolutionCode NVARCHAR(200),
    CauseCode NVARCHAR(200),
    SourceFile NVARCHAR(260)
);

-- Step 2: BULK INSERT from CSV
BULK INSERT qbr.TicketStaging
FROM 'C:\QBR_Data\created_tickets.csv'
WITH (
    FORMAT = 'CSV',
    FIRSTROW = 2,
    FIELDTERMINATOR = ',',
    ROWTERMINATOR = '\n',
    CODEPAGE = '65001'
);

-- Step 3: Transform and insert into main table
DECLARE @BatchID UNIQUEIDENTIFIER = NEWID();

INSERT INTO qbr.Ticket (
    TicketNumber, ParentTicketNumber, TicketType,
    CustomerID, TowerID, TrackID,
    AssignmentGroup, CompanyAccount, ConfigurationItem,
    Service, Part, Priority, State, Impact,
    ShortDescription, OpenedAt, CreatedAt, UpdatedAt, ClosedAt,
    CandidateForVE, VETimeSavedMinutes, ResolutionCode, CauseCode,
    SourceFile, LoadBatchID, LoadedAt
)
SELECT 
    s.TicketNumber,
    NULLIF(s.ParentTicketNumber, ''),
    CASE WHEN s.ParentTicketNumber IS NOT NULL AND s.ParentTicketNumber <> '' THEN 'Child' ELSE 'Parent' END,
    c.CustomerID,
    t.TowerID,
    tr.TrackID,
    s.AssignmentGroup,
    s.CompanyAccount,
    s.ConfigurationItem,
    s.Service,
    s.Part,
    s.Priority,
    s.State,
    s.Impact,
    s.ShortDescription,
    TRY_CONVERT(DATETIME2, s.OpenedAt),
    TRY_CONVERT(DATETIME2, s.CreatedAt),
    TRY_CONVERT(DATETIME2, s.UpdatedAt),
    TRY_CONVERT(DATETIME2, s.ClosedAt),
    s.CandidateForVE,
    TRY_CONVERT(DECIMAL(18,2), s.VETimeSavedMinutes),
    s.ResolutionCode,
    s.CauseCode,
    s.SourceFile,
    @BatchID,
    SYSUTCDATETIME()
FROM qbr.TicketStaging s
LEFT JOIN qbr.Customer c ON c.CustomerName = s.CompanyAccount
LEFT JOIN qbr.Track tr ON tr.TrackName = s.AssignmentGroup
LEFT JOIN qbr.Tower t ON t.TowerID = tr.TowerID;

-- Step 4: Clean up staging
DROP TABLE qbr.TicketStaging;
*/

-- ============================================================
-- TEMPLATE 2: Quick Insert Single Ticket
-- ============================================================
/*
INSERT INTO qbr.Ticket (
    TicketNumber, ParentTicketNumber, TicketType,
    CustomerID, TowerID, TrackID,
    AssignmentGroup, CompanyAccount, ConfigurationItem,
    Service, Part, Priority, State,
    OpenedAt, ClosedAt, SourceFile, LoadBatchID, LoadedAt
)
VALUES (
    'INC999999999999',  -- TicketNumber
    NULL,               -- ParentTicketNumber (NULL for Parent)
    'Parent',           -- TicketType
    1,                  -- CustomerID (1=Dome Depot)
    3,                  -- TowerID (3=Foundation)
    13,                 -- TrackID (13=THD Data)
    'FN-THD-L1',        -- AssignmentGroup
    'Dome Depot',       -- CompanyAccount
    'srv-thd-999',      -- ConfigurationItem
    'Compute',          -- Service
    'Server',           -- Part
    '2 - High',         -- Priority
    'Closed',           -- State
    '2026-07-15 10:00:00',  -- OpenedAt
    '2026-07-15 14:00:00',  -- ClosedAt
    'manual_entry',     -- SourceFile
    NEWID(),            -- LoadBatchID
    SYSUTCDATETIME()    -- LoadedAt
);
*/

-- ============================================================
-- TEMPLATE 3: Update Tower/Track Mapping
-- ============================================================
/*
-- Add new Tower
INSERT INTO qbr.Tower (TowerName, TowerDescription, DisplayOrder, IsActive)
VALUES ('New Tower', 'Description', 5, 1);

-- Add new Track
INSERT INTO qbr.Track (TowerID, TrackName, TrackDescription, DisplayOrder, IsActive)
VALUES (5, 'New Track', 'Description', 1, 1);

-- Update Track mapping
UPDATE qbr.Track SET TowerID = 1 WHERE TrackName = 'SomeTrack';
*/

-- ============================================================
-- TEMPLATE 4: Data Validation Queries
-- ============================================================
/*
-- Check ticket counts by Tower/Track
SELECT 
    t.TowerName,
    tr.TrackName,
    COUNT(*) AS TicketCount,
    SUM(CASE WHEN tk.TicketType = 'Parent' THEN 1 ELSE 0 END) AS Parents,
    SUM(CASE WHEN tk.TicketType = 'Child' THEN 1 ELSE 0 END) AS Children
FROM qbr.Ticket tk
JOIN qbr.Tower t ON t.TowerID = tk.TowerID
JOIN qbr.Track tr ON tr.TrackID = tk.TrackID
GROUP BY t.TowerName, tr.TrackName
ORDER BY TicketCount DESC;

-- Check alerts by Part
SELECT 
    Part,
    COUNT(*) AS AlertCount,
    AlertType,
    Severity
FROM qbr.Alert
GROUP BY Part, AlertType, Severity
ORDER BY AlertCount DESC;

-- Parent-Child relationships
SELECT 
    ParentTicketNumber,
    COUNT(*) AS ChildCount
FROM qbr.Ticket
WHERE TicketType = 'Child'
GROUP BY ParentTicketNumber
ORDER BY ChildCount DESC;
*/

PRINT 'Templates ready. Uncomment and modify as needed.';
GO
