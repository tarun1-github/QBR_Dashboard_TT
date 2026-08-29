/*
 QBR V7 - LOCAL SQLITE AUTHENTICATION
 Your current app is using SQLite, so DO NOT use qbr.AppUser here.
 This script is for SQLite-compatible table creation.
 Execute once against the SQLite DB used by app.db.
*/
CREATE TABLE IF NOT EXISTS app_users (
    UserID INTEGER PRIMARY KEY AUTOINCREMENT,
    Username TEXT NOT NULL UNIQUE,
    DisplayName TEXT NOT NULL,
    PasswordHash TEXT NULL,
    RoleName TEXT NOT NULL,
    MustSetPassword INTEGER NOT NULL DEFAULT 1,
    IsActive INTEGER NOT NULL DEFAULT 1,
    FailedLoginCount INTEGER NOT NULL DEFAULT 0,
    LockedUntil TEXT NULL,
    CreatedAt TEXT DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt TEXT NULL
);

INSERT OR IGNORE INTO app_users
(Username,DisplayName,PasswordHash,RoleName,MustSetPassword,IsActive)
VALUES
('ttaneja','Tarun Taneja',NULL,'SUPERUSER',1,1),
('braparthy','Bharat Raparthy',NULL,'SUPERVISOR',1,1),
('vsingh','Vikrant Singh',NULL,'MANAGER',1,1),
('nmahla','Nishant Mahla',NULL,'MANAGER',1,1),
('gsingh','Garima Singh',NULL,'MANAGER',1,1),
('tsaxena','Toshiba Saxena',NULL,'MANAGER',1,1),
('tshukla','Tushar Shukla',NULL,'MANAGER',1,1),
('Skumar','Sandeep Kumar',NULL,'MANAGER',1,1),
('nkalra','Neha Kalra',NULL,'MANAGER',1,1);
