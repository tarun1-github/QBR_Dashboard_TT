/* Run ONLY after ttaneja login is confirmed. */
DELETE FROM qbr.UserTrackAccess WHERE UserID=(SELECT UserID FROM qbr.AppUser WHERE Username='tarun');
DELETE FROM qbr.PasswordAudit WHERE UserID=(SELECT UserID FROM qbr.AppUser WHERE Username='tarun');
DELETE FROM qbr.PasswordResetToken WHERE UserID=(SELECT UserID FROM qbr.AppUser WHERE Username='tarun');
DELETE FROM qbr.AppUser WHERE Username='tarun';
