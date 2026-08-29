/*
 QBR DASHBOARD V4 DATABASE CHANGES
 Run this AFTER the original qbr schema script.
 Hierarchy: Tower -> Track -> Time View -> Ticket -> Parent/Child -> Alert
*/

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name='qbr')
    EXEC('CREATE SCHEMA qbr');
GO

IF OBJECT_ID('qbr.TowerTrack','U') IS NULL
BEGIN
    CREATE TABLE qbr.TowerTrack(
        TowerTrackID INT IDENTITY(1,1) PRIMARY KEY,
        TowerName NVARCHAR(100) NOT NULL,
        TrackName NVARCHAR(150) NOT NULL,
        IsActive BIT NOT NULL DEFAULT 1,
        CONSTRAINT UQ_TowerTrack UNIQUE(TowerName,TrackName)
    );
END
GO

MERGE qbr.TowerTrack AS T
USING (VALUES
('Collaboration','BOA EV'),('Collaboration','HSBC'),('Collaboration','Problem Management'),
('Collaboration','BOA TP'),('Collaboration','GTM TP'),('Collaboration','HD Voice (Bgl)'),('Collaboration','SCNOC'),
('Security','Cybersecurity'),('Security','DC-ACI'),('Security','Infra'),('Security','SOC'),
('Foundation','SFNOC'),('Non-CMS','RIL')
) S(TowerName,TrackName)
ON T.TowerName=S.TowerName AND T.TrackName=S.TrackName
WHEN MATCHED THEN UPDATE SET IsActive=1
WHEN NOT MATCHED THEN INSERT(TowerName,TrackName) VALUES(S.TowerName,S.TrackName);
GO

IF OBJECT_ID('qbr.AppUser','U') IS NULL
BEGIN
    CREATE TABLE qbr.AppUser(
        UserID INT IDENTITY(1,1) PRIMARY KEY,
        Username NVARCHAR(100) NOT NULL UNIQUE,
        DisplayName NVARCHAR(200) NOT NULL,
        PasswordHash NVARCHAR(500) NULL,
        RoleName NVARCHAR(50) NOT NULL,
        MustSetPassword BIT NOT NULL DEFAULT 1,
        IsActive BIT NOT NULL DEFAULT 1,
        FailedLoginCount INT NOT NULL DEFAULT 0,
        LockedUntil DATETIME2 NULL,
        CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        UpdatedAt DATETIME2 NULL
    );
END
GO

IF COL_LENGTH('qbr.AppUser','MustSetPassword') IS NULL
    ALTER TABLE qbr.AppUser ADD MustSetPassword BIT NOT NULL CONSTRAINT DF_AppUser_MustSetPassword DEFAULT 1;
GO
IF COL_LENGTH('qbr.AppUser','FailedLoginCount') IS NULL
    ALTER TABLE qbr.AppUser ADD FailedLoginCount INT NOT NULL CONSTRAINT DF_AppUser_FailedLoginCount DEFAULT 0;
GO
IF COL_LENGTH('qbr.AppUser','LockedUntil') IS NULL
    ALTER TABLE qbr.AppUser ADD LockedUntil DATETIME2 NULL;
GO

IF OBJECT_ID('qbr.UserTrackAccess','U') IS NULL
BEGIN
    CREATE TABLE qbr.UserTrackAccess(
        UserTrackAccessID INT IDENTITY(1,1) PRIMARY KEY,
        UserID INT NOT NULL,
        TowerTrackID INT NOT NULL,
        CanView BIT NOT NULL DEFAULT 1,
        CanExport BIT NOT NULL DEFAULT 0,
        CanManage BIT NOT NULL DEFAULT 0,
        CONSTRAINT UQ_UserTowerTrack UNIQUE(UserID,TowerTrackID)
    );
END
GO

IF COL_LENGTH('qbr.UserTrackAccess','TowerTrackID') IS NULL
    ALTER TABLE qbr.UserTrackAccess ADD TowerTrackID INT NULL;
GO
IF COL_LENGTH('qbr.UserTrackAccess','CanManage') IS NULL
    ALTER TABLE qbr.UserTrackAccess ADD CanManage BIT NOT NULL CONSTRAINT DF_UserTrackAccess_CanManage DEFAULT 0;
GO

IF OBJECT_ID('qbr.PasswordResetToken','U') IS NULL
BEGIN
    CREATE TABLE qbr.PasswordResetToken(
        TokenID BIGINT IDENTITY PRIMARY KEY,
        UserID INT NOT NULL,
        TokenHash NVARCHAR(256) NOT NULL,
        ExpiresAt DATETIME2 NOT NULL,
        UsedAt DATETIME2 NULL,
        CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
END
GO

IF OBJECT_ID('qbr.PasswordAudit','U') IS NULL
BEGIN
    CREATE TABLE qbr.PasswordAudit(
        AuditID BIGINT IDENTITY PRIMARY KEY,
        UserID INT NOT NULL,
        ActionName NVARCHAR(50) NOT NULL,
        ActionAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
END
GO

IF OBJECT_ID('qbr.Alert','U') IS NOT NULL AND COL_LENGTH('qbr.Alert','TowerName') IS NULL
    ALTER TABLE qbr.Alert ADD TowerName NVARCHAR(100) NULL;
GO
IF OBJECT_ID('qbr.Ticket','U') IS NOT NULL AND COL_LENGTH('qbr.Ticket','TowerName') IS NULL
    ALTER TABLE qbr.Ticket ADD TowerName NVARCHAR(100) NULL;
GO

/* Seed users. No passwords are stored here: all users must set a password at first login. */
MERGE qbr.AppUser AS T
USING (VALUES
('tarun','Tarun Taneja','SUPERUSER'),
('braparthy','Bharat Raparthy','SUPERVISOR'),
('vsingh','Vikrant Singh','MANAGER'),
('nmahla','Nishant Mahla','MANAGER'),
('gsingh','Garima Singh','MANAGER'),
('tsaxena','Toshiba Saxena','MANAGER'),
('tshukla','Tushar Shukla','MANAGER'),
('Skumar','Sandeep Kumar','MANAGER'),
('nkalra','Neha Kalra','MANAGER')
) S(Username,DisplayName,RoleName)
ON T.Username=S.Username
WHEN MATCHED THEN UPDATE SET DisplayName=S.DisplayName,RoleName=S.RoleName,IsActive=1
WHEN NOT MATCHED THEN
 INSERT(Username,DisplayName,RoleName,MustSetPassword,IsActive)
 VALUES(S.Username,S.DisplayName,S.RoleName,1,1);
GO

/* Supervisors have full access to all active Tower/Track combinations. */
INSERT INTO qbr.UserTrackAccess(UserID,TowerTrackID,CanView,CanExport,CanManage)
SELECT u.UserID,t.TowerTrackID,1,1,1
FROM qbr.AppUser u CROSS JOIN qbr.TowerTrack t
WHERE u.Username IN ('braparthy','tarun') AND t.IsActive=1
AND NOT EXISTS(
 SELECT 1 FROM qbr.UserTrackAccess a
 WHERE a.UserID=u.UserID AND a.TowerTrackID=t.TowerTrackID
);
GO

/* Managers start with access to every current track so each track can be tested.
   Supervisor can later add/delete/update this assignment from the web UI. */
INSERT INTO qbr.UserTrackAccess(UserID,TowerTrackID,CanView,CanExport,CanManage)
SELECT u.UserID,t.TowerTrackID,1,1,0
FROM qbr.AppUser u CROSS JOIN qbr.TowerTrack t
WHERE u.RoleName='MANAGER' AND t.IsActive=1
AND NOT EXISTS(
 SELECT 1 FROM qbr.UserTrackAccess a
 WHERE a.UserID=u.UserID AND a.TowerTrackID=t.TowerTrackID
);
GO

CREATE INDEX IX_TowerTrack_Tower ON qbr.TowerTrack(TowerName,TrackName);
CREATE INDEX IX_UserTrackAccess_User ON qbr.UserTrackAccess(UserID,TowerTrackID);
CREATE INDEX IX_AppUser_Role ON qbr.AppUser(RoleName,IsActive);
GO
