/*
 ============================================================
 QBR Dashboard - Seed Data (Towers, Tracks, Customers)
 ============================================================
 Run this after creating the schema to populate reference data.
*/

-- ============================================================
-- 1. INSERT TOWERS
-- ============================================================
SET IDENTITY_INSERT qbr.Tower ON;

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

SET IDENTITY_INSERT qbr.Tower OFF;
GO

-- ============================================================
-- 2. INSERT TRACKS
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
-- 3. INSERT CUSTOMERS
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
-- 4. INSERT DASHBOARD KPI CONFIGURATION
-- ============================================================
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
-- 5. INSERT DASHBOARD FILTER CONFIGURATION
-- ============================================================
MERGE qbr.DashboardFilter AS t
USING (VALUES
    ('Date Range', 'date', 'Last 30 Days'),
    ('Tower', 'tower', 'All'),
    ('Track', 'track', 'All'),
    ('Priority', 'priority', 'All'),
    ('State', 'state', 'All'),
    ('Customer', 'customer', 'All')
) s(FilterName, FilterType, DefaultValue)
ON t.FilterName = s.FilterName
WHEN NOT MATCHED THEN INSERT(FilterName, FilterType, DefaultValue, IsActive)
    VALUES(s.FilterName, s.FilterType, s.DefaultValue, 1);
GO

PRINT 'Seed data inserted successfully!';
PRINT '';
PRINT 'Towers: Collaboration, Security, Foundation, Non-CMS';
PRINT 'Tracks: 15 tracks across all towers';
PRINT 'Customers: 5 customers configured';
PRINT 'KPIs: 12 KPI cards configured';
GO
