/* QBR Ticket-centric model validation. Run after 08_ticket_customer_mapping.sql. */
SET NOCOUNT ON;

PRINT '1. Customer mapping catalogue';
SELECT CustomerID,CompanyAccountName,TowerID,TrackID
FROM qbr.Customer
WHERE ISNULL(IsActive,1)=1
ORDER BY TowerID,TrackID,CompanyAccountName;

PRINT '2. Foundation tracks';
SELECT t.TowerName,tr.TrackName,tr.TrackID
FROM qbr.Track tr
JOIN qbr.Tower t ON t.TowerID=tr.TowerID
WHERE t.TowerName='Foundation' AND tr.TrackName IN ('SFNOC','THD Data','HSBC Data')
ORDER BY CASE tr.TrackName WHEN 'SFNOC' THEN 1 WHEN 'THD Data' THEN 2 WHEN 'HSBC Data' THEN 3 ELSE 9 END;

PRINT '3. Unmapped ticket accounts - target is zero';
SELECT tk.CompanyAccount,COUNT(*) AS TicketCount
FROM qbr.Ticket tk
LEFT JOIN qbr.Customer c
  ON UPPER(LTRIM(RTRIM(ISNULL(tk.CompanyAccount,''))))=UPPER(LTRIM(RTRIM(ISNULL(c.CompanyAccountName,''))))
 AND ISNULL(c.IsActive,1)=1
WHERE c.CustomerID IS NULL
GROUP BY tk.CompanyAccount
ORDER BY TicketCount DESC,tk.CompanyAccount;

PRINT '4. Ticket classification';
SELECT
  COUNT(*) AS TotalTickets,
  SUM(CASE WHEN UPPER(LTRIM(RTRIM(ISNULL(Caller,'')))) IN ('EMS','CMSP') THEN 1 ELSE 0 END) AS MonitoringTickets,
  SUM(CASE WHEN UPPER(LTRIM(RTRIM(ISNULL(Caller,'')))) NOT IN ('EMS','CMSP') OR Caller IS NULL THEN 1 ELSE 0 END) AS UserTickets
FROM qbr.Ticket;

PRINT '5. Duplicate TicketNumber - target is zero';
SELECT TicketNumber,COUNT(*) AS DuplicateCount
FROM qbr.Ticket
GROUP BY TicketNumber
HAVING COUNT(*)>1
ORDER BY DuplicateCount DESC,TicketNumber;

PRINT '6. Unknown Tower/Track after Customer mapping - target is zero';
SELECT COUNT(*) AS UnresolvedTickets
FROM qbr.Ticket tk
LEFT JOIN qbr.Customer c
  ON UPPER(LTRIM(RTRIM(ISNULL(tk.CompanyAccount,''))))=UPPER(LTRIM(RTRIM(ISNULL(c.CompanyAccountName,''))))
 AND ISNULL(c.IsActive,1)=1
WHERE c.CustomerID IS NULL OR tk.TowerID IS NULL OR tk.TrackID IS NULL;

PRINT '7. Ticket volume by Tower -> Track';
SELECT t.TowerName,tr.TrackName,COUNT(*) AS Tickets
FROM qbr.Ticket tk
JOIN qbr.Tower t ON t.TowerID=tk.TowerID
JOIN qbr.Track tr ON tr.TrackID=tk.TrackID
GROUP BY t.TowerName,tr.TrackName
ORDER BY Tickets DESC,t.TowerName,tr.TrackName;

PRINT '8. Monitoring/device frequency';
SELECT ISNULL(Device,'Unknown') AS Device,COUNT(*) AS MonitoringTickets
FROM qbr.Ticket
WHERE UPPER(LTRIM(RTRIM(ISNULL(Caller,'')))) IN ('EMS','CMSP')
GROUP BY ISNULL(Device,'Unknown')
ORDER BY MonitoringTickets DESC,Device;
