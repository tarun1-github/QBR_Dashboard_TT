/* QBR Dashboard - final TowerTrack + Customer mapping seed */
SET NOCOUNT ON;
SET XACT_ABORT ON;
BEGIN TRANSACTION;

/* Ensure the complete TowerTrack catalogue exists. */
IF OBJECT_ID('qbr.TowerTrack','U') IS NOT NULL
BEGIN
    DECLARE @TT TABLE(TowerName NVARCHAR(100),TrackName NVARCHAR(100));
    INSERT INTO @TT VALUES
    ('Collaboration','BOA EV'),('Collaboration','HSBC'),('Collaboration','Problem Management'),
    ('Collaboration','BOA TP'),('Collaboration','GTM TP'),('Collaboration','HD Voice (Bgl)'),('Collaboration','SCNOC'),
    ('Security','Cybersecurity'),('Security','DC-ACI'),('Security','Infra'),('Security','SOC'),
    ('Foundation','SFNOC'),('Foundation','THD Data'),('Foundation','HSBC Data'),('Non-CMS','RIL');

    INSERT INTO qbr.TowerTrack(TowerName,TrackName,IsActive)
    SELECT m.TowerName,m.TrackName,1
    FROM @TT m
    WHERE NOT EXISTS(
        SELECT 1 FROM qbr.TowerTrack x
        WHERE UPPER(LTRIM(RTRIM(x.TowerName)))=UPPER(m.TowerName)
          AND UPPER(LTRIM(RTRIM(x.TrackName)))=UPPER(m.TrackName)
    );

    UPDATE qbr.TowerTrack
    SET TrackName='THD Data'
    WHERE UPPER(LTRIM(RTRIM(TowerName)))='FOUNDATION'
      AND UPPER(LTRIM(RTRIM(TrackName))) IN ('THD','DATA FOUNDATION')
      AND NOT EXISTS(
          SELECT 1 FROM qbr.TowerTrack x
          WHERE UPPER(LTRIM(RTRIM(x.TowerName)))='FOUNDATION'
            AND UPPER(LTRIM(RTRIM(x.TrackName)))='THD DATA'
      );
END;

/* Ensure Customer is aligned to the business map. */
UPDATE c SET CompanyAccountName='Home Depot',CustomerName='Home Depot'
FROM qbr.Customer c
WHERE UPPER(LTRIM(RTRIM(ISNULL(c.CompanyAccountName,c.CustomerName)))) LIKE '%HOME%';

UPDATE c
SET c.TowerID=tw.TowerID,c.TrackID=tr.TrackID,c.IsActive=1
FROM qbr.Customer c
JOIN qbr.Tower tw ON UPPER(tw.TowerName)='FOUNDATION'
JOIN qbr.Track tr ON tr.TowerID=tw.TowerID AND UPPER(tr.TrackName)='THD DATA'
WHERE UPPER(LTRIM(RTRIM(ISNULL(c.CompanyAccountName,c.CustomerName))))='HOME DEPOT';

COMMIT TRANSACTION;

SELECT TowerName,TrackName FROM qbr.TowerTrack WHERE IsActive=1 ORDER BY TowerName,TrackName;
