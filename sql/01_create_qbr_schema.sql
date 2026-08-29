/*
 QBR Ticket & Alert Analytics - SQL Server
*/
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name='qbr') EXEC('CREATE SCHEMA qbr');
GO
IF OBJECT_ID('qbr.ProjectTrack','U') IS NULL
CREATE TABLE qbr.ProjectTrack(
 ProjectTrackID INT IDENTITY PRIMARY KEY,
 ProjectName NVARCHAR(100) NOT NULL,
 TrackName NVARCHAR(100) NOT NULL,
 IsActive BIT NOT NULL DEFAULT 1,
 CONSTRAINT UQ_ProjectTrack UNIQUE(ProjectName,TrackName)
);
GO
IF OBJECT_ID('qbr.Ticket','U') IS NULL
CREATE TABLE qbr.Ticket(
 TicketKey BIGINT IDENTITY PRIMARY KEY,
 TicketNumber NVARCHAR(50) NOT NULL UNIQUE,
 ParentTicketNumber NVARCHAR(50) NULL,
 TicketType NVARCHAR(20) NOT NULL,
 ProjectName NVARCHAR(100) NULL,
 TrackName NVARCHAR(100) NULL,
 AssignmentGroup NVARCHAR(150) NULL,
 CompanyAccount NVARCHAR(150) NULL,
 ConfigurationItem NVARCHAR(255) NULL,
 Service NVARCHAR(150) NULL,
 Part NVARCHAR(150) NULL,
 Priority NVARCHAR(50) NULL,
 State NVARCHAR(100) NULL,
 OpenedAt DATETIME2 NULL,
 CreatedAt DATETIME2 NULL,
 UpdatedAt DATETIME2 NULL,
 ClosedAt DATETIME2 NULL,
 CandidateForVE NVARCHAR(50) NULL,
 VETimeSavedMinutes DECIMAL(18,2) NULL,
 CauseResolution NVARCHAR(MAX) NULL,
 SourceFile NVARCHAR(260) NULL,
 LoadBatchID UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID(),
 LoadedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
IF OBJECT_ID('qbr.Alert','U') IS NULL
CREATE TABLE qbr.Alert(
 AlertKey BIGINT IDENTITY PRIMARY KEY,
 AlertID NVARCHAR(100) NOT NULL UNIQUE,
 AlertTime DATETIME2 NOT NULL,
 ProjectName NVARCHAR(100) NULL,
 TrackName NVARCHAR(100) NULL,
 Service NVARCHAR(150) NULL,
 Part NVARCHAR(150) NULL,
 AlertType NVARCHAR(200) NULL,
 Severity NVARCHAR(50) NULL,
 MonitoringTool NVARCHAR(100) NOT NULL DEFAULT 'NZG2',
 SourceFile NVARCHAR(260) NULL,
 LoadBatchID UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID(),
 LoadedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
IF OBJECT_ID('qbr.TicketAlert','U') IS NULL
CREATE TABLE qbr.TicketAlert(
 TicketAlertKey BIGINT IDENTITY PRIMARY KEY,
 TicketNumber NVARCHAR(50) NOT NULL,
 AlertID NVARCHAR(100) NOT NULL,
 RelationshipType NVARCHAR(100) NULL,
 CorrelationMethod NVARCHAR(100) NULL,
 CorrelationConfidence DECIMAL(5,2) NULL,
 CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
 CONSTRAINT UQ_TicketAlert UNIQUE(TicketNumber,AlertID)
);
GO
IF OBJECT_ID('qbr.AppUser','U') IS NULL
CREATE TABLE qbr.AppUser(
 UserID INT IDENTITY PRIMARY KEY,
 Username NVARCHAR(150) NOT NULL UNIQUE,
 DisplayName NVARCHAR(200),
 PasswordHash NVARCHAR(500) NOT NULL,
 RoleName NVARCHAR(50) NOT NULL,
 IsActive BIT NOT NULL DEFAULT 1,
 ManagerUserID INT NULL,
 CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
IF OBJECT_ID('qbr.UserTrackAccess','U') IS NULL
CREATE TABLE qbr.UserTrackAccess(
 UserTrackAccessID INT IDENTITY PRIMARY KEY,
 UserID INT NOT NULL,
 ProjectTrackID INT NOT NULL,
 CanView BIT NOT NULL DEFAULT 1,
 CanExport BIT NOT NULL DEFAULT 0,
 CONSTRAINT UQ_UserTrack UNIQUE(UserID,ProjectTrackID)
);
GO
IF OBJECT_ID('qbr.RefreshLog','U') IS NULL
CREATE TABLE qbr.RefreshLog(
 RefreshID BIGINT IDENTITY PRIMARY KEY,
 LoadBatchID UNIQUEIDENTIFIER NOT NULL,
 SourceName NVARCHAR(100) NOT NULL,
 StartedAt DATETIME2 NOT NULL,
 FinishedAt DATETIME2 NULL,
 RowsRead INT NULL,
 RowsLoaded INT NULL,
 Status NVARCHAR(30) NOT NULL,
 ErrorMessage NVARCHAR(MAX) NULL
);
GO
MERGE qbr.ProjectTrack AS t
USING (VALUES
('BOA EV','Collab'),('HSBC','Collab'),('Problem Management','Collab'),
('RIL','Non CMS'),('Cybersecurity','Security'),('SFNOC','Foundation'),
('THD','Data Foundation'),('BOA TP','Collab'),('GTM TP','Collab'),
('HD Voice (Bgl)','Collab'),('HSBC Data','Foundation'),('SCNOC','Collab'),
('DC-ACI','Security'),('Infra','Security'),('SOC','Security')
) s(ProjectName,TrackName)
ON t.ProjectName=s.ProjectName AND t.TrackName=s.TrackName
WHEN NOT MATCHED THEN INSERT(ProjectName,TrackName) VALUES(s.ProjectName,s.TrackName);
GO
CREATE INDEX IX_Ticket_ProjectTrackDate ON qbr.Ticket(ProjectName,TrackName,OpenedAt);
CREATE INDEX IX_Ticket_Parent ON qbr.Ticket(ParentTicketNumber);
CREATE INDEX IX_Alert_ProjectTrackTime ON qbr.Alert(ProjectName,TrackName,AlertTime);
CREATE INDEX IX_TicketAlert_Ticket ON qbr.TicketAlert(TicketNumber);
CREATE INDEX IX_TicketAlert_Alert ON qbr.TicketAlert(AlertID);
