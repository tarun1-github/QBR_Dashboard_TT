/*
 ============================================================
 QBR Dashboard - Schema Migration Script
 ============================================================
 This script migrates from the old schema to the new DB-driven schema.
 Run this if you have existing data in the old schema.
*/

-- ============================================================
-- Step 1: Create new Tower table
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Tower' AND schema_id = SCHEMA_ID('qbr'))
CREATE TABLE qbr.Tower(
    TowerID INT IDENTITY PRIMARY KEY,
    TowerName NVARCHAR(100) NOT NULL UNIQUE,
    TowerDescription NVARCHAR(500) NULL,
    DisplayOrder INT NOT NULL DEFAULT 0,
    IsActive BIT NOT NULL DEFAULT 1,
    CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

-- ============================================================
-- Step 2: Create new Track table
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Track' AND schema_id = SCHEMA_ID('qbr'))
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
-- Step 3: Create new Customer table
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Customer' AND schema_id = SCHEMA_ID('qbr'))
CREATE TABLE qbr.Customer(
    CustomerID INT IDENTITY PRIMARY KEY,
    CustomerName NVARCHAR(200) NOT NULL UNIQUE,
    CustomerCode NVARCHAR(50) NULL,
    IsActive BIT NOT NULL DEFAULT 1,
    CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

-- ============================================================
-- Step 4: Populate Towers
-- ============================================================
SET IDENTITY_INSERT qbr.Tower ON;

INSERT INTO qbr.Tower (TowerID, TowerName, TowerDescription, DisplayOrder, IsActive)
VALUES
    (1, 'Collaboration', 'Collaboration Services Tower', 1, 1),
    (2, 'Security', 'Security Operations Tower', 2, 1),
    (3, 'Foundation', 'Foundation & Data Tower', 3, 1),
    (4, 'Non-CMS', 'Non-CMS Services Tower', 4, 1)
ON CONFLICT (TowerName) DO NOTHING;

SET IDENTITY_INSERT qbr.Tower OFF;
GO

-- SQL Server MERGE alternative for Tower
MERGE qbr.Tower AS t
USING (VALUES
    (1, 'Collaboration', 'Collaboration Services Tower', 1),
    (2, 'Security', 'Security Operations Tower', 2),
    (3, 'Foundation', 'Foundation & Data Tower', 3),
    (4, 'Non-CMS', 'Non-CMS Services Tower', 4)
) s(TowerID, TowerName, TowerDescription, DisplayOrder)
ON t.TowerID = s.TowerID
WHEN NOT MATCHED THEN INSERT(TowerID, TowerName, TowerDescription, DisplayOrder, IsActive)
    VALUES(s.TowerID, s.TowerName, s.TowerDescription, s.DisplayOrder, 1)
WHEN MATCHED THEN UPDATE SET
    TowerName = s.TowerName,
    TowerDescription = s.TowerDescription,
    DisplayOrder = s.DisplayOrder;
GO

-- ============================================================
-- Step 5: Populate Tracks
-- ============================================================
SET IDENTITY_INSERT qbr.Track ON;

MERGE qbr.Track AS t
USING (VALUES
    -- Collaboration Tower (TowerID = 1)
    (1, 1, 'BOA EV', 'BOA EV Services', 1),
    (2, 1, 'HSBC Collab', 'HSBC Collaboration', 2),
    (3, 1, 'Problem Management', 'Problem Management', 3),
    (4, 1, 'BOA TP', 'BOA TP Services', 4),
    (5, 1, 'GTM TP', 'GTM TP Services', 5),
    (6, 1, 'HD Voice (Bgl)', 'HD Voice Bangalore', 6),
    (7, 1, 'SCNOC', 'SCNOC Services', 7),
    
    -- Security Tower (TowerID = 2)
    (8, 2, 'Cybersecurity', 'Cybersecurity Operations', 1),
    (9, 2, 'DC-ACI', 'Data Center ACI', 2),
    (10, 2, 'Infra', 'Infrastructure Security', 3),
    (11, 2, 'SOC', 'Security Operations Center', 4),
    
    -- Foundation Tower (TowerID = 3)
    (12, 3, 'SFNOC', 'SFNOC Operations', 1),
    (13, 3, 'THD Data', 'THD Data Services', 2),
    (14, 3, 'HSBC Data', 'HSBC Data Services', 3),
    
    -- Non-CMS Tower (TowerID = 4)
    (15, 4, 'RIL', 'RIL Services', 1)
) s(TrackID, TowerID, TrackName, TrackDescription, DisplayOrder)
ON t.TrackID = s.TrackID
WHEN NOT MATCHED THEN INSERT(TrackID, TowerID, TrackName, TrackDescription, DisplayOrder, IsActive)
    VALUES(s.TrackID, s.TowerID, s.TrackName, s.TrackDescription, s.DisplayOrder, 1)
WHEN MATCHED THEN UPDATE SET
    TrackName = s.TrackName,
    TrackDescription = s.TrackDescription,
    DisplayOrder = s.DisplayOrder;

SET IDENTITY_INSERT qbr.Track OFF;
GO

-- ============================================================
-- Step 6: Populate Customers
-- ============================================================
MERGE qbr.Customer AS t
USING (VALUES
    ('Dome Depot', 'DOME', 1),
    ('Jio Platforms', 'JIO', 1),
    ('HSBC', 'HSBC', 1),
    ('Bank of America', 'BOA', 1),
    ('Reliance', 'RIL', 1)
) s(CustomerName, CustomerCode, IsActive)
ON t.CustomerName = s.CustomerName
WHEN NOT MATCHED THEN INSERT(CustomerName, CustomerCode, IsActive)
    VALUES(s.CustomerName, s.CustomerCode, s.IsActive);
GO

-- ============================================================
-- Step 7: Add new columns to Ticket table (if not exist)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE name = 'CustomerID' AND object_id = OBJECT_ID('qbr.Ticket'))
    ALTER TABLE qbr.Ticket ADD CustomerID INT NULL FOREIGN KEY REFERENCES qbr.Customer(CustomerID);
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE name = 'TowerID' AND object_id = OBJECT_ID('qbr.Ticket'))
    ALTER TABLE qbr.Ticket ADD TowerID INT NULL FOREIGN KEY REFERENCES qbr.Tower(TowerID);
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE name = 'TrackID' AND object_id = OBJECT_ID('qbr.Ticket'))
    ALTER TABLE qbr.Ticket ADD TrackID INT NULL FOREIGN KEY REFERENCES qbr.Track(TrackID);
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE name = 'Impact' AND object_id = OBJECT_ID('qbr.Ticket'))
    ALTER TABLE qbr.Ticket ADD Impact NVARCHAR(50) NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE name = 'ShortDescription' AND object_id = OBJECT_ID('qbr.Ticket'))
    ALTER TABLE qbr.Ticket ADD ShortDescription NVARCHAR(500) NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE name = 'ResolutionCode' AND object_id = OBJECT_ID('qbr.Ticket'))
    ALTER TABLE qbr.Ticket ADD ResolutionCode NVARCHAR(200) NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE name = 'CauseCode' AND object_id = OBJECT_ID('qbr.Ticket'))
    ALTER TABLE qbr.Ticket ADD CauseCode NVARCHAR(200) NULL;
GO

-- ============================================================
-- Step 8: Add new columns to Alert table (if not exist)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE name = 'CustomerID' AND object_id = OBJECT_ID('qbr.Alert'))
    ALTER TABLE qbr.Alert ADD CustomerID INT NULL FOREIGN KEY REFERENCES qbr.Customer(CustomerID);
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE name = 'TowerID' AND object_id = OBJECT_ID('qbr.Alert'))
    ALTER TABLE qbr.Alert ADD TowerID INT NULL FOREIGN KEY REFERENCES qbr.Tower(TowerID);
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE name = 'TrackID' AND object_id = OBJECT_ID('qbr.Alert'))
    ALTER TABLE qbr.Alert ADD TrackID INT NULL FOREIGN KEY REFERENCES qbr.Track(TrackID);
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE name = 'AlertDescription' AND object_id = OBJECT_ID('qbr.Alert'))
    ALTER TABLE qbr.Alert ADD AlertDescription NVARCHAR(500) NULL;
GO

-- ============================================================
-- Step 9: Create DashboardKPI table
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'DashboardKPI' AND schema_id = SCHEMA_ID('qbr'))
CREATE TABLE qbr.DashboardKPI(
    KPIID INT IDENTITY PRIMARY KEY,
    KPIName NVARCHAR(100) NOT NULL,
    KPICategory NVARCHAR(50) NOT NULL,
    DisplayOrder INT NOT NULL DEFAULT 0,
    Icon NVARCHAR(10) NULL,
    ColorCode NVARCHAR(20) NULL,
    IsActive BIT NOT NULL DEFAULT 1,
    CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

-- Insert KPIs
MERGE qbr.DashboardKPI AS t
USING (VALUES
    ('Total Tickets', 'executive', 1, '🎫', '#19708b'),
    ('Parent Tickets', 'executive', 2, '👑', '#5b8f3b'),
    ('Child Tickets', 'executive', 3, '↳', '#ee8233'),
    ('Alerts', 'executive', 4, '⚡', '#c91414'),
    ('Max/Min Per Day', 'executive', 5, '📊', '#8a6b09'),
    ('Avg Tickets/Day', 'executive', 6, '📈', '#2d7d9a'),
    ('Open Tickets', 'status', 7, '🔵', '#1e88e5'),
    ('Closed Tickets', 'status', 8, '✅', '#43a047'),
    ('Pending Tickets', 'status', 9, '⏳', '#fb8c00'),
    ('Critical Priority', 'priority', 10, '🔴', '#d32f2f'),
    ('High Priority', 'priority', 11, '🟠', '#f57c00'),
    ('Moderate Priority', 'priority', 12, '🟡', '#fbc02d')
) s(KPIName, KPICategory, DisplayOrder, Icon, ColorCode)
ON t.KPIName = s.KPIName
WHEN NOT MATCHED THEN INSERT(KPIName, KPICategory, DisplayOrder, Icon, ColorCode, IsActive)
    VALUES(s.KPIName, s.KPICategory, s.DisplayOrder, s.Icon, s.ColorCode, 1);
GO

-- ============================================================
-- Step 10: Update existing Tickets with Tower/Track IDs
-- ============================================================
UPDATE t
SET t.TowerID = tr.TowerID,
    t.TrackID = tr.TrackID
FROM qbr.Ticket t
JOIN qbr.Track tr ON t.ProjectName = tr.TrackName
WHERE t.TowerID IS NULL;
GO

PRINT 'Migration completed successfully!';
PRINT '';
PRINT 'New tables created: Tower, Track, Customer, DashboardKPI';
PRINT 'Columns added to Ticket: CustomerID, TowerID, TrackID, Impact, ShortDescription, ResolutionCode, CauseCode';
PRINT 'Columns added to Alert: CustomerID, TowerID, TrackID, AlertDescription';
GO
