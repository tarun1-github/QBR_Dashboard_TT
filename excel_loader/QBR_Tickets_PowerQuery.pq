// QBR Ticket Power Query transformation template
// Parameters expected:
//   pFilePath = full path to Created_tickets.xlsx / Closed_tickets.xlsx
// The query keeps the real QBR field names and normalizes legacy aliases.

let
    Source = Excel.Workbook(File.Contents(pFilePath), null, true),
    Sheets = Table.SelectRows(Source, each [Kind] = "Sheet" or [Kind] = "Table"),
    Data = Table.Combine(List.Transform(Sheets[Data], each Table.PromoteHeaders(_, [PromoteAllScalars=true]))),

    RenameAliases = Table.RenameColumns(Data, {
        {"Number", "TicketNumber"},
        {"Ticket Number", "TicketNumber"},
        {"Incident Number", "TicketNumber"},
        {"Parent Incident", "ParentTicketNumber"},
        {"Parent Incident Number", "ParentTicketNumber"},
        {"Assignment group", "AssignmentGroup"},
        {"Company account", "CompanyAccount"},
        {"Configuration Item", "ConfigurationItem"},
        {"Short description", "ShortDescription"},
        {"Part", "Device"}
    }, MissingField.Ignore),

    NormalizeCompany = Table.TransformColumns(RenameAliases, {
        {"CompanyAccount", each if _ <> null and Text.Contains(Text.From(_), "Home", Comparer.OrdinalIgnoreCase) then "Home Depot" else _, type text}
    }, null, MissingField.Ignore),

    AddCallerType = Table.AddColumn(NormalizeCompany, "CallerType", each
        let c = if [Caller] = null then "" else Text.Upper(Text.From([Caller]))
        in if Text.Contains(c, "EMS") or Text.Contains(c, "CMSP") then "Monitoring" else "User", type text),

    AddMonitoringFlag = Table.AddColumn(AddCallerType, "IsMonitoringGenerated", each [CallerType] = "Monitoring", type logical),

    AddTicketType = Table.AddColumn(AddMonitoringFlag, "TicketType_Normalized", each
        if [ParentTicketNumber] <> null and Text.Trim(Text.From([ParentTicketNumber])) <> "" then "Child" else "Parent", type text),

    RemoveBlankTickets = Table.SelectRows(AddTicketType, each [TicketNumber] <> null and Text.Trim(Text.From([TicketNumber])) <> ""),
    DistinctTickets = Table.Distinct(RemoveBlankTickets, {"TicketNumber"}),

    CustomerMap = #table(
        {"CompanyAccount","CustomerName","TowerName","TrackName"},
        {
            {"Home Depot","Home Depot","Foundation","THD Data"},
            {"Jio Platforms","Jio Platforms",null,null},
            {"HSBC","HSBC","Collaboration","HSBC"},
            {"Bank of America","Bank of America","Collaboration","BOA EV"},
            {"Reliance","Reliance",null,null},
            {"Problem Management","Problem Management","Collaboration","Problem Management"},
            {"BOA TP","BOA TP","Collaboration","BOA TP"},
            {"GTM TP","GTM TP","Collaboration","GTM TP"},
            {"HD Voice (Bgl)","HD Voice (Bgl)","Collaboration","HD Voice (Bgl)"},
            {"SCNOC","SCNOC","Collaboration","SCNOC"},
            {"SFNOC","SFNOC","Foundation","SFNOC"},
            {"HSBC Data","HSBC Data","Foundation","HSBC Data"},
            {"RIL","RIL","Non-CMS","RIL"},
            {"Cybersecurity","Cybersecurity","Security","Cybersecurity"},
            {"DC-ACI","DC-ACI","Security","DC-ACI"},
            {"Infra","Infra","Security","Infra"},
            {"SOC","SOC","Security","SOC"}
        }
    ),

    JoinCustomer = Table.NestedJoin(DistinctTickets, {"CompanyAccount"}, CustomerMap, {"CompanyAccount"}, "CustomerMap", JoinKind.LeftOuter),
    ExpandCustomer = Table.ExpandTableColumn(JoinCustomer, "CustomerMap", {"CustomerName","TowerName","TrackName"}, {"CustomerName_Mapped","TowerName_Mapped","TrackName_Mapped"}),

    AddFinalCustomer = Table.AddColumn(ExpandCustomer, "CustomerName_Final", each if [CustomerName_Mapped] <> null then [CustomerName_Mapped] else [CompanyAccount], type text),
    AddFinalTower = Table.AddColumn(AddFinalCustomer, "TowerName_Final", each [TowerName_Mapped], type text),
    AddFinalTrack = Table.AddColumn(AddFinalTower, "TrackName_Final", each [TrackName_Mapped], type text),
    AddMappingStatus = Table.AddColumn(AddFinalTrack, "MappingStatus", each if [CompanyAccount] = null or [CompanyAccount] = "" then "Blank Company" else if [TowerName_Final] = null or [TrackName_Final] = null then "Unmapped Company" else "Mapped", type text)

in
    AddMappingStatus
