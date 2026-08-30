/*
 QBR Dashboard - Ticket-centric mapping model

 qbr.Ticket is the single fact table.
 qbr.Customer is the CompanyAccount -> Tower -> Track mapping table.
 Caller EMS/CMSP identifies monitoring-generated tickets.
 qbr.Alert / qbr.TicketAlert are retained temporarily for rollback only and
 are no longer read or written by the application.
*/
SET NOCOUNT ON;

/* 1. Extend Customer into the authoritative account mapping table. */
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('qbr.Customer') AND name='CompanyAccountName')
    ALTER TABLE qbr.Customer ADD CompanyAccountName NVARCHAR(200) NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('qbr.Customer') AND name='TowerID')
    ALTER TABLE qbr.Customer ADD TowerID INT NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('qbr.Customer') AND name='TrackID')
    ALTER TABLE qbr.Customer ADD TrackID INT NULL;
GO

UPDATE qbr.Customer
SET CompanyAccountName = COALESCE(NULLIF(LTRIM(RTRIM(CompanyAccountName)),''), NULLIF(LTRIM(RTRIM(CustomerName)),''));
GO

/* Normalize the historical Dome Depot typo BEFORE inserting the catalogue. */
UPDATE qbr.Customer
SET CompanyAccountName='Home Depot', CustomerName='Home Depot'
WHERE UPPER(LTRIM(RTRIM(ISNULL(CompanyAccountName,CustomerName)))) IN ('DOME DEPOT','THE HOME DEPOT','THD','HOME DEPOT');
GO

/* 2. Seed the authoritative 15 business mappings. */
;WITH Mapping AS
(
    SELECT * FROM (VALUES
      ('BOA EV','Bank of America','Collaboration','BOA EV'),
      ('HSBC','HSBC','Collaboration','HSBC'),
      ('Problem Management','Problem Management','Collaboration','Problem Management'),
      ('BOA TP','BOA TP','Collaboration','BOA TP'),
      ('GTM TP','GTM TP','Collaboration','GTM TP'),
      ('HD Voice (Bgl)','HD Voice (Bgl)','Collaboration','HD Voice (Bgl)'),
      ('SCNOC','SCNOC','Collaboration','SCNOC'),
      ('Cybersecurity','Cybersecurity','Security','Cybersecurity'),
      ('DC-ACI','DC-ACI','Security','DC-ACI'),
      ('Infra','Infra','Security','Infra'),
      ('SOC','SOC','Security','SOC'),
      ('SFNOC','SFNOC','Foundation','SFNOC'),
      ('Home Depot','Home Depot','Foundation','THD Data'),
      ('HSBC Data','HSBC Data','Foundation','HSBC Data'),
      ('RIL','RIL','Non-CMS','RIL')
    ) v(CompanyAccountName,CustomerName,TowerName,TrackName)
)
INSERT INTO qbr.Customer(CustomerName,CompanyAccountName,CustomerCode,TowerID,TrackID,IsActive)
SELECT m.CustomerName,m.CompanyAccountName,UPPER(REPLACE(m.TrackName,' ','')),tw.TowerID,tr.TrackID,1
FROM Mapping m
JOIN qbr.Tower tw ON tw.TowerName=m.TowerName
JOIN qbr.Track tr ON tr.TowerID=tw.TowerID AND tr.TrackName=m.TrackName
WHERE NOT EXISTS
(
    SELECT 1 FROM qbr.Customer c
    WHERE UPPER(LTRIM(RTRIM(ISNULL(c.CompanyAccountName,''))))=UPPER(m.CompanyAccountName)
);
GO

/* Refresh all 15 mappings. */
;WITH Mapping AS
(
    SELECT * FROM (VALUES
      ('Bank of America','Collaboration','BOA EV'),('BOA EV','Collaboration','BOA EV'),
      ('HSBC','Collaboration','HSBC'),('Problem Management','Collaboration','Problem Management'),
      ('BOA TP','Collaboration','BOA TP'),('GTM TP','Collaboration','GTM TP'),
      ('HD Voice (Bgl)','Collaboration','HD Voice (Bgl)'),('SCNOC','Collaboration','SCNOC'),
      ('Cybersecurity','Security','Cybersecurity'),('DC-ACI','Security','DC-ACI'),
      ('Infra','Security','Infra'),('SOC','Security','SOC'),('SFNOC','Foundation','SFNOC'),
      ('Home Depot','Foundation','THD Data'),('HSBC Data','Foundation','HSBC Data'),('RIL','Non-CMS','RIL')
    ) v(CompanyAccountName,TowerName,TrackName)
)
UPDATE c
SET c.TowerID=tw.TowerID,c.TrackID=tr.TrackID,c.IsActive=1
FROM qbr.Customer c
JOIN Mapping m ON UPPER(LTRIM(RTRIM(ISNULL(c.CompanyAccountName,''))))=UPPER(m.CompanyAccountName)
JOIN qbr.Tower tw ON tw.TowerName=m.TowerName
JOIN qbr.Track tr ON tr.TowerID=tw.TowerID AND tr.TrackName=m.TrackName;
GO

/* 3. Ticket columns required by the new model. */
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('qbr.Ticket') AND name='Caller')
    ALTER TABLE qbr.Ticket ADD Caller NVARCHAR(200) NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('qbr.Ticket') AND name='Device')
    ALTER TABLE qbr.Ticket ADD Device NVARCHAR(200) NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('qbr.Ticket') AND name='IsMonitoringGenerated')
    ALTER TABLE qbr.Ticket ADD IsMonitoringGenerated BIT NULL;
GO

IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('qbr.Ticket') AND name='Part')
    UPDATE qbr.Ticket SET Device=COALESCE(NULLIF(LTRIM(RTRIM(Device)),''),Part) WHERE Device IS NULL OR LTRIM(RTRIM(Device))='';
GO

/* 4. Normalize ticket CompanyAccount and classify monitoring tickets. */
UPDATE qbr.Ticket
SET CompanyAccount=CASE WHEN UPPER(LTRIM(RTRIM(ISNULL(CompanyAccount,'')))) LIKE '%HOME%' THEN 'Home Depot' ELSE LTRIM(RTRIM(CompanyAccount)) END,
    IsMonitoringGenerated=CASE WHEN UPPER(LTRIM(RTRIM(ISNULL(Caller,'')))) IN ('EMS','CMSP') THEN 1 ELSE 0 END
WHERE CompanyAccount IS NOT NULL OR Caller IS NOT NULL;
GO

/* 5. Populate Ticket Customer/Tower/Track from CompanyAccount. */
UPDATE tk
SET tk.CustomerID=c.CustomerID,
    tk.TowerID=c.TowerID,
    tk.TrackID=c.TrackID,
    tk.IsMonitoringGenerated=CASE WHEN UPPER(LTRIM(RTRIM(ISNULL(tk.Caller,'')))) IN ('EMS','CMSP') THEN 1 ELSE 0 END
FROM qbr.Ticket tk
JOIN qbr.Customer c
  ON UPPER(LTRIM(RTRIM(ISNULL(tk.CompanyAccount,''))))=UPPER(LTRIM(RTRIM(ISNULL(c.CompanyAccountName,''))))
 AND ISNULL(c.IsActive,1)=1;
GO

/* 6. Report any CompanyAccount that is still unmapped. This should be zero
      for the current THD Data ticket feed. */
SELECT tk.CompanyAccount,COUNT(*) AS TicketCount
FROM qbr.Ticket tk
LEFT JOIN qbr.Customer c
  ON UPPER(LTRIM(RTRIM(ISNULL(tk.CompanyAccount,''))))=UPPER(LTRIM(RTRIM(ISNULL(c.CompanyAccountName,''))))
 AND ISNULL(c.IsActive,1)=1
WHERE c.CustomerID IS NULL
GROUP BY tk.CompanyAccount
ORDER BY TicketCount DESC,tk.CompanyAccount;
GO

/* 7. Final reference output. */
SELECT CustomerID,CompanyAccountName,TowerID,TrackID
FROM qbr.Customer
WHERE ISNULL(IsActive,1)=1
ORDER BY TowerID,TrackID,CompanyAccountName;
GO

PRINT 'Ticket-centric customer mapping migration completed.';
PRINT 'EMS/CMSP tickets are classified through qbr.Ticket.IsMonitoringGenerated.';
PRINT 'qbr.Alert and qbr.TicketAlert remain only for rollback and are not used by the application.';
GO
