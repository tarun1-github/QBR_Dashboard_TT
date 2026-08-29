/*
 ServiceNow raw-load reference.
 Python ingestion should insert into qbr.Ticket using parameterized SQL.
 ProjectName/TrackName are resolved from qbr.ProjectTrack mapping.
*/
IF OBJECT_ID('qbr.Stg_ServiceNow','U') IS NULL
CREATE TABLE qbr.Stg_ServiceNow(
 Number NVARCHAR(50), ParentIncident NVARCHAR(50),
 CompanyAccount NVARCHAR(150), AssignmentGroup NVARCHAR(150),
 ConfigurationItem NVARCHAR(255), State NVARCHAR(100),
 Priority NVARCHAR(50), Opened DATETIME2, Created DATETIME2, Updated DATETIME2,
 CandidateForVE NVARCHAR(50), CMSVETimesavedMinutes DECIMAL(18,2),
 CauseResolution NVARCHAR(MAX), SourceFile NVARCHAR(260), LoadBatchID UNIQUEIDENTIFIER
);
GO
