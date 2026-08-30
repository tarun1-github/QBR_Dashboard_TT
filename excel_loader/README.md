# QBR Excel Data Loader

This folder contains the Excel/VBA + Power Query starter implementation for the QBR ticket loader.

## Files

- `QBR_LoadData.bas` - VBA module. Imports one or more QBR Excel files, keeps the ticket fields, normalizes CompanyAccount, classifies EMS/CMSP callers, applies Customer -> Tower -> Track mapping, detects duplicates, and builds load-report sheets.
- `QBR_Tickets_PowerQuery.pq` - Power Query M template for the same normalization rules.

## Business rules

1. Input files are normally `Created_tickets.xlsx` and `Closed_tickets.xlsx`.
2. Ticket number is required. Blank ticket numbers are invalid.
3. Duplicate TicketNumber values are sent to Duplicate Records.
4. If CompanyAccount contains `Home` (case-insensitive), it is normalized to `Home Depot`.
5. Customer mapping supplies TowerName and TrackName.
6. Caller containing `EMS` or `CMSP` is classified as Monitoring; all other callers are User.
7. Legacy input field `Part` is accepted and normalized to `Device`.
8. The loader preserves the QBR ticket-centric fields used by the current application: TicketNumber, ParentTicketNumber, TicketType, ProjectName, TrackName, AssignmentGroup, CompanyAccount, CustomerName, TowerName, ConfigurationItem, Service, Device, Caller, Priority, State, Impact, ShortDescription, OpenedAt, CreatedAt, UpdatedAt, ClosedAt, CandidateForVE, VETimeSavedMinutes, ResolutionCode, CauseCode, SourceFile, IsMonitoringGenerated.

## Excel setup

1. Create a blank macro-enabled workbook: `QBR_Data_Loader.xlsm`.
2. Open Excel -> Developer -> Visual Basic.
3. Insert -> Module.
4. Copy the contents of `QBR_LoadData.bas` into the module.
5. Run `SetupQBRLoader` once.
6. On `Load Control`, click `SELECT FILES` and select one or more Created/Closed Excel files.
7. Click `LOAD DATA`.
8. Review `Load Summary`, `Loaded Records`, `Duplicate Records`, `Invalid Records`, `Unmapped Company`, and `Errors`.

## Dummy-data test

Use dummy copies of the Created/Closed files. Include at least:

- one normal user ticket with caller `engineer1`
- one monitoring ticket with caller `EMS Controller Events`
- one monitoring ticket with caller `ems_splunk_homd1`
- one monitoring ticket with caller `CMSP`
- one company value such as `Domain HomeDepot` to verify normalization to `Home Depot`
- one duplicate TicketNumber
- one blank TicketNumber
- one unmapped company
- one legacy `Part` column instead of `Device`

No production data is embedded in this repository.

## Important

The VBA workbook is intentionally separate from the Python/Streamlit Docker application. It is an Excel-side ingestion/testing tool. The next milestone can connect its output to the QBR SQL database through an approved API/import mechanism rather than giving Excel direct production database credentials.
