let
    Source = QBR_Tickets,
    Result = Table.SelectRows(Source, each [DuplicateFlag] = true)
in
    Result
