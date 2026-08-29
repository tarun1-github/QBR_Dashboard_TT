USE CPDB;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.server_principals
    WHERE name = 'qbr_app'
)
BEGIN
    CREATE LOGIN [qbr_app]
    WITH PASSWORD = 'YOUR_STRONG_PASSWORD';
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.database_principals
    WHERE name = 'qbr_app'
)
BEGIN
    CREATE USER [qbr_app]
    FOR LOGIN [qbr_app];
END
GO

ALTER ROLE db_datareader ADD MEMBER [qbr_app];
ALTER ROLE db_datawriter ADD MEMBER [qbr_app];
GO