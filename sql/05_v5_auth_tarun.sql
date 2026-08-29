/*
 QBR V5 AUTHENTICATION PATCH
 Run ONLY this file now.
 Existing qbr.AppUser is the login table; a separate dlogin table is NOT required.
 This patch adds Tarun's alias ttaneja and prepares first-login password flow.
*/

IF NOT EXISTS (SELECT 1 FROM qbr.AppUser WHERE Username='ttaneja')
BEGIN
    INSERT INTO qbr.AppUser
        (Username,DisplayName,PasswordHash,RoleName,MustSetPassword,IsActive,FailedLoginCount)
    VALUES
        ('ttaneja','Tarun Taneja',NULL,'SUPERUSER',1,1,0);
END
ELSE
BEGIN
    UPDATE qbr.AppUser
    SET DisplayName='Tarun Taneja',
        RoleName='SUPERUSER',
        IsActive=1,
        MustSetPassword=CASE WHEN PasswordHash IS NULL THEN 1 ELSE MustSetPassword END
    WHERE Username='ttaneja';
END
GO

/* Make sure all requested first-time users have no preset password. */
UPDATE qbr.AppUser
SET MustSetPassword=1
WHERE Username IN
('ttaneja','braparthy','vsingh','nmahla','gsingh','tsaxena','tshukla','Skumar','nkalra')
  AND PasswordHash IS NULL;
GO
