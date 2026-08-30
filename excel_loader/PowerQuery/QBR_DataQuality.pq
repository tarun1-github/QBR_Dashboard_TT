let
    Source = QBR_Tickets,
    Result = Table.SelectRows(Source, each [LoadStatus] = "Invalid")
in
    Result
