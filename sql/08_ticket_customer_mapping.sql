/*
 QBR Dashboard - Ticket-centric mapping model

 Purpose:
   1. qbr.Ticket is the single fact table.
   2. qbr.Customer is the CompanyAccount -> Tower -> Track mapping table.
   3. Caller = EMS/CMSP identifies monitoring-generated tickets.
   4. qbr.Alert / qbr.TicketAlert are no longer required by the application.
      They are intentionally NOT dropped in this migration; remove them only
      after the new dashboard has been validated in production.
*/

SET NOCOUNT ON;

/* ------------------------------------------------------------
   1. Extend Customer into the authoritative account mapping table
   ------------------------------------------------------------ */
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('qbr.Customer') AND name='CompanyAccountName')
    ALTER TABLE qbr.Customer ADD CompanyAccountName NVARCHAR(200) NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('qbr.Customer') AND name='TowerID')
    ALTER TABLE qbr.Customer ADD TowerID INT NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('qbr.Customer') AND name='TrackID')
    ALTER TABLE qbr.Customer ADD TrackID INT NULL;
GO

/* Existing CustomerName becomes the initial account name where possible. */
UPDATE qbr.Customer
SET CompanyAccountName = COALESCE(NULLIF(LTRIM(RTRIM(CompanyAccountName)),''), NULLIF(LTRIM(RTRIM(CustomerName)),''))
WHERE CompanyAccountName IS NULL OR LTRIM(RTRIM(CompanyAccountName))='';
GO

/* ------------------------------------------------------------
   2. Ensure the 15 business mappings exist.
      Home Depot is the normalized account for all values containing Home.
   ------------------------------------------------------------ */
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
    WHERE UPPER(LTRIM(RTRIM(ISNULL(c.CompanyAccountName,'')))) = UPPER(m.CompanyAccountName)
);
GO

/* Fix the historical typo / normalize Home Depot and refresh all mappings. */
UPDATE c
SET c.CompanyAccountName='Home Depot', c.CustomerName='Home Depot', c.TowerID=tw.TowerID, c.TrackID=tr.TrackID, c.IsActive=1
FROM qbr.Customer c
JOIN qbr.Tower tw ON tw.TowerName='Foundation'
JOIN qbr.Track tr ON tr.TowerID=tw.TowerID AND tr.TrackName='THD Data'
WHERE UPPER(LTRIM(RTRIM(ISNULL(c.CompanyAccountName,c.CustomerName)))) IN ('DOME DEPOT','HOME DEPOT','THE HOME DEPOT','THD');
GO

UPDATE c
SET c.TowerID=tw.TowerID, c.TrackID=tr.TrackID, c.IsActive=1
FROM qbr.Customer c
JOIN qbr.Tower tw ON UPPER(tw.TowerName)=UPPER(
    CASE UPPER(LTRIM(RTRIM(ISNULL(c.CompanyAccountName,c.CustomerName))))
      WHEN 'BANK OF AMERICA' THEN 'Collaboration'
      WHEN 'BOA EV' THEN 'Collaboration'
      WHEN 'HSBC' THEN 'Collaboration'
      WHEN 'PROBLEM MANAGEMENT' THEN 'Collaboration'
      WHEN 'BOA TP' THEN 'Collaboration'
      WHEN 'GTM TP' THEN 'Collaboration'
      WHEN 'HD VOICE (BGL)' THEN 'Collaboration'
      WHEN 'SCNOC' THEN 'Collaboration'
      WHEN 'CYBERSECURITY' THEN 'Security'
      WHEN 'DC-ACI' THEN 'Security'
      WHEN 'INFRA' THEN 'Security'
      WHEN 'SOC' THEN 'Security'
      WHEN 'SFNOC' THEN 'Foundation'
      WHEN 'HSBC DATA' THEN 'Foundation'
      WHEN 'RIL' THEN 'Non-CMS'
      ELSE '' END)
JOIN qbr.Track tr ON tr.TowerID=tw.TowerID AND UPPER(tr.TrackName)=UPPER(
    CASE UPPER(LTRIM(RTRIM(ISNULL(c.CompanyAccountName,c.CustomerName))))
      WHEN 'BANK OF AMERICA' THEN 'BOA EV'
      WHEN 'BOA EV' THEN 'BOA EV'
      WHEN 'HSBC' THEN 'HSBC'
      WHEN 'PROBLEM MANAGEMENT' THEN 'Problem Management'
      WHEN 'BOA TP' THEN 'BOA TP'
      WHEN 'GTM TP' THEN 'GTM TP'
      WHEN 'HD VOICE (BGL)' THEN 'HD Voice (Bgl)'
      WHEN 'SCNOC' THEN 'SCNOC'
      WHEN 'CYBERSECURITY' THEN 'Cybersecurity'
      WHEN 'DC-ACI' THEN 'DC-ACI'
      WHEN 'INFRA' THEN 'Infra'
      WHEN 'SOC' THEN 'SOC'
      WHEN 'SFNOC' THEN 'SFNOC'
      WHEN 'HSBC DATA' THEN 'HSBC Data'
      WHEN 'RIL' THEN 'RIL'
      ELSE '' END);
GO

/* ------------------------------------------------------------
   3. Ticket columns required by the new model
   ------------------------------------------------------------ */
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('qbr.Ticket') AND name='Caller')
    ALTER TABLE qbr.Ticket ADD Caller NVARCHAR(200) NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('qbr.Ticket') AND name='Device')
    ALTER TABLE qbr.Ticket ADD Device NVARCHAR(200) NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('qbr.Ticket') AND name='IsMonitoringGenerated')
    ALTER TABLE qbr.Ticket ADD IsMonitoringGenerated BIT NULL;
GO

/* Backfill Device from the legacy Part column where present. */
IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('qbr.Ticket') AND name='Part')
    UPDATE qbr.Ticket SET Device=COALESCE(NULLIF(LTRIM(RTRIM(Device)),''),Part) WHERE Device IS NULL OR LTRIM(RTRIM(Device))='';
GO

UPDATE qbr.Ticket
SET IsMonitoringGenerated=CASE WHEN UPPER(LTRIM(RTRIM(ISNULL(Caller,'')))) IN ('EMS','CMSP') THEN 1 ELSE 0 END;
GO

/* ------------------------------------------------------------
   4. Populate Ticket Customer/Tower/Track from CompanyAccount.
      Home / The Home Depot / THD all map to Home Depot -> Foundation -> THD Data.
   ------------------------------------------------------------ */
UPDATE tk
SET tk.CompanyAccount=CASE WHEN UPPER(LTRIM(RTRIM(ISNULL(tk.CompanyAccount,'')))) LIKE '%HOME%' THEN 'Home Depot' ELSE LTRIM(RTRIM(tk.CompanyAccount)) END
FROM qbr.Ticket tk
WHERE tk.CompanyAccount IS NOT NULL;
GO

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

/* ------------------------------------------------------------
   5. Keep ProjectTrack/TowerTrack as reference/access catalogues,
      but Customer is the authoritative CompanyAccount mapping for tickets.
   ------------------------------------------------------------ */
SELECT CustomerID,CompanyAccountName,TowerID,TrackID
FROM qbr.Customer
WHERE ISNULL(IsActive,1)=1
ORDER BY TowerID,TrackID,CompanyAccountName;
GO

PRINT 'Ticket-centric customer mapping migration completed.';
PRINT 'EMS/CMSP tickets are classified through qbr.Ticket.IsMonitoringGenerated.';
PRINT 'qbr.Alert and qbr.TicketAlert are no longer required by the application and were intentionally retained for safe rollback.';
GO
