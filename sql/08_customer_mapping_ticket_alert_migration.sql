/*
 QBR Dashboard - Customer Mapping + Ticket/Alert Field Migration
 ================================================================
 Purpose:
   1. Make qbr.Customer the authoritative CompanyAccount -> Tower -> Track map.
   2. Normalize any CompanyAccount containing "Home" to "Home Depot".
   3. Ensure Foundation has SFNOC, THD Data and HSBC Data.
   4. Rename Part -> Device on Ticket and Alert.
   5. Preserve Caller so EMS/CMSP monitoring-generated tickets can be identified.
   6. Backfill existing Ticket TowerID/TrackID/CustomerID from the mapping table.

 Run this once in CPDB before running the updated load_data.py.
*/

SET NOCOUNT ON;
SET XACT_ABORT ON;
BEGIN TRANSACTION;

/* ------------------------------------------------------------
   1. Reference towers
------------------------------------------------------------ */
IF OBJECT_ID('qbr.Tower','U') IS NULL
BEGIN
    CREATE TABLE qbr.Tower(
        TowerID INT IDENTITY PRIMARY KEY,
        TowerName NVARCHAR(100) NOT NULL UNIQUE,
        TowerDescription NVARCHAR(500) NULL,
        DisplayOrder INT NOT NULL DEFAULT 0,
        IsActive BIT NOT NULL DEFAULT 1,
        CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
END;

INSERT INTO qbr.Tower (TowerName,DisplayOrder)
SELECT v.TowerName,v.DisplayOrder
FROM (VALUES
    ('Collaboration',1),('Foundation',2),('Security',3),('Non-CMS',4)
) v(TowerName,DisplayOrder)
WHERE NOT EXISTS (SELECT 1 FROM qbr.Tower t WHERE UPPER(t.TowerName)=UPPER(v.TowerName));

/* ------------------------------------------------------------
   2. Reference tracks - business names are authoritative
------------------------------------------------------------ */
IF OBJECT_ID('qbr.Track','U') IS NULL
BEGIN
    CREATE TABLE qbr.Track(
        TrackID INT IDENTITY PRIMARY KEY,
        TowerID INT NOT NULL FOREIGN KEY REFERENCES qbr.Tower(TowerID),
        TrackName NVARCHAR(100) NOT NULL,
        TrackDescription NVARCHAR(500) NULL,
        DisplayOrder INT NOT NULL DEFAULT 0,
        IsActive BIT NOT NULL DEFAULT 1,
        CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_TowerTrack UNIQUE(TowerID,TrackName)
    );
END;

/* Normalize the old Foundation label if present. */
IF EXISTS (
    SELECT 1 FROM qbr.Track tr
    JOIN qbr.Tower tw ON tw.TowerID=tr.TowerID
    WHERE UPPER(tw.TowerName)='FOUNDATION'
      AND UPPER(LTRIM(RTRIM(tr.TrackName))) IN ('DATA FOUNDATION','THD','THD DATA')
)
AND NOT EXISTS (
    SELECT 1 FROM qbr.Track tr
    JOIN qbr.Tower tw ON tw.TowerID=tr.TowerID
    WHERE UPPER(tw.TowerName)='FOUNDATION'
      AND UPPER(LTRIM(RTRIM(tr.TrackName)))='THD DATA'
)
BEGIN
    UPDATE tr SET TrackName='THD Data'
    FROM qbr.Track tr
    JOIN qbr.Tower tw ON tw.TowerID=tr.TowerID
    WHERE UPPER(tw.TowerName)='FOUNDATION'
      AND UPPER(LTRIM(RTRIM(tr.TrackName))) IN ('DATA FOUNDATION','THD','THD DATA');
END;

INSERT INTO qbr.Track (TowerID,TrackName,DisplayOrder)
SELECT tw.TowerID,v.TrackName,v.DisplayOrder
FROM (VALUES
 ('Collaboration','BOA EV',1),
 ('Collaboration','HSBC',2),
 ('Collaboration','Problem Management',3),
 ('Collaboration','BOA TP',4),
 ('Collaboration','GTM TP',5),
 ('Collaboration','HD Voice (Bgl)',6),
 ('Collaboration','SCNOC',7),
 ('Security','Cybersecurity',1),
 ('Security','DC-ACI',2),
 ('Security','Infra',3),
 ('Security','SOC',4),
 ('Foundation','SFNOC',1),
 ('Foundation','THD Data',2),
 ('Foundation','HSBC Data',3),
 ('Non-CMS','RIL',1)
) v(TowerName,TrackName,DisplayOrder)
JOIN qbr.Tower tw ON UPPER(tw.TowerName)=UPPER(v.TowerName)
WHERE NOT EXISTS (
    SELECT 1 FROM qbr.Track tr
    WHERE tr.TowerID=tw.TowerID AND UPPER(LTRIM(RTRIM(tr.TrackName)))=UPPER(v.TrackName)
);

/* ------------------------------------------------------------
   3. Customer mapping table
------------------------------------------------------------ */
IF OBJECT_ID('qbr.Customer','U') IS NULL
BEGIN
    CREATE TABLE qbr.Customer(
        CustomerID INT IDENTITY PRIMARY KEY,
        CustomerName NVARCHAR(200) NOT NULL UNIQUE,
        CustomerCode NVARCHAR(50) NULL,
        CompanyAccountName NVARCHAR(200) NULL,
        TowerID INT NULL FOREIGN KEY REFERENCES qbr.Tower(TowerID),
        TrackID INT NULL FOREIGN KEY REFERENCES qbr.Track(TrackID),
        IsActive BIT NOT NULL DEFAULT 1,
        CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
END
ELSE
BEGIN
    IF COL_LENGTH('qbr.Customer','CompanyAccountName') IS NULL
        ALTER TABLE qbr.Customer ADD CompanyAccountName NVARCHAR(200) NULL;
    IF COL_LENGTH('qbr.Customer','TowerID') IS NULL
        ALTER TABLE qbr.Customer ADD TowerID INT NULL;
    IF COL_LENGTH('qbr.Customer','TrackID') IS NULL
        ALTER TABLE qbr.Customer ADD TrackID INT NULL;
END;

/* Seed/update the exact business mapping supplied for QBR. */
DECLARE @Map TABLE(
    TowerName NVARCHAR(100),
    TrackName NVARCHAR(100),
    CompanyAccountName NVARCHAR(200)
);
INSERT INTO @Map VALUES
 ('Collaboration','BOA EV','Bank of America'),
 ('Collaboration','HSBC','HSBC'),
 ('Collaboration','Problem Management','Problem Management'),
 ('Collaboration','BOA TP','BOA TP'),
 ('Collaboration','GTM TP','GTM TP'),
 ('Collaboration','HD Voice (Bgl)','HD Voice (Bgl)'),
 ('Collaboration','SCNOC','SCNOC'),
 ('Security','Cybersecurity','Cybersecurity'),
 ('Security','DC-ACI','DC-ACI'),
 ('Security','Infra','Infra'),
 ('Security','SOC','SOC'),
 ('Foundation','SFNOC','SFNOC'),
 ('Foundation','THD Data','Home Depot'),
 ('Foundation','HSBC Data','HSBC Data'),
 ('Non-CMS','RIL','RIL');

UPDATE c
SET c.CustomerName=m.CompanyAccountName,
    c.CompanyAccountName=m.CompanyAccountName,
    c.TowerID=tw.TowerID,
    c.TrackID=tr.TrackID,
    c.IsActive=1
FROM qbr.Customer c
JOIN @Map m ON UPPER(LTRIM(RTRIM(ISNULL(c.CompanyAccountName,c.CustomerName))))=UPPER(m.CompanyAccountName)
JOIN qbr.Tower tw ON UPPER(tw.TowerName)=UPPER(m.TowerName)
JOIN qbr.Track tr ON tr.TowerID=tw.TowerID AND UPPER(tr.TrackName)=UPPER(m.TrackName);

INSERT INTO qbr.Customer(CustomerName,CompanyAccountName,TowerID,TrackID,IsActive)
SELECT m.CompanyAccountName,m.CompanyAccountName,tw.TowerID,tr.TrackID,1
FROM @Map m
JOIN qbr.Tower tw ON UPPER(tw.TowerName)=UPPER(m.TowerName)
JOIN qbr.Track tr ON tr.TowerID=tw.TowerID AND UPPER(tr.TrackName)=UPPER(m.TrackName)
WHERE NOT EXISTS (
    SELECT 1 FROM qbr.Customer c
    WHERE UPPER(LTRIM(RTRIM(ISNULL(c.CompanyAccountName,c.CustomerName))))=UPPER(m.CompanyAccountName)
);

/* ------------------------------------------------------------
   4. Ticket fields: Part -> Device, plus Caller
------------------------------------------------------------ */
IF OBJECT_ID('qbr.Ticket','U') IS NOT NULL
BEGIN
    IF COL_LENGTH('qbr.Ticket','Device') IS NULL AND COL_LENGTH('qbr.Ticket','Part') IS NOT NULL
        EXEC sp_rename 'qbr.Ticket.Part','Device','COLUMN';
    ELSE IF COL_LENGTH('qbr.Ticket','Device') IS NULL
        ALTER TABLE qbr.Ticket ADD Device NVARCHAR(150) NULL;

    IF COL_LENGTH('qbr.Ticket','Caller') IS NULL
        ALTER TABLE qbr.Ticket ADD Caller NVARCHAR(150) NULL;

    IF COL_LENGTH('qbr.Ticket','IsMonitoringGenerated') IS NULL
        ALTER TABLE qbr.Ticket ADD IsMonitoringGenerated BIT NOT NULL CONSTRAINT DF_Ticket_IsMonitoringGenerated DEFAULT(0);
END;

/* ------------------------------------------------------------
   5. Alert fields: Part -> Device, plus Caller
------------------------------------------------------------ */
IF OBJECT_ID('qbr.Alert','U') IS NOT NULL
BEGIN
    IF COL_LENGTH('qbr.Alert','Device') IS NULL AND COL_LENGTH('qbr.Alert','Part') IS NOT NULL
        EXEC sp_rename 'qbr.Alert.Part','Device','COLUMN';
    ELSE IF COL_LENGTH('qbr.Alert','Device') IS NULL
        ALTER TABLE qbr.Alert ADD Device NVARCHAR(150) NULL;

    IF COL_LENGTH('qbr.Alert','Caller') IS NULL
        ALTER TABLE qbr.Alert ADD Caller NVARCHAR(150) NULL;
END;

/* ------------------------------------------------------------
   6. Normalize ticket company accounts.
      User requirement: any CompanyAccount containing Home => Home Depot.
------------------------------------------------------------ */
IF OBJECT_ID('qbr.Ticket','U') IS NOT NULL
BEGIN
    UPDATE qbr.Ticket
    SET CompanyAccount='Home Depot'
    WHERE CompanyAccount IS NOT NULL
      AND UPPER(LTRIM(RTRIM(CompanyAccount))) LIKE '%HOME%';

    UPDATE tk
    SET tk.CustomerID=c.CustomerID,
        tk.TowerID=c.TowerID,
        tk.TrackID=c.TrackID
    FROM qbr.Ticket tk
    JOIN qbr.Customer c
      ON UPPER(LTRIM(RTRIM(ISNULL(tk.CompanyAccount,''))))=
         UPPER(LTRIM(RTRIM(ISNULL(c.CompanyAccountName,c.CustomerName))));
END;

/* ------------------------------------------------------------
   7. Classify monitoring-generated tickets.
      EMS/CMSP = monitoring generated; everything else = user ticket.
------------------------------------------------------------ */
IF OBJECT_ID('qbr.Ticket','U') IS NOT NULL AND COL_LENGTH('qbr.Ticket','Caller') IS NOT NULL
BEGIN
    UPDATE qbr.Ticket
    SET Caller=LTRIM(RTRIM(Caller)),
        IsMonitoringGenerated=CASE WHEN UPPER(LTRIM(RTRIM(ISNULL(Caller,'')))) IN ('EMS','CMSP') THEN 1 ELSE 0 END;
END;

/* ------------------------------------------------------------
   8. Useful indexes
------------------------------------------------------------ */
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_Ticket_CompanyAccount' AND object_id=OBJECT_ID('qbr.Ticket'))
    CREATE INDEX IX_Ticket_CompanyAccount ON qbr.Ticket(CompanyAccount);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_Ticket_Caller' AND object_id=OBJECT_ID('qbr.Ticket'))
    CREATE INDEX IX_Ticket_Caller ON qbr.Ticket(Caller);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_Customer_CompanyAccount' AND object_id=OBJECT_ID('qbr.Customer'))
    CREATE INDEX IX_Customer_CompanyAccount ON qbr.Customer(CompanyAccountName);

COMMIT TRANSACTION;

/* Verification */
SELECT TowerName,TrackName FROM qbr.TowerTrack WHERE IsActive=1 ORDER BY TowerName,TrackName;
SELECT CustomerName,CompanyAccountName,tw.TowerName,tr.TrackName
FROM qbr.Customer c
LEFT JOIN qbr.Tower tw ON tw.TowerID=c.TowerID
LEFT JOIN qbr.Track tr ON tr.TrackID=c.TrackID
WHERE c.IsActive=1
ORDER BY tw.DisplayOrder,tr.DisplayOrder,c.CustomerName;

SELECT COUNT(*) AS TicketRows,
       SUM(CASE WHEN UPPER(LTRIM(RTRIM(ISNULL(Caller,'')))) IN ('EMS','CMSP') THEN 1 ELSE 0 END) AS MonitoringGeneratedTickets,
       SUM(CASE WHEN UPPER(LTRIM(RTRIM(ISNULL(Caller,'')))) NOT IN ('EMS','CMSP') OR Caller IS NULL THEN 1 ELSE 0 END) AS UserTickets
FROM qbr.Ticket;
