# QBR Ticket-Centric Migration

## Target architecture

`qbr.Ticket` is the single fact table.

- `Caller = EMS` or `CMSP` => monitoring-generated ticket.
- Any other Caller => user-generated ticket.
- `qbr.Customer` is the authoritative `CompanyAccount -> Tower -> Track` mapping.
- `Device` replaces the old `Part` business terminology.
- `qbr.Alert` and `qbr.TicketAlert` are legacy/rollback tables only. The application no longer reads or writes them.

## CompanyAccount mapping

| CompanyAccount | Tower | Track |
|---|---|---|
| Bank of America | Collaboration | BOA EV |
| HSBC | Collaboration | HSBC |
| Problem Management | Collaboration | Problem Management |
| BOA TP | Collaboration | BOA TP |
| GTM TP | Collaboration | GTM TP |
| HD Voice (Bgl) | Collaboration | HD Voice (Bgl) |
| SCNOC | Collaboration | SCNOC |
| Cybersecurity | Security | Cybersecurity |
| DC-ACI | Security | DC-ACI |
| Infra | Security | Infra |
| SOC | Security | SOC |
| SFNOC | Foundation | SFNOC |
| Home Depot / any account containing Home | Foundation | THD Data |
| HSBC Data | Foundation | HSBC Data |
| RIL | Non-CMS | RIL |

## Execution order

1. Back up CPDB.
2. Run `sql/08_ticket_customer_mapping.sql`.
3. Review the two result sets at the end of that script. Unmapped CompanyAccount should be zero; Foundation must show SFNOC, THD Data and HSBC Data.
4. Run `sql/09_validate_ticket_model.sql`. Duplicate TicketNumber and unresolved Tower/Track should be zero.
5. Pull the `test-chatgpt-write` branch locally and run `python -m py_compile load_data_v2.py app/dashboard_data.py app/dashboard.py`.
6. Put the new ServiceNow XLSX/CSV/TXT files in `app/dataset`.
7. Run `python load_data.py --replace-tickets` only when a full reload is intended. The loader de-duplicates TicketNumber before insert and creates `_duplicate_records.xlsx`; no duplicate is inserted.
8. After a successful commit, source files and generated reports are moved to `app/dataset/processed/<timestamp>`.
9. Start Streamlit and validate Ticket Volume by Tower -> Track, monitoring/device frequency, parent-child, max/min volume, and login persistence.
10. Only after production validation should the legacy `qbr.Alert` and `qbr.TicketAlert` tables be retired.

## Important safety rule

Do not delete `qbr.Alert` or `qbr.TicketAlert` before the new ticket-centric dashboard has been validated. The application does not depend on them after this migration, but retaining them during validation provides a rollback/reference point.
