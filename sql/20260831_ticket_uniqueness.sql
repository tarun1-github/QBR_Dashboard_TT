/*
 QBR Ticket uniqueness protection
 Date: 2026-08-31

 Purpose:
   Prevent duplicate business tickets in qbr.Ticket at the database layer.

 Application loader already performs duplicate detection and existing-ticket
 checks. This migration adds the final database-level guard.

 Design:
   TicketNumberKey is a normalized persisted computed column.
   A CHECK constraint prevents NULL/blank TicketNumber values.
   A UNIQUE index is then created on TicketNumberKey.

 IMPORTANT:
   Validation must return zero rows before the constraint/index section is run.
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

/* 3. Add normalized persisted key if it does not already exist */
IF COL_LENGTH('qbr.Ticket', 'TicketNumberKey') IS NULL
BEGIN
    ALTER TABLE qbr.Ticket
    ADD TicketNumberKey AS UPPER(LTRIM(RTRIM(TicketNumber))) PERSISTED;
END;
GO

/* 4. Prevent future NULL/blank TicketNumber values */
IF NOT EXISTS
(
    SELECT 1
    FROM sys.check_constraints
    WHERE parent_object_id = OBJECT_ID('qbr.Ticket', 'U')
      AND name = 'CK_Ticket_TicketNumber_NotBlank'
)
BEGIN
    ALTER TABLE qbr.Ticket
    ADD CONSTRAINT CK_Ticket_TicketNumber_NotBlank
        CHECK (TicketNumber IS NOT NULL AND LTRIM(RTRIM(TicketNumber)) <> '');
END;
GO

/* 5. Enforce uniqueness on the normalized key.
      No filtered index is used because SQL Server does not allow a computed
      column in a filtered-index predicate. The CHECK constraint above makes
      the key non-NULL/non-blank for every valid row. */
IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('qbr.Ticket', 'U')
      AND name = 'UX_Ticket_TicketNumberKey'
)
BEGIN
    CREATE UNIQUE NONCLUSTERED INDEX UX_Ticket_TicketNumberKey
        ON qbr.Ticket (TicketNumberKey);
END;
GO

/* 6. Verify */
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

/* 7. Verify the CHECK constraint */
SELECT
    name AS ConstraintName,
    is_disabled,
    definition
FROM sys.check_constraints
WHERE parent_object_id = OBJECT_ID('qbr.Ticket', 'U')
  AND name = 'CK_Ticket_TicketNumber_NotBlank';
GO
