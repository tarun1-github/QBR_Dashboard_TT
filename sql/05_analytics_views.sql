/*
 QBR Dashboard - Analytics Views

 qbr.Ticket is the single fact table.
 Caller EMS/CMSP = monitoring-generated ticket.
 qbr.Customer supplies CompanyAccount -> Tower -> Track mapping.
 qbr.Alert/qbr.TicketAlert are not used by these views.
*/

CREATE OR ALTER VIEW qbr.vw_ExecutiveKPI AS
SELECT
    COUNT(*) AS TotalTickets,
    SUM(CASE WHEN TicketType='Parent' THEN 1 ELSE 0 END) AS ParentTickets,
    SUM(CASE WHEN TicketType='Child' THEN 1 ELSE 0 END) AS ChildTickets,
    SUM(CASE WHEN UPPER(LTRIM(RTRIM(ISNULL(Caller,'')))) IN ('EMS','CMSP') THEN 1 ELSE 0 END) AS TotalMonitoringTickets,
    SUM(CASE WHEN State='Open' OR ClosedAt IS NULL THEN 1 ELSE 0 END) AS OpenTickets,
    SUM(CASE WHEN State='Closed' AND ClosedAt IS NOT NULL THEN 1 ELSE 0 END) AS ClosedTickets,
    SUM(CASE WHEN Priority IN ('1 - Critical','Critical','1') THEN 1 ELSE 0 END) AS CriticalTickets,
    SUM(CASE WHEN Priority IN ('2 - High','High','2') THEN 1 ELSE 0 END) AS HighTickets,
    SUM(CASE WHEN Priority IN ('3 - Moderate','Moderate','3','Medium') THEN 1 ELSE 0 END) AS ModerateTickets,
    COUNT(DISTINCT TowerID) AS ActiveTowers,
    COUNT(DISTINCT TrackID) AS ActiveTracks,
    MIN(OpenedAt) AS EarliestTicket,
    MAX(OpenedAt) AS LatestTicket
FROM qbr.Ticket;
GO

CREATE OR ALTER VIEW qbr.vw_TowerTrackVolume AS
SELECT
    t.TowerID,t.TowerName,tr.TrackID,tr.TrackName,
    COUNT(tk.TicketKey) AS TotalTickets,
    SUM(CASE WHEN tk.TicketType='Parent' THEN 1 ELSE 0 END) AS ParentTickets,
    SUM(CASE WHEN tk.TicketType='Child' THEN 1 ELSE 0 END) AS ChildTickets,
    SUM(CASE WHEN tk.Priority IN ('1 - Critical','Critical','1') THEN 1 ELSE 0 END) AS CriticalTickets,
    SUM(CASE WHEN tk.Priority IN ('2 - High','High','2') THEN 1 ELSE 0 END) AS HighTickets,
    SUM(CASE WHEN tk.State='Closed' THEN 1 ELSE 0 END) AS ClosedTickets,
    SUM(CASE WHEN tk.State='Open' OR tk.ClosedAt IS NULL THEN 1 ELSE 0 END) AS OpenTickets,
    COUNT(DISTINCT tk.Device) AS UniqueDevices,
    SUM(CASE WHEN UPPER(LTRIM(RTRIM(ISNULL(tk.Caller,'')))) IN ('EMS','CMSP') THEN 1 ELSE 0 END) AS MonitoringTickets,
    ISNULL(SUM(tk.VETimeSavedMinutes),0) AS TotalVEMinutes
FROM qbr.Tower t
JOIN qbr.Track tr ON tr.TowerID=t.TowerID
LEFT JOIN qbr.Ticket tk ON tk.TrackID=tr.TrackID
GROUP BY t.TowerID,t.TowerName,tr.TrackID,tr.TrackName;
GO

CREATE OR ALTER VIEW qbr.vw_DailyVolume AS
SELECT
    CAST(tk.OpenedAt AS DATE) AS TicketDate,
    DATENAME(WEEKDAY,tk.OpenedAt) AS DayOfWeek,
    DATEPART(WEEKDAY,tk.OpenedAt) AS DayOfWeekNum,
    t.TowerName,tr.TrackName,
    COUNT(*) AS TotalTickets,
    SUM(CASE WHEN tk.TicketType='Parent' THEN 1 ELSE 0 END) AS Parents,
    SUM(CASE WHEN tk.TicketType='Child' THEN 1 ELSE 0 END) AS Children,
    SUM(CASE WHEN UPPER(LTRIM(RTRIM(ISNULL(tk.Caller,'')))) IN ('EMS','CMSP') THEN 1 ELSE 0 END) AS MonitoringTickets,
    SUM(CASE WHEN tk.Priority IN ('1 - Critical','Critical','1') THEN 1 ELSE 0 END) AS Critical,
    SUM(CASE WHEN tk.Priority IN ('2 - High','High','2') THEN 1 ELSE 0 END) AS High,
    SUM(CASE WHEN tk.Priority IN ('3 - Moderate','Moderate','3','Medium') THEN 1 ELSE 0 END) AS Moderate
FROM qbr.Ticket tk
LEFT JOIN qbr.Tower t ON t.TowerID=tk.TowerID
LEFT JOIN qbr.Track tr ON tr.TrackID=tk.TrackID
WHERE tk.OpenedAt IS NOT NULL
GROUP BY CAST(tk.OpenedAt AS DATE),DATENAME(WEEKDAY,tk.OpenedAt),DATEPART(WEEKDAY,tk.OpenedAt),t.TowerName,tr.TrackName;
GO

CREATE OR ALTER VIEW qbr.vw_WeeklyVolume AS
SELECT
    DATEPART(YEAR,tk.OpenedAt) AS Year,
    DATEPART(WEEK,tk.OpenedAt) AS Week,
    DATEADD(WEEK,DATEDIFF(WEEK,0,tk.OpenedAt),0) AS WeekStart,
    t.TowerName,tr.TrackName,COUNT(*) AS TotalTickets,
    SUM(CASE WHEN tk.TicketType='Parent' THEN 1 ELSE 0 END) AS Parents,
    SUM(CASE WHEN tk.TicketType='Child' THEN 1 ELSE 0 END) AS Children,
    SUM(CASE WHEN UPPER(LTRIM(RTRIM(ISNULL(tk.Caller,'')))) IN ('EMS','CMSP') THEN 1 ELSE 0 END) AS MonitoringTickets
FROM qbr.Ticket tk
LEFT JOIN qbr.Tower t ON t.TowerID=tk.TowerID
LEFT JOIN qbr.Track tr ON tr.TrackID=tk.TrackID
WHERE tk.OpenedAt IS NOT NULL
GROUP BY DATEPART(YEAR,tk.OpenedAt),DATEPART(WEEK,tk.OpenedAt),DATEADD(WEEK,DATEDIFF(WEEK,0,tk.OpenedAt),0),t.TowerName,tr.TrackName;
GO

CREATE OR ALTER VIEW qbr.vw_MonthlyVolume AS
SELECT
    YEAR(tk.OpenedAt) AS Year,MONTH(tk.OpenedAt) AS Month,DATENAME(MONTH,tk.OpenedAt) AS MonthName,
    t.TowerName,tr.TrackName,COUNT(*) AS TotalTickets,
    SUM(CASE WHEN tk.TicketType='Parent' THEN 1 ELSE 0 END) AS Parents,
    SUM(CASE WHEN tk.TicketType='Child' THEN 1 ELSE 0 END) AS Children,
    SUM(CASE WHEN UPPER(LTRIM(RTRIM(ISNULL(tk.Caller,'')))) IN ('EMS','CMSP') THEN 1 ELSE 0 END) AS MonitoringTickets
FROM qbr.Ticket tk
LEFT JOIN qbr.Tower t ON t.TowerID=tk.TowerID
LEFT JOIN qbr.Track tr ON tr.TrackID=tk.TrackID
WHERE tk.OpenedAt IS NOT NULL
GROUP BY YEAR(tk.OpenedAt),MONTH(tk.OpenedAt),DATENAME(MONTH,tk.OpenedAt),t.TowerName,tr.TrackName;
GO

CREATE OR ALTER VIEW qbr.vw_QuarterlyVolume AS
SELECT
    YEAR(tk.OpenedAt) AS Year,DATEPART(QUARTER,tk.OpenedAt) AS Quarter,
    'Q'+CAST(DATEPART(QUARTER,tk.OpenedAt) AS VARCHAR)+' '+CAST(YEAR(tk.OpenedAt) AS VARCHAR) AS QuarterLabel,
    t.TowerName,tr.TrackName,COUNT(*) AS TotalTickets,
    SUM(CASE WHEN tk.TicketType='Parent' THEN 1 ELSE 0 END) AS Parents,
    SUM(CASE WHEN tk.TicketType='Child' THEN 1 ELSE 0 END) AS Children,
    SUM(CASE WHEN UPPER(LTRIM(RTRIM(ISNULL(tk.Caller,'')))) IN ('EMS','CMSP') THEN 1 ELSE 0 END) AS MonitoringTickets
FROM qbr.Ticket tk
LEFT JOIN qbr.Tower t ON t.TowerID=tk.TowerID
LEFT JOIN qbr.Track tr ON tr.TrackID=tk.TrackID
WHERE tk.OpenedAt IS NOT NULL
GROUP BY YEAR(tk.OpenedAt),DATEPART(QUARTER,tk.OpenedAt),t.TowerName,tr.TrackName;
GO

/* Monitoring/device frequency - replaces the old Alert/Part view. */
CREATE OR ALTER VIEW qbr.vw_AlertFrequency AS
SELECT
    ISNULL(tk.Device,'Unknown') AS Device,
    'Monitoring-generated ticket' AS AlertType,
    ISNULL(tk.Priority,'Unknown') AS Severity,
    t.TowerName,tr.TrackName,
    COUNT(*) AS AlertCount,
    COUNT(DISTINCT tk.TicketNumber) AS LinkedTickets
FROM qbr.Ticket tk
LEFT JOIN qbr.Tower t ON t.TowerID=tk.TowerID
LEFT JOIN qbr.Track tr ON tr.TrackID=tk.TrackID
WHERE UPPER(LTRIM(RTRIM(ISNULL(tk.Caller,'')))) IN ('EMS','CMSP')
GROUP BY ISNULL(tk.Device,'Unknown'),ISNULL(tk.Priority,'Unknown'),t.TowerName,tr.TrackName;
GO

CREATE OR ALTER VIEW qbr.vw_ParentChildRelation AS
SELECT
    p.TicketNumber AS ParentTicketNumber,
    t.TowerName,tr.TrackName,
    p.Priority AS ParentPriority,p.OpenedAt AS ParentOpened,p.ClosedAt AS ParentClosed,
    COUNT(c.TicketKey) AS ChildCount,MIN(c.OpenedAt) AS FirstChildOpened,MAX(c.ClosedAt) AS LastChildClosed
FROM qbr.Ticket p
LEFT JOIN qbr.Ticket c ON c.ParentTicketNumber=p.TicketNumber AND c.TicketType='Child'
LEFT JOIN qbr.Tower t ON t.TowerID=p.TowerID
LEFT JOIN qbr.Track tr ON tr.TrackID=p.TrackID
WHERE p.TicketType='Parent'
GROUP BY p.TicketNumber,t.TowerName,tr.TrackName,p.Priority,p.OpenedAt,p.ClosedAt;
GO

CREATE OR ALTER VIEW qbr.vw_TicketVolumeStats AS
WITH DailyCounts AS
(
    SELECT CAST(OpenedAt AS DATE) AS TicketDate,COUNT(*) AS DailyTotal
    FROM qbr.Ticket WHERE OpenedAt IS NOT NULL GROUP BY CAST(OpenedAt AS DATE)
)
SELECT
    (SELECT TOP 1 TicketDate FROM DailyCounts ORDER BY DailyTotal DESC,TicketDate) AS MaxVolumeDate,
    (SELECT TOP 1 DailyTotal FROM DailyCounts ORDER BY DailyTotal DESC,TicketDate) AS MaxVolume,
    (SELECT TOP 1 TicketDate FROM DailyCounts ORDER BY DailyTotal ASC,TicketDate) AS MinVolumeDate,
    (SELECT TOP 1 DailyTotal FROM DailyCounts ORDER BY DailyTotal ASC,TicketDate) AS MinVolume,
    (SELECT AVG(DailyTotal*1.0) FROM DailyCounts) AS AvgVolume,
    (SELECT MIN(TicketDate) FROM DailyCounts) AS DateRangeStart,
    (SELECT MAX(TicketDate) FROM DailyCounts) AS DateRangeEnd
FROM DailyCounts;
GO

/* Monitoring severity by Tower -> Track. */
CREATE OR ALTER VIEW qbr.vw_TowerTrackAlerts AS
SELECT
    t.TowerName,tr.TrackName,
    COUNT(tk.TicketKey) AS TotalAlerts,
    SUM(CASE WHEN tk.Priority IN ('1 - Critical','Critical','1') THEN 1 ELSE 0 END) AS CriticalAlerts,
    SUM(CASE WHEN tk.Priority IN ('2 - High','High','2') THEN 1 ELSE 0 END) AS HighAlerts,
    SUM(CASE WHEN tk.Priority IN ('3 - Moderate','Moderate','3','Medium') THEN 1 ELSE 0 END) AS ModerateAlerts,
    COUNT(DISTINCT tk.Device) AS UniqueDevices,
    COUNT(DISTINCT tk.Service) AS UniqueServices
FROM qbr.Tower t
JOIN qbr.Track tr ON tr.TowerID=t.TowerID
LEFT JOIN qbr.Ticket tk
  ON tk.TrackID=tr.TrackID
 AND UPPER(LTRIM(RTRIM(ISNULL(tk.Caller,'')))) IN ('EMS','CMSP')
GROUP BY t.TowerName,tr.TrackName;
GO

CREATE OR ALTER PROCEDURE qbr.sp_GetDashboardData
    @StartDate DATETIME2=NULL,@EndDate DATETIME2=NULL,@TowerID INT=NULL,@TrackID INT=NULL
AS
BEGIN
    SET NOCOUNT ON;
    IF @StartDate IS NULL SET @StartDate=DATEADD(DAY,-30,GETDATE());
    IF @EndDate IS NULL SET @EndDate=GETDATE();

    SELECT COUNT(*) TotalTickets,
           SUM(CASE WHEN TicketType='Parent' THEN 1 ELSE 0 END) ParentTickets,
           SUM(CASE WHEN TicketType='Child' THEN 1 ELSE 0 END) ChildTickets,
           SUM(CASE WHEN UPPER(LTRIM(RTRIM(ISNULL(Caller,'')))) IN ('EMS','CMSP') THEN 1 ELSE 0 END) MonitoringTickets,
           SUM(CASE WHEN State='Closed' THEN 1 ELSE 0 END) ClosedTickets,
           SUM(CASE WHEN Priority IN ('1 - Critical','Critical','1') THEN 1 ELSE 0 END) CriticalTickets,
           SUM(CASE WHEN Priority IN ('2 - High','High','2') THEN 1 ELSE 0 END) HighTickets
    FROM qbr.Ticket
    WHERE OpenedAt BETWEEN @StartDate AND @EndDate
      AND (@TowerID IS NULL OR TowerID=@TowerID)
      AND (@TrackID IS NULL OR TrackID=@TrackID);

    SELECT t.TowerName,tr.TrackName,COUNT(*) TicketCount,
           SUM(CASE WHEN UPPER(LTRIM(RTRIM(ISNULL(tk.Caller,'')))) IN ('EMS','CMSP') THEN 1 ELSE 0 END) MonitoringTickets
    FROM qbr.Ticket tk
    JOIN qbr.Tower t ON t.TowerID=tk.TowerID
    JOIN qbr.Track tr ON tr.TrackID=tk.TrackID
    WHERE tk.OpenedAt BETWEEN @StartDate AND @EndDate
      AND (@TowerID IS NULL OR tk.TowerID=@TowerID)
      AND (@TrackID IS NULL OR tk.TrackID=@TrackID)
    GROUP BY t.TowerName,tr.TrackName
    ORDER BY TicketCount DESC;

    SELECT CAST(OpenedAt AS DATE) TicketDate,COUNT(*) DailyTotal,
           SUM(CASE WHEN TicketType='Parent' THEN 1 ELSE 0 END) Parents,
           SUM(CASE WHEN TicketType='Child' THEN 1 ELSE 0 END) Children,
           SUM(CASE WHEN UPPER(LTRIM(RTRIM(ISNULL(Caller,'')))) IN ('EMS','CMSP') THEN 1 ELSE 0 END) MonitoringTickets
    FROM qbr.Ticket
    WHERE OpenedAt BETWEEN @StartDate AND @EndDate
      AND (@TowerID IS NULL OR TowerID=@TowerID)
      AND (@TrackID IS NULL OR TrackID=@TrackID)
    GROUP BY CAST(OpenedAt AS DATE)
    ORDER BY TicketDate;

    SELECT ISNULL(Device,'Unknown') Device,COUNT(*) AlertCount
    FROM qbr.Ticket
    WHERE UPPER(LTRIM(RTRIM(ISNULL(Caller,'')))) IN ('EMS','CMSP')
      AND OpenedAt BETWEEN @StartDate AND @EndDate
      AND (@TowerID IS NULL OR TowerID=@TowerID)
      AND (@TrackID IS NULL OR TrackID=@TrackID)
    GROUP BY ISNULL(Device,'Unknown')
    ORDER BY AlertCount DESC;
END;
GO

CREATE OR ALTER PROCEDURE qbr.sp_RefreshDashboard
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @BatchID UNIQUEIDENTIFIER=NEWID();
    INSERT INTO qbr.RefreshLog(LoadBatchID,SourceName,StartedAt,Status)
    VALUES(@BatchID,'Dashboard Refresh',SYSUTCDATETIME(),'Running');
    UPDATE STATISTICS qbr.Ticket;
    UPDATE qbr.RefreshLog SET FinishedAt=SYSUTCDATETIME(),Status='Completed' WHERE LoadBatchID=@BatchID;
    SELECT 'Dashboard refreshed successfully' AS Result;
END;
GO

PRINT 'Ticket-centric analytics views and procedures created successfully.';
GO
