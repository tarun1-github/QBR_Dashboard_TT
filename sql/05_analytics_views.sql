/*
 ============================================================
 QBR Dashboard - Analytics Views & Stored Procedures
 ============================================================
 These views provide the data for the dashboard KPIs and charts.
*/

-- ============================================================
-- VIEW 1: Executive KPI Summary
-- ============================================================
CREATE OR ALTER VIEW qbr.vw_ExecutiveKPI AS
SELECT
    (SELECT COUNT(*) FROM qbr.Ticket WHERE OpenedAt IS NOT NULL) AS TotalTickets,
    (SELECT COUNT(*) FROM qbr.Ticket WHERE TicketType = 'Parent') AS ParentTickets,
    (SELECT COUNT(*) FROM qbr.Ticket WHERE TicketType = 'Child') AS ChildTickets,
    (SELECT COUNT(*) FROM qbr.Alert) AS TotalAlerts,
    (SELECT COUNT(*) FROM qbr.Ticket WHERE State = 'Open' OR ClosedAt IS NULL) AS OpenTickets,
    (SELECT COUNT(*) FROM qbr.Ticket WHERE State = 'Closed' AND ClosedAt IS NOT NULL) AS ClosedTickets,
    (SELECT COUNT(*) FROM qbr.Ticket WHERE Priority = '1 - Critical') AS CriticalTickets,
    (SELECT COUNT(*) FROM qbr.Ticket WHERE Priority = '2 - High') AS HighTickets,
    (SELECT COUNT(*) FROM qbr.Ticket WHERE Priority = '3 - Moderate') AS ModerateTickets,
    (SELECT COUNT(DISTINCT TowerID) FROM qbr.Ticket WHERE TowerID IS NOT NULL) AS ActiveTowers,
    (SELECT COUNT(DISTINCT TrackID) FROM qbr.Ticket WHERE TrackID IS NOT NULL) AS ActiveTracks,
    (SELECT MIN(OpenedAt) FROM qbr.Ticket) AS EarliestTicket,
    (SELECT MAX(OpenedAt) FROM qbr.Ticket) AS LatestTicket;
GO

-- ============================================================
-- VIEW 2: Tower/Track Volume Summary
-- ============================================================
CREATE OR ALTER VIEW qbr.vw_TowerTrackVolume AS
SELECT
    t.TowerID,
    t.TowerName,
    tr.TrackID,
    tr.TrackName,
    COUNT(tk.TicketKey) AS TotalTickets,
    SUM(CASE WHEN tk.TicketType = 'Parent' THEN 1 ELSE 0 END) AS ParentTickets,
    SUM(CASE WHEN tk.TicketType = 'Child' THEN 1 ELSE 0 END) AS ChildTickets,
    SUM(CASE WHEN tk.Priority = '1 - Critical' THEN 1 ELSE 0 END) AS CriticalTickets,
    SUM(CASE WHEN tk.Priority = '2 - High' THEN 1 ELSE 0 END) AS HighTickets,
    SUM(CASE WHEN tk.State = 'Closed' THEN 1 ELSE 0 END) AS ClosedTickets,
    SUM(CASE WHEN tk.State = 'Open' OR tk.ClosedAt IS NULL THEN 1 ELSE 0 END) AS OpenTickets,
    COUNT(DISTINCT tk.Part) AS UniqueParts,
    ISNULL(SUM(tk.VETimeSavedMinutes), 0) AS TotalVEMinutes
FROM qbr.Tower t
JOIN qbr.Track tr ON tr.TowerID = t.TowerID
LEFT JOIN qbr.Ticket tk ON tk.TrackID = tr.TrackID
GROUP BY t.TowerID, t.TowerName, tr.TrackID, tr.TrackName;
GO

-- ============================================================
-- VIEW 3: Daily Ticket Volume (for trend charts)
-- ============================================================
CREATE OR ALTER VIEW qbr.vw_DailyVolume AS
SELECT
    CAST(OpenedAt AS DATE) AS TicketDate,
    DATENAME(WEEKDAY, OpenedAt) AS DayOfWeek,
    DATEPART(WEEKDAY, OpenedAt) AS DayOfWeekNum,
    TowerName,
    TrackName,
    COUNT(*) AS TotalTickets,
    SUM(CASE WHEN TicketType = 'Parent' THEN 1 ELSE 0 END) AS Parents,
    SUM(CASE WHEN TicketType = 'Child' THEN 1 ELSE 0 END) AS Children,
    SUM(CASE WHEN Priority = '1 - Critical' THEN 1 ELSE 0 END) AS Critical,
    SUM(CASE WHEN Priority = '2 - High' THEN 1 ELSE 0 END) AS High,
    SUM(CASE WHEN Priority = '3 - Moderate' THEN 1 ELSE 0 END) AS Moderate
FROM qbr.Ticket tk
LEFT JOIN qbr.Tower t ON t.TowerID = tk.TowerID
LEFT JOIN qbr.Track tr ON tr.TrackID = tk.TrackID
WHERE OpenedAt IS NOT NULL
GROUP BY CAST(OpenedAt AS DATE), DATENAME(WEEKDAY, OpenedAt), DATEPART(WEEKDAY, OpenedAt), TowerName, TrackName;
GO

-- ============================================================
-- VIEW 4: Weekly Ticket Volume
-- ============================================================
CREATE OR ALTER VIEW qbr.vw_WeeklyVolume AS
SELECT
    DATEPART(YEAR, OpenedAt) AS Year,
    DATEPART(WEEK, OpenedAt) AS Week,
    DATEADD(WEEK, DATEDIFF(WEEK, 0, OpenedAt), 0) AS WeekStart,
    TowerName,
    TrackName,
    COUNT(*) AS TotalTickets,
    SUM(CASE WHEN TicketType = 'Parent' THEN 1 ELSE 0 END) AS Parents,
    SUM(CASE WHEN TicketType = 'Child' THEN 1 ELSE 0 END) AS Children
FROM qbr.Ticket tk
LEFT JOIN qbr.Tower t ON t.TowerID = tk.TowerID
LEFT JOIN qbr.Track tr ON tr.TrackID = tk.TrackID
WHERE OpenedAt IS NOT NULL
GROUP BY DATEPART(YEAR, OpenedAt), DATEPART(WEEK, OpenedAt), DATEADD(WEEK, DATEDIFF(WEEK, 0, OpenedAt), 0), TowerName, TrackName;
GO

-- ============================================================
-- VIEW 5: Monthly Ticket Volume
-- ============================================================
CREATE OR ALTER VIEW qbr.vw_MonthlyVolume AS
SELECT
    YEAR(OpenedAt) AS Year,
    MONTH(OpenedAt) AS Month,
    DATENAME(MONTH, OpenedAt) AS MonthName,
    TowerName,
    TrackName,
    COUNT(*) AS TotalTickets,
    SUM(CASE WHEN TicketType = 'Parent' THEN 1 ELSE 0 END) AS Parents,
    SUM(CASE WHEN TicketType = 'Child' THEN 1 ELSE 0 END) AS Children
FROM qbr.Ticket tk
LEFT JOIN qbr.Tower t ON t.TowerID = tk.TowerID
LEFT JOIN qbr.Track tr ON tr.TrackID = tk.TrackID
WHERE OpenedAt IS NOT NULL
GROUP BY YEAR(OpenedAt), MONTH(OpenedAt), DATENAME(MONTH, OpenedAt), TowerName, TrackName;
GO

-- ============================================================
-- VIEW 6: Quarterly Ticket Volume
-- ============================================================
CREATE OR ALTER VIEW qbr.vw_QuarterlyVolume AS
SELECT
    YEAR(OpenedAt) AS Year,
    DATEPART(QUARTER, OpenedAt) AS Quarter,
    'Q' + CAST(DATEPART(QUARTER, OpenedAt) AS VARCHAR) + ' ' + CAST(YEAR(OpenedAt) AS VARCHAR) AS QuarterLabel,
    TowerName,
    TrackName,
    COUNT(*) AS TotalTickets,
    SUM(CASE WHEN TicketType = 'Parent' THEN 1 ELSE 0 END) AS Parents,
    SUM(CASE WHEN TicketType = 'Child' THEN 1 ELSE 0 END) AS Children
FROM qbr.Ticket tk
LEFT JOIN qbr.Tower t ON t.TowerID = tk.TowerID
LEFT JOIN qbr.Track tr ON tr.TrackID = tk.TrackID
WHERE OpenedAt IS NOT NULL
GROUP BY YEAR(OpenedAt), DATEPART(QUARTER, OpenedAt), TowerName, TrackName;
GO

-- ============================================================
-- VIEW 7: Alert Frequency by Part
-- ============================================================
CREATE OR ALTER VIEW qbr.vw_AlertFrequency AS
SELECT
    a.Part,
    a.AlertType,
    a.Severity,
    t.TowerName,
    tr.TrackName,
    COUNT(*) AS AlertCount,
    COUNT(DISTINCT a.TicketNumber) AS LinkedTickets
FROM qbr.Alert a
LEFT JOIN qbr.Tower t ON t.TowerID = a.TowerID
LEFT JOIN qbr.Track tr ON tr.TrackID = a.TrackID
GROUP BY a.Part, a.AlertType, a.Severity, t.TowerName, tr.TrackName;
GO

-- ============================================================
-- VIEW 8: Parent-Child Relationship
-- ============================================================
CREATE OR ALTER VIEW qbr.vw_ParentChildRelation AS
SELECT
    p.TicketNumber AS ParentTicketNumber,
    p.TowerName,
    p.TrackName,
    p.Priority AS ParentPriority,
    p.OpenedAt AS ParentOpened,
    p.ClosedAt AS ParentClosed,
    COUNT(c.TicketKey) AS ChildCount,
    MIN(c.OpenedAt) AS FirstChildOpened,
    MAX(c.ClosedAt) AS LastChildClosed
FROM qbr.Ticket tk_parent
JOIN qbr.Ticket p ON p.TicketNumber = tk_parent.TicketNumber
LEFT JOIN qbr.Ticket c ON c.ParentTicketNumber = p.TicketNumber AND c.TicketType = 'Child'
WHERE p.TicketType = 'Parent'
GROUP BY p.TicketNumber, p.TowerName, p.TrackName, p.Priority, p.OpenedAt, p.ClosedAt;
GO

-- ============================================================
-- VIEW 9: Max/Min Ticket Volumes by Date
-- ============================================================
CREATE OR ALTER VIEW qbr.vw_TicketVolumeStats AS
WITH DailyCounts AS (
    SELECT
        CAST(OpenedAt AS DATE) AS TicketDate,
        COUNT(*) AS DailyTotal
    FROM qbr.Ticket
    WHERE OpenedAt IS NOT NULL
    GROUP BY CAST(OpenedAt AS DATE)
)
SELECT
    (SELECT TOP 1 TicketDate FROM DailyCounts ORDER BY DailyTotal DESC) AS MaxVolumeDate,
    (SELECT TOP 1 DailyTotal FROM DailyCounts ORDER BY DailyTotal DESC) AS MaxVolume,
    (SELECT TOP 1 TicketDate FROM DailyCounts ORDER BY DailyTotal ASC) AS MinVolumeDate,
    (SELECT TOP 1 DailyTotal FROM DailyCounts ORDER BY DailyTotal ASC) AS MinVolume,
    (SELECT AVG(DailyTotal * 1.0) FROM DailyCounts) AS AvgVolume,
    (SELECT MIN(TicketDate) FROM DailyCounts) AS DateRangeStart,
    (SELECT MAX(TicketDate) FROM DailyCounts) AS DateRangeEnd
FROM DailyCounts;
GO

-- ============================================================
-- VIEW 10: Tower/Track Alert Summary
-- ============================================================
CREATE OR ALTER VIEW qbr.vw_TowerTrackAlerts AS
SELECT
    t.TowerName,
    tr.TrackName,
    COUNT(a.AlertKey) AS TotalAlerts,
    SUM(CASE WHEN a.Severity = 'Critical' THEN 1 ELSE 0 END) AS CriticalAlerts,
    SUM(CASE WHEN a.Severity = 'High' THEN 1 ELSE 0 END) AS HighAlerts,
    SUM(CASE WHEN a.Severity = 'Moderate' THEN 1 ELSE 0 END) AS ModerateAlerts,
    COUNT(DISTINCT a.Part) AS UniqueParts,
    COUNT(DISTINCT a.AlertType) AS UniqueAlertTypes
FROM qbr.Tower t
JOIN qbr.Track tr ON tr.TowerID = t.TowerID
LEFT JOIN qbr.Alert a ON a.TrackID = tr.TrackID
GROUP BY t.TowerName, tr.TrackName;
GO

-- ============================================================
-- STORED PROCEDURE 1: Get Dashboard Data
-- ============================================================
CREATE OR ALTER PROCEDURE qbr.sp_GetDashboardData
    @StartDate DATETIME2 = NULL,
    @EndDate DATETIME2 = NULL,
    @TowerID INT = NULL,
    @TrackID INT = NULL
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Default date range: last 30 days
    IF @StartDate IS NULL SET @StartDate = DATEADD(DAY, -30, GETDATE());
    IF @EndDate IS NULL SET @EndDate = GETDATE();
    
    -- Executive KPIs
    SELECT
        COUNT(*) AS TotalTickets,
        SUM(CASE WHEN TicketType = 'Parent' THEN 1 ELSE 0 END) AS ParentTickets,
        SUM(CASE WHEN TicketType = 'Child' THEN 1 ELSE 0 END) AS ChildTickets,
        SUM(CASE WHEN State = 'Closed' THEN 1 ELSE 0 END) AS ClosedTickets,
        SUM(CASE WHEN Priority = '1 - Critical' THEN 1 ELSE 0 END) AS CriticalTickets,
        SUM(CASE WHEN Priority = '2 - High' THEN 1 ELSE 0 END) AS HighTickets
    FROM qbr.Ticket
    WHERE OpenedAt BETWEEN @StartDate AND @EndDate
        AND (@TowerID IS NULL OR TowerID = @TowerID)
        AND (@TrackID IS NULL OR TrackID = @TrackID);
    
    -- Tower/Track breakdown
    SELECT
        t.TowerName,
        tr.TrackName,
        COUNT(*) AS TicketCount
    FROM qbr.Ticket tk
    JOIN qbr.Tower t ON t.TowerID = tk.TowerID
    JOIN qbr.Track tr ON tr.TrackID = tk.TrackID
    WHERE tk.OpenedAt BETWEEN @StartDate AND @EndDate
        AND (@TowerID IS NULL OR tk.TowerID = @TowerID)
        AND (@TrackID IS NULL OR tk.TrackID = @TrackID)
    GROUP BY t.TowerName, tr.TrackName
    ORDER BY TicketCount DESC;
    
    -- Daily trend
    SELECT
        CAST(OpenedAt AS DATE) AS TicketDate,
        COUNT(*) AS DailyTotal,
        SUM(CASE WHEN TicketType = 'Parent' THEN 1 ELSE 0 END) AS Parents,
        SUM(CASE WHEN TicketType = 'Child' THEN 1 ELSE 0 END) AS Children
    FROM qbr.Ticket
    WHERE OpenedAt BETWEEN @StartDate AND @EndDate
        AND (@TowerID IS NULL OR TowerID = @TowerID)
        AND (@TrackID IS NULL OR TrackID = @TrackID)
    GROUP BY CAST(OpenedAt AS DATE)
    ORDER BY TicketDate;
    
    -- Alert summary
    SELECT
        Part,
        AlertType,
        COUNT(*) AS AlertCount
    FROM qbr.Alert
    WHERE AlertTime BETWEEN @StartDate AND @EndDate
        AND (@TowerID IS NULL OR TowerID = @TowerID)
        AND (@TrackID IS NULL OR TrackID = @TrackID)
    GROUP BY Part, AlertType
    ORDER BY AlertCount DESC;
END;
GO

-- ============================================================
-- STORED PROCEDURE 2: Refresh Dashboard Cache
-- ============================================================
CREATE OR ALTER PROCEDURE qbr.sp_RefreshDashboard
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Log refresh start
    DECLARE @BatchID UNIQUEIDENTIFIER = NEWID();
    
    INSERT INTO qbr.RefreshLog (LoadBatchID, SourceName, StartedAt, Status)
    VALUES (@BatchID, 'Dashboard Refresh', SYSUTCDATETIME(), 'Running');
    
    -- Update statistics (helps query performance)
    UPDATE STATISTICS qbr.Ticket;
    UPDATE STATISTICS qbr.Alert;
    
    -- Log refresh complete
    UPDATE qbr.RefreshLog
    SET FinishedAt = SYSUTCDATETIME(),
        Status = 'Completed'
    WHERE LoadBatchID = @BatchID;
    
    SELECT 'Dashboard refreshed successfully' AS Result;
END;
GO

PRINT 'Analytics views and procedures created successfully!';
GO
