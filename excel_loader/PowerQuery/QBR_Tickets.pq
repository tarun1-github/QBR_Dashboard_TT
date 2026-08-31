let
    InputTable = Excel.CurrentWorkbook(){[Name="QBR_InputFiles"]}[Content],
    Paths = List.RemoveNulls(InputTable[FilePath]),
    Files = Table.FromList(Paths, Splitter.SplitByNothing(), {"FilePath"}),
    AddExtension = Table.AddColumn(Files, "Extension", each Text.Lower(Path.GetExtension([FilePath]))),

    ReadFile = (p as text) as table =>
        let
            ext = Text.Lower(Path.GetExtension(p)),
            result = if ext = ".csv" then
                Table.PromoteHeaders(Csv.Document(File.Contents(p), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]), [PromoteAllScalars=true])
            else
                let wb = Excel.Workbook(File.Contents(p), null, true),
                    tables = Table.SelectRows(wb, each [Kind] = "Table" or [Kind] = "Sheet"),
                    first = if Table.RowCount(tables) > 0 then tables{0}[Data] else #table({}, {})
                in Table.PromoteHeaders(first, [PromoteAllScalars=true])
        in result,

    AddData = Table.AddColumn(AddExtension, "Data", each ReadFile([FilePath])),
    Expanded = if Table.RowCount(AddData) = 0 then #table({}, {}) else Table.Combine(AddData[Data]),

    RenameAliases = Table.RenameColumns(Expanded, {
        {"Number", "TicketNumber"},
        {"Parent Incident", "ParentTicketNumber"},
        {"Assignment group", "AssignmentGroup"},
        {"Company account", "CompanyAccount"},
        {"Configuration item", "ConfigurationItem"},
        {"Short description", "ShortDescription"},
        {"Resolution code", "ResolutionCode"},
        {"Cause code", "CauseCode"},
        {"Part", "Device"}
    }, MissingField.Ignore),

    AddSource = if Table.HasColumns(RenameAliases, "SourceFile") then RenameAliases else Table.AddColumn(RenameAliases, "SourceFile", each "Excel Input"),
    CleanCompany = if Table.HasColumns(AddSource, "CompanyAccount") then Table.TransformColumns(AddSource, {{"CompanyAccount", each if _ = null then null else Text.Trim(Text.From(_)), type text}}) else AddSource,
    NormalizeHome = if Table.HasColumns(CleanCompany, "CompanyAccount") then Table.TransformColumns(CleanCompany, {{"CompanyAccount", each if _ <> null and Text.Contains(_, "Home", Comparer.OrdinalIgnoreCase) then "Home Depot" else _, type text}}) else CleanCompany,

    AddCallerType = if Table.HasColumns(NormalizeHome, "Caller") then
        Table.AddColumn(NormalizeHome, "CallerType", each if Text.Contains(Text.From([Caller]), "EMS", Comparer.OrdinalIgnoreCase) or Text.Contains(Text.From([Caller]), "CMSP", Comparer.OrdinalIgnoreCase) then "Monitoring" else "User", type text)
    else Table.AddColumn(NormalizeHome, "CallerType", each "User", type text),

    Required = {"TicketNumber", "CompanyAccount", "Caller", "Priority", "State", "OpenedAt", "CreatedAt", "UpdatedAt", "ClosedAt"},
    AddValidation = Table.AddColumn(AddCallerType, "ValidationStatus", each
        let missing = List.Select(Required, (c) => not Table.HasColumns(AddCallerType, c) or Record.FieldOrDefault(_, c, null) = null or Text.Trim(Text.From(Record.FieldOrDefault(_, c, ""))) = "")
        in if List.Count(missing) = 0 then "Valid" else "Invalid: " & Text.Combine(missing, ", "), type text),

    AddDuplicateFlag = if Table.HasColumns(AddValidation, "TicketNumber") then
        Table.AddColumn(AddValidation, "DuplicateFlag", each let n = [TicketNumber] in if n = null then false else List.Count(List.Select(AddValidation[TicketNumber], (x) => x = n)) > 1, type logical)
    else Table.AddColumn(AddValidation, "DuplicateFlag", each false, type logical),

    AddLoadStatus = Table.AddColumn(AddDuplicateFlag, "LoadStatus", each if [ValidationStatus] <> "Valid" then "Invalid" else if [DuplicateFlag] then "Duplicate" else "Loaded", type text)
 in
    AddLoadStatus
