/* QBR Dashboard - replace legacy Part analytics with Device */
SET NOCOUNT ON;

CREATE OR ALTER VIEW qbr.vw_TowerTrackVolume AS
SELECT
    t.TowerID,t.TowerName,tr.TrackID,tr.TrackName,
    COUNT(tk.TicketKey) AS TotalTickets,
    SUM(CASE WHEN tk.TicketType='Parent' THEN 1 ELSE 0 END) AS ParentTickets,
    SUM(CASE WHEN tk.TicketType='Child' THEN 1 ELSE 0 END) AS ChildTickets,
    SUM(CASE WHEN tk.Priority='1 - Critical' THEN 1 ELSE 0 END) AS CriticalTickets,
    SUM(CASE WHEN tk.Priority='2 - High' THEN 1 ELSE 0 END) AS HighTickets,
    SUM(CASE WHEN tk.State='Closed' THEN 1 ELSE 0 END) AS ClosedTickets,
    SUM(CASE WHEN tk.State='Open' OR tk.ClosedAt IS NULL THEN 1 ELSE 0 END) AS OpenTickets,
    COUNT(DISTINCT tk.Device) AS UniqueDevices,
    ISNULL(SUM(tk.VETimeSavedMinutes),0) AS TotalVEMinutes
FROM qbr.Tower t
JOIN qbr.Track tr ON tr.TowerID=t.TowerID
LEFT JOIN qbr.Ticket tk ON tk.TrackID=tr.TrackID
GROUP BY t.TowerID,t.TowerName,tr.TrackID,tr.TrackName;
GO

CREATE OR ALTER VIEW qbr.vw_AlertFrequency AS
SELECT
    a.Device,
    a.AlertType,
    a.Severity,
    t.TowerName,
    tr.TrackName,
    COUNT(*) AS AlertCount,
    COUNT(DISTINCT a.TicketNumber) AS LinkedTickets
FROM qbr.Alert a
LEFT JOIN qbr.Tower t ON t.TowerID=a.TowerID
LEFT JOIN qbr.Track tr ON tr.TrackID=a.TrackID
GROUP BY a.Device,a.AlertType,a.Severity,t.TowerName,tr.TrackName;
GO

CREATE OR ALTER VIEW qbr.vw_TowerTrackAlerts AS
SELECT
    t.TowerName,
    tr.TrackName,
    COUNT(a.AlertKey) AS TotalAlerts,
    SUM(CASE WHEN a.Severity='Critical' THEN 1 ELSE 0 END) AS CriticalAlerts,
    SUM(CASE WHEN a.Severity='High' THEN 1 ELSE 0 END) AS HighAlerts,
    SUM(CASE WHEN a.Severity='Moderate' THEN 1 ELSE 0 END) AS ModerateAlerts,
    COUNT(DISTINCT a.Device) AS UniqueDevices,
    COUNT(DISTINCT a.AlertType) AS UniqueAlertTypes
FROM qbr.Tower t
JOIN qbr.Track tr ON tr.TowerID=t.TowerID
LEFT JOIN qbr.Alert a ON a.TrackID=tr.TrackID
GROUP BY t.TowerName,tr.TrackName;
GO

CREATE OR ALTER PROCEDURE qbr.sp_GetDashboardData
    @StartDate DATETIME2=NULL,
    @EndDate DATETIME2=NULL,
    @TowerID INT=NULL,
    @TrackID INT=NULL
AS
BEGIN
    SET NOCOUNT ON;
    IF @StartDate IS NULL SET @StartDate=DATEADD(DAY,-30,GETDATE());
    IF @EndDate IS NULL SET @EndDate=GETDATE();

    SELECT COUNT(*) AS TotalTickets,
           SUM(CASE WHEN TicketType='Parent' THEN 1 ELSE 0 END) AS ParentTickets,
           SUM(CASE WHEN TicketType='Child' THEN 1 ELSE 0 END) AS ChildTickets,
           SUM(CASE WHEN State='Closed' THEN 1 ELSE 0 END) AS ClosedTickets,
           SUM(CASE WHEN Priority='1 - Critical' THEN 1 ELSE 0 END) AS CriticalTickets,
           SUM(CASE WHEN Priority='2 - High' THEN 1 ELSE 0 END) AS HighTickets
    FROM qbr.Ticket
    WHERE OpenedAt BETWEEN @StartDate AND @EndDate
      AND (@TowerID IS NULL OR TowerID=@TowerID)
      AND (@TrackID IS NULL OR TrackID=@TrackID);

    SELECT t.TowerName,tr.TrackName,COUNT(*) AS TicketCount
    FROM qbr.Ticket tk
    JOIN qbr.Tower t ON t.TowerID=tk.TowerID
    JOIN qbr.Track tr ON tr.TrackID=tk.TrackID
    WHERE tk.OpenedAt BETWEEN @StartDate AND @EndDate
      AND (@TowerID IS NULL OR tk.TowerID=@TowerID)
      AND (@TrackID IS NULL OR tk.TrackID=@TrackID)
    GROUP BY t.TowerName,tr.TrackName
    ORDER BY TicketCount DESC;

    SELECT CAST(OpenedAt AS DATE) AS TicketDate,
           COUNT(*) AS DailyTotal,
           SUM(CASE WHEN TicketType='Parent' THEN 1 ELSE 0 END) AS Parents,
           SUM(CASE WHEN TicketType='Child' THEN 1 ELSE 0 END) AS Children
    FROM qbr.Ticket
    WHERE OpenedAt BETWEEN @StartDate AND @EndDate
      AND (@TowerID IS NULL OR TowerID=@TowerID)
      AND (@TrackID IS NULL OR TrackID=@TrackID)
    GROUP BY CAST(OpenedAt AS DATE)
    ORDER BY TicketDate;

    SELECT Device,AlertType,COUNT(*) AS AlertCount
    FROM qbr.Alert
    WHERE AlertTime BETWEEN @StartDate AND @EndDate
      AND (@TowerID IS NULL OR TowerID=@TowerID)
      AND (@TrackID IS NULL OR TrackID=@TrackID)
    GROUP BY Device,AlertType
    ORDER BY AlertCount DESC;
END;
GO
