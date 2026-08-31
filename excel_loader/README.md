# QBR Excel Loader Prototype

This folder contains the Windows/Excel prototype for the QBR ticket loader.

## Components

- `VBA/QBR_LoadData.bas` - VBA UI/orchestration module.
- `PowerQuery/QBR_Tickets.pq` - Power Query transformation.
- `PowerQuery/QBR_DataQuality.pq` - invalid-record output.
- `PowerQuery/QBR_Duplicates.pq` - duplicate-record output.
- `PowerQuery/Customer_Mapping.csv` - customer/company/tower/track mapping.
- `DummyData/Created_tickets.csv` and `DummyData/Closed_tickets.csv` - safe dummy data only.

## Business rules

1. Preserve the QBR ticket-centric fields used by the current application.
2. `Part` is accepted as a legacy input alias and normalized to `Device`.
3. Company accounts containing `Home` are normalized to `Home Depot`.
4. Caller containing `EMS` or `CMSP` is classified as `Monitoring`; all other callers are `User`.
5. Duplicate ticket numbers are reported rather than stopping the complete load.
6. Invalid rows are reported separately.
7. Customer mapping supplies Tower and Track.

## QBR fields represented by the dummy files

`Number`, `Parent Incident`, `Ticket Type`, `Project Name`, `Track Name`, `Assignment group`, `Company account`, `Configuration item`, `Service`, `Part`, `Device`, `Caller`, `Priority`, `State`, `Impact`, `Short description`, `Opened`, `Created`, `Updated`, `Closed`, `CandidateForVE`, `VETimeSavedMinutes`, `Resolution code`, `Cause code`.

The normalized model uses: `TicketNumber`, `ParentTicketNumber`, `TicketType`, `ProjectName`, `TrackName`, `AssignmentGroup`, `CompanyAccount`, `ConfigurationItem`, `Service`, `Device`, `Caller`, `Priority`, `State`, `Impact`, `ShortDescription`, `OpenedAt`, `CreatedAt`, `UpdatedAt`, `ClosedAt`, `CandidateForVE`, `VETimeSavedMinutes`, `ResolutionCode`, `CauseCode`, plus derived `CallerType`, `ValidationStatus`, `DuplicateFlag`, and `LoadStatus`.

## Excel setup

1. Create a blank macro-enabled workbook named `QBR_Data_Loader.xlsm`.
2. Open VBA (`Alt+F11`), Insert > Module, and paste/import `VBA/QBR_LoadData.bas`.
3. Run `SetupQBRLoader` once.
4. The VBA loader creates the `QBR Input Files` table after files are selected.
5. Add the Power Query `QBR_Tickets` from `PowerQuery/QBR_Tickets.pq` and load it to a worksheet/Data Model.
6. Add the dependent `QBR_DataQuality` and `QBR_Duplicates` queries.
7. Create the requested report sheets: `Load Summary`, `Loaded Records`, `Duplicate Records`, `Invalid Records`, `Unmapped Company`, `Errors`, and `Load History`.

## Dummy-data test

The dummy data deliberately includes normal user tickets, EMS/CMSP monitoring tickets, a `Home` company variant, a duplicate TicketNumber, an invalid record, and an unmapped-company scenario. No production ticket data is included.

## Important

The VBA workbook is an Excel-side ingestion/testing tool. Do not put SQL passwords, API keys, or other production secrets into the workbook or Git repository. The production integration should use an approved API/import mechanism rather than embedding database credentials in Excel.
