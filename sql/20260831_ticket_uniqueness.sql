/*
 QBR Ticket uniqueness protection
 Date: 2026-08-31

 Purpose:
   Prevent duplicate business tickets in qbr.Ticket at the database layer.

 Application loader already performs duplicate detection and existing-ticket
 checks. This migration adds the final database-level guard.

 IMPORTANT:
   Run the validation queries first. Do not execute the CREATE INDEX section
   until validation returns zero duplicate/blank TicketNumber keys.
*/

USE [CPDB];
GO

/* 1. Validate normalized duplicates */
SELECT
    UPPER(LTRIM(RTRIM(TicketNumber))) AS TicketNumberKey,
    COUNT(*) AS RecordCount
FROM qbr.Ticket
WHERE TicketNumber IS NOT NULL
  AND LTRIM(RTRIM(TicketNumber)) <> ''
GROUP BY UPPER(LTRIM(RTRIM(TicketNumber)))
HAVING COUNT(*) > 1
ORDER BY RecordCount DESC;
GO

/* 2. Validate blank/null TicketNumber rows */
SELECT COUNT(*) AS BlankOrNullTicketNumbers
FROM qbr.Ticket
WHERE TicketNumber IS NULL
   OR LTRIM(RTRIM(TicketNumber)) = '';
GO

/* 3. Add normalized persisted key only if it does not already exist */
IF COL_LENGTH('qbr.Ticket', 'TicketNumberKey') IS NULL
BEGIN
    ALTER TABLE qbr.Ticket
    ADD TicketNumberKey AS UPPER(LTRIM(RTRIM(TicketNumber))) PERSISTED;
END;
GO

/* 4. Enforce uniqueness for meaningful ticket numbers */
IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('qbr.Ticket', 'U')
      AND name = 'UX_Ticket_TicketNumberKey'
)
BEGIN
    CREATE UNIQUE NONCLUSTERED INDEX UX_Ticket_TicketNumberKey
        ON qbr.Ticket (TicketNumberKey)
        WHERE TicketNumberKey IS NOT NULL
          AND TicketNumberKey <> '';
END;
GO

/* 5. Verify */
SELECT
    i.name AS IndexName,
    i.is_unique,
    i.type_desc,
    c.name AS ColumnName
FROM sys.indexes i
JOIN sys.index_columns ic
  ON ic.object_id = i.object_id
 AND ic.index_id = i.index_id
JOIN sys.columns c
  ON c.object_id = ic.object_id
 AND c.column_id = ic.column_id
WHERE i.object_id = OBJECT_ID('qbr.Ticket', 'U')
  AND i.name = 'UX_Ticket_TicketNumberKey';
GO
