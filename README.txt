QBR Executive Dashboard - Data Loader Guide
=============================================

FILE NOMENCLATURE & FORMATS
---------------------------

Supported file formats:
- .xlsx / .xls  (Excel files)
- .csv           (Comma-separated values)
- .txt           (Tab or comma-separated text files)

Place your data files in: app/dataset/ folder

COLUMN MAPPINGS (Flexible)
--------------------------

The system automatically detects these column names (case-insensitive):

Ticket Columns:
- Number / TicketNumber / Ticket_Number / Incident_Number
- Parent Incident / ParentIncident / Parent_Incident / ParentTicketNumber
- Priority / priority
- State / Status
- Impact / impact
- Assignment group / AssignmentGroup / Track / TrackName
- Company account / CompanyAccount / Company / Customer
- Configuration item / ConfigurationItem / CI
- Short description / ShortDescription / Description
- Opened / OpenedAt / Created
- Closed / ClosedAt / Resolved
- Cause code / CauseCode
- Resolution code / ResolutionCode

Alert Columns (if available):
- AlertID / AlertNumber
- AlertTime / AlertDate / Timestamp
- Part / Component
- AlertType / Type
- Severity / Priority

TOWER & TRACK MAPPING
---------------------

Tickets are automatically mapped to Towers and Tracks based on Assignment Group:

Collaboration Tower:
  - BOA EV        -> Assignment groups: BOA-EV, BOA-EV-L1, BOA-EV-L2
  - HSBC Collab   -> Assignment groups: HSBC-COL, HSBC-COL-L1, HSBC-COL-L2
  - Problem Mgmt  -> Assignment groups: PM, PM-L1
  - BOA TP        -> Assignment groups: BOA-TP
  - GTM TP        -> Assignment groups: GTM-TP
  - HD Voice      -> Assignment groups: HD-VOICE
  - SCNOC         -> Assignment groups: SCNOC

Security Tower:
  - Cybersecurity -> Assignment groups: SEC-CYB, SEC-CYB-L1, SEC-CYB-L2
  - DC-ACI        -> Assignment groups: DC-ACI
  - Infra         -> Assignment groups: INFRA
  - SOC           -> Assignment groups: SOC

Foundation Tower:
  - SFNOC         -> Assignment groups: FN-SFNOC, FN-SFNOC-L1, FN-SFNOC-L2
  - THD Data      -> Assignment groups: FN-THD, FN-THD-L1, FN-THD-L2, JLK-R&S, JLK-WIRELESS
  - HSBC Data     -> Assignment groups: HSBC-DATA

Non-CMS Tower:
  - RIL           -> Assignment groups: NC-RIL, NC-RIL-L1, NC-RIL-L2

LOADING DATA
------------

Load all files in dataset folder:
    python load_data.py

Load specific file:
    python load_data.py --file created_tickets.xlsx

Clear all data and reload:
    python load_data.py --clear

Show data summary:
    python load_data.py --show-summary

RUN DASHBOARD
-------------

    streamlit run app/dashboard.py
