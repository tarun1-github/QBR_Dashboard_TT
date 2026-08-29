/*
 ============================================================
 QBR Dashboard - Sample Data (Dummy Tickets & Alerts)
 ============================================================
 This script inserts sample data for testing the dashboard.
 Replace with real data from your Excel/ServiceNow exports.
 
 Data covers: July 2026 (Created) and July 2026 (Closed)
*/

DECLARE @BatchID UNIQUEIDENTIFIER = NEWID();
DECLARE @Now DATETIME2 = SYSUTCDATETIME();

-- ============================================================
-- 1. INSERT SAMPLE TICKETS (Created in July 2026)
-- ============================================================

-- Collaboration Tower - BOA EV Track
INSERT INTO qbr.Ticket (TicketNumber, ParentTicketNumber, TicketType, CustomerID, TowerID, TrackID,
    AssignmentGroup, CompanyAccount, ConfigurationItem, Service, Part, Priority, State, Impact,
    ShortDescription, OpenedAt, CreatedAt, UpdatedAt, ClosedAt, CandidateForVE, VETimeSavedMinutes,
    ResolutionCode, CauseCode, SourceFile, LoadBatchID, LoadedAt)
VALUES
('INC001000000001', NULL, 'Parent', 4, 1, 1, 'BOA-EV-L1', 'Bank of America', 'srv-boaev-001', 'Compute', 'Server', '1 - Critical', 'Closed', '1 - Enterprise',
 'Server outage in BOA EV cluster', '2026-07-01 08:30:00', '2026-07-01 08:30:00', '2026-07-01 12:00:00', '2026-07-01 11:45:00', 'True', 15.0, 'Resolved', 'Hardware', 'created_july.xlsx', @BatchID, @Now),
('INC001000000002', 'INC001000000001', 'Child', 4, 1, 1, 'BOA-EV-L1', 'Bank of America', 'srv-boaev-001', 'Compute', 'Server', '2 - High', 'Closed', '2 - Large',
 'Child: Server failover initiated', '2026-07-01 08:35:00', '2026-07-01 08:35:00', '2026-07-01 11:00:00', '2026-07-01 11:45:00', 'True', 10.0, 'Resolved', 'Hardware', 'created_july.xlsx', @BatchID, @Now),
('INC001000000003', NULL, 'Parent', 4, 1, 1, 'BOA-EV-L2', 'Bank of America', 'net-boaev-002', 'Network', 'Switch', '2 - High', 'Closed', '2 - Large',
 'Network switch failure', '2026-07-05 14:20:00', '2026-07-05 14:20:00', '2026-07-05 18:00:00', '2026-07-05 17:30:00', 'False', NULL, 'Resolved', 'Network', 'created_july.xlsx', @BatchID, @Now),
('INC001000000004', NULL, 'Parent', 4, 1, 1, 'BOA-EV-L1', 'Bank of America', 'app-boaev-003', 'Application', 'Middleware', '3 - Moderate', 'Closed', '3 - Localized',
 'Application performance degradation', '2026-07-10 09:15:00', '2026-07-10 09:15:00', '2026-07-10 15:00:00', '2026-07-10 14:30:00', 'True', 5.0, 'Resolved', 'Software', 'created_july.xlsx', @BatchID, @Now),
('INC001000000005', 'INC001000000004', 'Child', 4, 1, 1, 'BOA-EV-L1', 'Bank of America', 'app-boaev-003', 'Application', 'Middleware', '3 - Moderate', 'Closed', '3 - Localized',
 'Child: Database connection pool exhausted', '2026-07-10 09:20:00', '2026-07-10 09:20:00', '2026-07-10 14:00:00', '2026-07-10 14:30:00', 'True', 5.0, 'Resolved', 'Software', 'created_july.xlsx', @BatchID, @Now);

-- Collaboration Tower - HSBC Collab Track
INSERT INTO qbr.Ticket (TicketNumber, ParentTicketNumber, TicketType, CustomerID, TowerID, TrackID,
    AssignmentGroup, CompanyAccount, ConfigurationItem, Service, Part, Priority, State, Impact,
    ShortDescription, OpenedAt, CreatedAt, UpdatedAt, ClosedAt, CandidateForVE, VETimeSavedMinutes,
    ResolutionCode, CauseCode, SourceFile, LoadBatchID, LoadedAt)
VALUES
('INC002000000001', NULL, 'Parent', 3, 1, 2, 'HSBC-COL-L1', 'HSBC', 'srv-hsbccol-001', 'Compute', 'Server', '1 - Critical', 'Closed', '1 - Enterprise',
 'Email service outage', '2026-07-02 07:00:00', '2026-07-02 07:00:00', '2026-07-02 12:00:00', '2026-07-02 11:30:00', 'True', 20.0, 'Resolved', 'Hardware', 'created_july.xlsx', @BatchID, @Now),
('INC002000000002', 'INC002000000001', 'Child', 3, 1, 2, 'HSBC-COL-L1', 'HSBC', 'srv-hsbccol-001', 'Compute', 'Server', '2 - High', 'Closed', '2 - Large',
 'Child: Mail queue backup', '2026-07-02 07:10:00', '2026-07-02 07:10:00', '2026-07-02 11:00:00', '2026-07-02 11:30:00', 'True', 15.0, 'Resolved', 'Hardware', 'created_july.xlsx', @BatchID, @Now),
('INC002000000003', NULL, 'Parent', 3, 1, 2, 'HSBC-COL-L2', 'HSBC', 'net-hsbccol-002', 'Network', 'Firewall', '2 - High', 'Closed', '2 - Large',
 'Firewall rule misconfiguration', '2026-07-08 16:45:00', '2026-07-08 16:45:00', '2026-07-08 20:00:00', '2026-07-08 19:30:00', 'False', NULL, 'Resolved', 'Configuration', 'created_july.xlsx', @BatchID, @Now),
('INC002000000004', NULL, 'Parent', 3, 1, 2, 'HSBC-COL-L1', 'HSBC', 'app-hsbccol-003', 'Application', 'Web Portal', '3 - Moderate', 'Closed', '3 - Localized',
 'SharePoint access issues', '2026-07-15 10:30:00', '2026-07-15 10:30:00', '2026-07-15 16:00:00', '2026-07-15 15:00:00', 'True', 8.0, 'Resolved', 'Software', 'created_july.xlsx', @BatchID, @Now),
('INC002000000005', NULL, 'Parent', 3, 1, 2, 'HSBC-COL-L1', 'HSBC', 'db-hsbccol-004', 'Database', 'SQL Server', '2 - High', 'Closed', '2 - Large',
 'Database replication lag', '2026-07-20 11:00:00', '2026-07-20 11:00:00', '2026-07-20 18:00:00', '2026-07-20 17:00:00', 'False', NULL, 'Resolved', 'Database', 'created_july.xlsx', @BatchID, @Now);

-- Security Tower - Cybersecurity Track
INSERT INTO qbr.Ticket (TicketNumber, ParentTicketNumber, TicketType, CustomerID, TowerID, TrackID,
    AssignmentGroup, CompanyAccount, ConfigurationItem, Service, Part, Priority, State, Impact,
    ShortDescription, OpenedAt, CreatedAt, UpdatedAt, ClosedAt, CandidateForVE, VETimeSavedMinutes,
    ResolutionCode, CauseCode, SourceFile, LoadBatchID, LoadedAt)
VALUES
('INC003000000001', NULL, 'Parent', 1, 2, 8, 'SEC-CYB-L1', 'Dome Depot', 'fw-cyb-001', 'Security', 'Firewall', '1 - Critical', 'Closed', '1 - Enterprise',
 'DDoS attack detected', '2026-07-01 03:00:00', '2026-07-01 03:00:00', '2026-07-01 08:00:00', '2026-07-01 07:30:00', 'True', 30.0, 'Resolved', 'Security', 'created_july.xlsx', @BatchID, @Now),
('INC003000000002', 'INC003000000001', 'Child', 1, 2, 8, 'SEC-CYB-L1', 'Dome Depot', 'fw-cyb-001', 'Security', 'Firewall', '1 - Critical', 'Closed', '1 - Enterprise',
 'Child: Rate limiting applied', '2026-07-01 03:05:00', '2026-07-01 03:05:00', '2026-07-01 07:00:00', '2026-07-01 07:30:00', 'True', 25.0, 'Resolved', 'Security', 'created_july.xlsx', @BatchID, @Now),
('INC003000000003', NULL, 'Parent', 1, 2, 8, 'SEC-CYB-L2', 'Dome Depot', 'ids-cyb-002', 'Security', 'IDS/IPS', '2 - High', 'Closed', '2 - Large',
 'Intrusion attempt blocked', '2026-07-07 22:15:00', '2026-07-07 22:15:00', '2026-07-08 02:00:00', '2026-07-08 01:30:00', 'False', NULL, 'Resolved', 'Security', 'created_july.xlsx', @BatchID, @Now),
('INC003000000004', NULL, 'Parent', 1, 2, 8, 'SEC-CYB-L1', 'Dome Depot', 'av-cyb-003', 'Security', 'Antivirus', '3 - Moderate', 'Closed', '3 - Localized',
 'Malware detected on endpoint', '2026-07-12 13:45:00', '2026-07-12 13:45:00', '2026-07-12 17:00:00', '2026-07-12 16:30:00', 'True', 10.0, 'Resolved', 'Security', 'created_july.xlsx', @BatchID, @Now),
('INC003000000005', 'INC003000000004', 'Child', 1, 2, 8, 'SEC-CYB-L1', 'Dome Depot', 'av-cyb-003', 'Security', 'Antivirus', '3 - Moderate', 'Closed', '3 - Localized',
 'Child: Endpoint quarantined', '2026-07-12 13:50:00', '2026-07-12 13:50:00', '2026-07-12 16:00:00', '2026-07-12 16:30:00', 'True', 5.0, 'Resolved', 'Security', 'created_july.xlsx', @BatchID, @Now);

-- Foundation Tower - SFNOC Track
INSERT INTO qbr.Ticket (TicketNumber, ParentTicketNumber, TicketType, CustomerID, TowerID, TrackID,
    AssignmentGroup, CompanyAccount, ConfigurationItem, Service, Part, Priority, State, Impact,
    ShortDescription, OpenedAt, CreatedAt, UpdatedAt, ClosedAt, CandidateForVE, VETimeSavedMinutes,
    ResolutionCode, CauseCode, SourceFile, LoadBatchID, LoadedAt)
VALUES
('INC004000000001', NULL, 'Parent', 1, 3, 12, 'FN-SFNOC-L1', 'Dome Depot', 'stor-sfnoc-001', 'Storage', 'SAN', '1 - Critical', 'Closed', '1 - Enterprise',
 'Storage array failure', '2026-07-03 06:00:00', '2026-07-03 06:00:00', '2026-07-03 14:00:00', '2026-07-03 13:00:00', 'True', 45.0, 'Resolved', 'Hardware', 'created_july.xlsx', @BatchID, @Now),
('INC004000000002', 'INC004000000001', 'Child', 1, 3, 12, 'FN-SFNOC-L1', 'Dome Depot', 'stor-sfnoc-001', 'Storage', 'SAN', '2 - High', 'Closed', '2 - Large',
 'Child: Data recovery in progress', '2026-07-03 06:15:00', '2026-07-03 06:15:00', '2026-07-03 13:00:00', '2026-07-03 13:00:00', 'True', 30.0, 'Resolved', 'Hardware', 'created_july.xlsx', @BatchID, @Now),
('INC004000000003', NULL, 'Parent', 1, 3, 12, 'FN-SFNOC-L2', 'Dome Depot', 'net-sfnoc-002', 'Network', 'Core Switch', '2 - High', 'Closed', '2 - Large',
 'Core switch redundancy lost', '2026-07-09 19:30:00', '2026-07-09 19:30:00', '2026-07-10 01:00:00', '2026-07-09 23:30:00', 'False', NULL, 'Resolved', 'Network', 'created_july.xlsx', @BatchID, @Now),
('INC004000000004', NULL, 'Parent', 1, 3, 12, 'FN-SFNOC-L1', 'Dome Depot', 'srv-sfnoc-003', 'Compute', 'Blade Server', '3 - Moderate', 'Closed', '3 - Localized',
 'Blade server maintenance', '2026-07-16 08:00:00', '2026-07-16 08:00:00', '2026-07-16 12:00:00', '2026-07-16 11:00:00', 'True', 12.0, 'Resolved', 'Maintenance', 'created_july.xlsx', @BatchID, @Now),
('INC004000000005', NULL, 'Parent', 1, 3, 12, 'FN-SFNOC-L1', 'Dome Depot', 'pwr-sfnoc-004', 'Power', 'UPS', '2 - High', 'Closed', '2 - Large',
 'UPS battery replacement', '2026-07-22 14:00:00', '2026-07-22 14:00:00', '2026-07-22 18:00:00', '2026-07-22 17:00:00', 'False', NULL, 'Resolved', 'Maintenance', 'created_july.xlsx', @BatchID, @Now);

-- Foundation Tower - THD Data Track
INSERT INTO qbr.Ticket (TicketNumber, ParentTicketNumber, TicketType, CustomerID, TowerID, TrackID,
    AssignmentGroup, CompanyAccount, ConfigurationItem, Service, Part, Priority, State, Impact,
    ShortDescription, OpenedAt, CreatedAt, UpdatedAt, ClosedAt, CandidateForVE, VETimeSavedMinutes,
    ResolutionCode, CauseCode, SourceFile, LoadBatchID, LoadedAt)
VALUES
('INC005000000001', NULL, 'Parent', 1, 3, 13, 'FN-THD-L1', 'Dome Depot', 'wlc-thd-001', 'Wireless', 'WLC', '2 - High', 'Closed', '2 - Large',
 'Wireless controller failure', '2026-07-04 10:00:00', '2026-07-04 10:00:00', '2026-07-04 16:00:00', '2026-07-04 15:00:00', 'True', 20.0, 'Resolved', 'Hardware', 'created_july.xlsx', @BatchID, @Now),
('INC005000000002', 'INC005000000001', 'Child', 1, 3, 13, 'FN-THD-L1', 'Dome Depot', 'ap-thd-002', 'Wireless', 'Access Point', '3 - Moderate', 'Closed', '3 - Localized',
 'Child: AP rejoin/disjoin alerts', '2026-07-04 10:05:00', '2026-07-04 10:05:00', '2026-07-04 15:00:00', '2026-07-04 15:00:00', 'True', 15.0, 'Resolved', 'Hardware', 'created_july.xlsx', @BatchID, @Now),
('INC005000000003', NULL, 'Parent', 1, 3, 13, 'FN-THD-L2', 'Dome Depot', 'agg-thd-003', 'Network', 'Aggregator', '3 - Moderate', 'Closed', '3 - Localized',
 'Aggregator switch config change', '2026-07-11 20:00:00', '2026-07-11 20:00:00', '2026-07-11 23:00:00', '2026-07-11 22:30:00', 'False', NULL, 'Resolved', 'Configuration', 'created_july.xlsx', @BatchID, @Now),
('INC005000000004', NULL, 'Parent', 1, 3, 13, 'FN-THD-L1', 'Dome Depot', 'sdwan-thd-004', 'SDWAN', 'Edge Device', '2 - High', 'Closed', '2 - Large',
 'SDWAN site down', '2026-07-18 07:30:00', '2026-07-18 07:30:00', '2026-07-18 12:00:00', '2026-07-18 11:00:00', 'True', 10.0, 'Resolved', 'Network', 'created_july.xlsx', @BatchID, @Now),
('INC005000000005', 'INC005000000004', 'Child', 1, 3, 13, 'FN-THD-L1', 'Dome Depot', 'sdwan-thd-004', 'SDWAN', 'Edge Device', '2 - High', 'Closed', '2 - Large',
 'Child: BFD session recovery', '2026-07-18 07:35:00', '2026-07-18 07:35:00', '2026-07-18 11:00:00', '2026-07-18 11:00:00', 'True', 8.0, 'Resolved', 'Network', 'created_july.xlsx', @BatchID, @Now);

-- Non-CMS Tower - RIL Track
INSERT INTO qbr.Ticket (TicketNumber, ParentTicketNumber, TicketType, CustomerID, TowerID, TrackID,
    AssignmentGroup, CompanyAccount, ConfigurationItem, Service, Part, Priority, State, Impact,
    ShortDescription, OpenedAt, CreatedAt, UpdatedAt, ClosedAt, CandidateForVE, VETimeSavedMinutes,
    ResolutionCode, CauseCode, SourceFile, LoadBatchID, LoadedAt)
VALUES
('INC006000000001', NULL, 'Parent', 5, 4, 15, 'NC-RIL-L1', 'Reliance', 'srv-ril-001', 'Compute', 'Server', '2 - High', 'Closed', '2 - Large',
 'Compute resource exhaustion', '2026-07-06 09:00:00', '2026-07-06 09:00:00', '2026-07-06 15:00:00', '2026-07-06 14:00:00', 'True', 18.0, 'Resolved', 'Capacity', 'created_july.xlsx', @BatchID, @Now),
('INC006000000002', NULL, 'Parent', 5, 4, 15, 'NC-RIL-L2', 'Reliance', 'net-ril-002', 'Network', 'Router', '3 - Moderate', 'Closed', '3 - Localized',
 'Router interface flapping', '2026-07-13 15:30:00', '2026-07-13 15:30:00', '2026-07-13 19:00:00', '2026-07-13 18:00:00', 'False', NULL, 'Resolved', 'Network', 'created_july.xlsx', @BatchID, @Now),
('INC006000000003', NULL, 'Parent', 5, 4, 15, 'NC-RIL-L1', 'Reliance', 'app-ril-003', 'Application', 'API Gateway', '2 - High', 'Closed', '2 - Large',
 'API gateway timeout', '2026-07-19 11:00:00', '2026-07-19 11:00:00', '2026-07-19 17:00:00', '2026-07-19 16:00:00', 'True', 12.0, 'Resolved', 'Software', 'created_july.xlsx', @BatchID, @Now),
('INC006000000004', 'INC006000000003', 'Child', 5, 4, 15, 'NC-RIL-L1', 'Reliance', 'app-ril-003', 'Application', 'API Gateway', '3 - Moderate', 'Closed', '3 - Localized',
 'Child: Backend service restart', '2026-07-19 11:10:00', '2026-07-19 11:10:00', '2026-07-19 16:00:00', '2026-07-19 16:00:00', 'True', 8.0, 'Resolved', 'Software', 'created_july.xlsx', @BatchID, @Now),
('INC006000000005', NULL, 'Parent', 5, 4, 15, 'NC-RIL-L1', 'Reliance', 'db-ril-004', 'Database', 'Oracle', '1 - Critical', 'Closed', '1 - Enterprise',
 'Database performance issue', '2026-07-25 08:00:00', '2026-07-25 08:00:00', '2026-07-25 14:00:00', '2026-07-25 13:00:00', 'True', 25.0, 'Resolved', 'Database', 'created_july.xlsx', @BatchID, @Now);

PRINT 'Sample tickets inserted: 30 tickets across 6 tracks';
GO

-- ============================================================
-- 2. INSERT SAMPLE ALERTS
-- ============================================================
INSERT INTO qbr.Alert (AlertID, TicketNumber, CustomerID, TowerID, TrackID,
    AlertTime, Service, Part, AlertType, Severity, MonitoringTool, AlertDescription, SourceFile, LoadBatchID, LoadedAt)
VALUES
-- BOA EV Alerts
('ALT-20260701-001', 'INC001000000001', 4, 1, 1, '2026-07-01 08:25:00', 'Compute', 'Server', 'CPU_HIGH', 'Critical', 'NZG2', 'CPU utilization above 95%', 'alerts_july.xlsx', @BatchID, @Now),
('ALT-20260701-002', 'INC001000000001', 4, 1, 1, '2026-07-01 08:28:00', 'Compute', 'Server', 'MEMORY_HIGH', 'Critical', 'NZG2', 'Memory utilization above 90%', 'alerts_july.xlsx', @BatchID, @Now),
('ALT-20260705-001', 'INC001000000003', 4, 1, 1, '2026-07-05 14:15:00', 'Network', 'Switch', 'LINK_DOWN', 'High', 'NZG2', 'Switch port down', 'alerts_july.xlsx', @BatchID, @Now),
('ALT-20260710-001', 'INC001000000004', 4, 1, 1, '2026-07-10 09:10:00', 'Application', 'Middleware', 'RESPONSE_SLOW', 'Moderate', 'NZG2', 'Response time above threshold', 'alerts_july.xlsx', @BatchID, @Now),

-- HSBC Collab Alerts
('ALT-20260702-001', 'INC002000000001', 3, 1, 2, '2026-07-02 06:55:00', 'Compute', 'Server', 'SERVICE_DOWN', 'Critical', 'NZG2', 'Email service not responding', 'alerts_july.xlsx', @BatchID, @Now),
('ALT-20260702-002', 'INC002000000001', 3, 1, 2, '2026-07-02 06:58:00', 'Compute', 'Server', 'QUEUE_HIGH', 'High', 'NZG2', 'Mail queue exceeding limit', 'alerts_july.xlsx', @BatchID, @Now),
('ALT-20260708-001', 'INC002000000003', 3, 1, 2, '2026-07-08 16:40:00', 'Network', 'Firewall', 'RULE_VIOLATION', 'High', 'NZG2', 'Firewall rule blocking traffic', 'alerts_july.xlsx', @BatchID, @Now),
('ALT-20260715-001', 'INC002000000004', 3, 1, 2, '2026-07-15 10:25:00', 'Application', 'Web Portal', 'AUTH_FAILURE', 'Moderate', 'NZG2', 'Authentication failures detected', 'alerts_july.xlsx', @BatchID, @Now),

-- Cybersecurity Alerts
('ALT-20260701-003', 'INC003000000001', 1, 2, 8, '2026-07-01 02:50:00', 'Security', 'Firewall', 'DDOS_DETECTED', 'Critical', 'NZG2', 'DDoS attack pattern detected', 'alerts_july.xlsx', @BatchID, @Now),
('ALT-20260701-004', 'INC003000000001', 1, 2, 8, '2026-07-01 02:55:00', 'Security', 'IDS/IPS', 'TRAFFIC_SPIKE', 'Critical', 'NZG2', 'Abnormal traffic volume', 'alerts_july.xlsx', @BatchID, @Now),
('ALT-20260707-001', 'INC003000000003', 1, 2, 8, '2026-07-07 22:10:00', 'Security', 'IDS/IPS', 'INTRUSION_ATTEMPT', 'High', 'NZG2', 'Intrusion attempt blocked', 'alerts_july.xlsx', @BatchID, @Now),
('ALT-20260712-001', 'INC003000000004', 1, 2, 8, '2026-07-12 13:40:00', 'Security', 'Antivirus', 'MALWARE_DETECTED', 'Moderate', 'NZG2', 'Malware signature detected', 'alerts_july.xlsx', @BatchID, @Now),

-- SFNOC Alerts
('ALT-20260703-001', 'INC004000000001', 1, 3, 12, '2026-07-03 05:50:00', 'Storage', 'SAN', 'DISK_FAILURE', 'Critical', 'NZG2', 'Multiple disk failures', 'alerts_july.xlsx', @BatchID, @Now),
('ALT-20260703-002', 'INC004000000001', 1, 3, 12, '2026-07-03 05:55:00', 'Storage', 'SAN', 'CAPACITY_LOW', 'High', 'NZG2', 'Storage capacity critical', 'alerts_july.xlsx', @BatchID, @Now),
('ALT-20260709-001', 'INC004000000003', 1, 3, 12, '2026-07-09 19:25:00', 'Network', 'Core Switch', 'REDUNDANCY_LOST', 'High', 'NZG2', 'Switch redundancy lost', 'alerts_july.xlsx', @BatchID, @Now),

-- THD Data Alerts
('ALT-20260704-001', 'INC005000000001', 1, 3, 13, '2026-07-04 09:50:00', 'Wireless', 'WLC', 'DEVICE_UNREACHABLE', 'High', 'NZG2', 'WLC not responding', 'alerts_july.xlsx', @BatchID, @Now),
('ALT-20260704-002', 'INC005000000001', 1, 3, 13, '2026-07-04 09:55:00', 'Wireless', 'Access Point', 'AP_DISCONNECT', 'Moderate', 'NZG2', 'Multiple APs disconnected', 'alerts_july.xlsx', @BatchID, @Now),
('ALT-20260718-001', 'INC005000000004', 1, 3, 13, '2026-07-18 07:25:00', 'SDWAN', 'Edge Device', 'SITE_DOWN', 'High', 'NZG2', 'SDWAN site unreachable', 'alerts_july.xlsx', @BatchID, @Now),

-- RIL Alerts
('ALT-20260706-001', 'INC006000000001', 5, 4, 15, '2026-07-06 08:50:00', 'Compute', 'Server', 'CPU_HIGH', 'High', 'NZG2', 'CPU utilization spike', 'alerts_july.xlsx', @BatchID, @Now),
('ALT-20260719-001', 'INC006000000003', 5, 4, 15, '2026-07-19 10:50:00', 'Application', 'API Gateway', 'TIMEOUT', 'High', 'NZG2', 'API timeout errors', 'alerts_july.xlsx', @BatchID, @Now),
('ALT-20260725-001', 'INC006000000005', 5, 4, 15, '2026-07-25 07:50:00', 'Database', 'Oracle', 'SLOW_QUERY', 'Critical', 'NZG2', 'Database query performance degraded', 'alerts_july.xlsx', @BatchID, @Now);

PRINT 'Sample alerts inserted: 22 alerts across 6 tracks';
GO

-- ============================================================
-- 3. INSERT REFRESH LOG
-- ============================================================
INSERT INTO qbr.RefreshLog (LoadBatchID, SourceName, StartedAt, FinishedAt, RowsRead, RowsLoaded, Status, ErrorMessage)
VALUES (@BatchID, 'Sample Data Load', @Now, SYSUTCDATETIME(), 52, 52, 'Completed', NULL);

PRINT '';
PRINT '========================================';
PRINT 'Sample data loaded successfully!';
PRINT 'Batch ID: ' + CONVERT(NVARCHAR(50), @BatchID);
PRINT '========================================';
GO
