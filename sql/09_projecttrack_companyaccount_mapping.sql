/* QBR Dashboard - ProjectTrack compatibility mapping
   qbr.Customer remains the authoritative business mapping table.
   ProjectTrack receives CompanyAccount as a compatibility column because the
   dashboard analytics layer can use it for CompanyAccount -> Track resolution.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;
BEGIN TRANSACTION;

IF OBJECT_ID('qbr.ProjectTrack','U') IS NULL
BEGIN
    CREATE TABLE qbr.ProjectTrack(
        ProjectTrackID INT IDENTITY PRIMARY KEY,
        ProjectName NVARCHAR(200) NOT NULL,
        TrackName NVARCHAR(100) NOT NULL,
        CompanyAccount NVARCHAR(200) NULL,
        IsActive BIT NOT NULL DEFAULT 1
    );
END
ELSE IF COL_LENGTH('qbr.ProjectTrack','CompanyAccount') IS NULL
BEGIN
    ALTER TABLE qbr.ProjectTrack ADD CompanyAccount NVARCHAR(200) NULL;
END;

/* Keep one business mapping per track/account. */
DECLARE @Map TABLE(TowerName NVARCHAR(100),TrackName NVARCHAR(100),CompanyAccount NVARCHAR(200));
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

UPDATE pt
SET pt.CompanyAccount=m.CompanyAccount,
    pt.ProjectName=CASE WHEN m.TrackName='THD Data' THEN 'THD' ELSE pt.ProjectName END,
    pt.TrackName=m.TrackName,
    pt.IsActive=1
FROM qbr.ProjectTrack pt
JOIN @Map m ON UPPER(LTRIM(RTRIM(pt.TrackName)))=UPPER(m.TrackName);

INSERT INTO qbr.ProjectTrack(ProjectName,TrackName,CompanyAccount,IsActive)
SELECT CASE WHEN m.TrackName='THD Data' THEN 'THD' ELSE m.TrackName END,
       m.TrackName,m.CompanyAccount,1
FROM @Map m
WHERE NOT EXISTS(
    SELECT 1 FROM qbr.ProjectTrack pt
    WHERE UPPER(LTRIM(RTRIM(pt.TrackName)))=UPPER(m.TrackName)
      AND UPPER(LTRIM(RTRIM(ISNULL(pt.CompanyAccount,''))))=UPPER(m.CompanyAccount)
);

/* Normalize any Home* account in ProjectTrack too. */
UPDATE qbr.ProjectTrack
SET CompanyAccount='Home Depot'
WHERE UPPER(LTRIM(RTRIM(ISNULL(CompanyAccount,'')))) LIKE '%HOME%';

COMMIT TRANSACTION;

SELECT ProjectTrackID,ProjectName,TrackName,CompanyAccount,IsActive
FROM qbr.ProjectTrack
WHERE IsActive=1
ORDER BY ProjectTrackID;
