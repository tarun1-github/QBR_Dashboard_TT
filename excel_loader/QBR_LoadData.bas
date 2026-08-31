Attribute VB_Name = "QBR_LoadData"
Option Explicit

' QBR Ticket Data Loader
' Imports Created_tickets.xlsx / Closed_tickets.xlsx using the real QBR field names,
' normalizes Home* company accounts to Home Depot, classifies EMS/CMSP callers,
' and creates a QBR_Load_Report.xlsx-compatible report inside the workbook.
'
' The code uses late binding so no external VBA references are required.

Private Const SHEET_CONTROL As String = "Load Control"
Private Const SHEET_MAP As String = "Customer Mapping"
Private Const SHEET_LOADED As String = "Loaded Records"
Private Const SHEET_DUP As String = "Duplicate Records"
Private Const SHEET_INVALID As String = "Invalid Records"
Private Const SHEET_UNMAPPED As String = "Unmapped Company"
Private Const SHEET_ERRORS As String = "Errors"
Private Const SHEET_SUMMARY As String = "Load Summary"

Public Sub SetupQBRLoader()
    Application.ScreenUpdating = False
    EnsureSheet SHEET_CONTROL
    EnsureSheet SHEET_MAP
    EnsureSheet SHEET_SUMMARY
    EnsureSheet SHEET_LOADED
    EnsureSheet SHEET_DUP
    EnsureSheet SHEET_INVALID
    EnsureSheet SHEET_UNMAPPED
    EnsureSheet SHEET_ERRORS

    BuildControlSheet
    BuildCustomerMapping
    PrepareReportSheets
    Application.ScreenUpdating = True
    MsgBox "QBR Loader is ready. Select files and click LOAD DATA.", vbInformation
End Sub

Public Sub SelectQBRFiles()
    Dim fd As FileDialog, i As Long, ws As Worksheet
    Set ws = ThisWorkbook.Worksheets(SHEET_CONTROL)
    Set fd = Application.FileDialog(msoFileDialogFilePicker)

    With fd
        .Title = "Select QBR Created / Closed Excel files"
        .AllowMultiSelect = True
        .Filters.Clear
        .Filters.Add "Excel files", "*.xlsx;*.xlsm;*.xls"
        If .Show <> -1 Then Exit Sub
        ws.Range("B9:B20").ClearContents
        For i = 1 To .SelectedItems.Count
            ws.Cells(8 + i, 2).Value = .SelectedItems(i)
        Next i
    End With
End Sub

Public Sub LoadQBRData()
    Dim wsC As Worksheet, wsL As Worksheet, wsD As Worksheet, wsI As Worksheet
    Dim wsU As Worksheet, wsE As Worksheet, wsS As Worksheet, wbSrc As Workbook, wsSrc As Worksheet
    Dim files As Collection, path As Variant, lastRow As Long, r As Long, outRow As Long
    Dim headers As Object, seen As Object, map As Object
    Dim ticket As String, company As String, caller As String, key As String
    Dim tower As String, track As String, reason As String, fileName As String
    Dim total As Long, loaded As Long, dup As Long, invalid As Long, unmapped As Long, monitoring As Long, userTickets As Long, errCount As Long
    Dim v As Variant

    On Error GoTo FatalError
    Application.ScreenUpdating = False
    Application.EnableEvents = False
    Set wsC = ThisWorkbook.Worksheets(SHEET_CONTROL)
    Set wsL = ThisWorkbook.Worksheets(SHEET_LOADED)
    Set wsD = ThisWorkbook.Worksheets(SHEET_DUP)
    Set wsI = ThisWorkbook.Worksheets(SHEET_INVALID)
    Set wsU = ThisWorkbook.Worksheets(SHEET_UNMAPPED)
    Set wsE = ThisWorkbook.Worksheets(SHEET_ERRORS)
    Set wsS = ThisWorkbook.Worksheets(SHEET_SUMMARY)
    Set seen = CreateObject("Scripting.Dictionary")
    Set map = LoadMapping()
    Set files = GetSelectedFiles(wsC)

    If files.Count = 0 Then
        MsgBox "Please select at least one Created_tickets.xlsx or Closed_tickets.xlsx file.", vbExclamation
        GoTo CleanExit
    End If

    PrepareReportSheets
    outRow = 2

    For Each path In files
        fileName = Dir(CStr(path))
        On Error Resume Next
        Set wbSrc = Workbooks.Open(CStr(path), ReadOnly:=True, UpdateLinks:=False)
        If Err.Number <> 0 Or wbSrc Is Nothing Then
            errCount = errCount + 1
            wsE.Cells(wsE.Rows.Count, 1).End(xlUp).Offset(1, 0).Resize(1, 3).Value = Array(fileName, "Open file", Err.Description)
            Err.Clear
            On Error GoTo FatalError
            GoTo NextFile
        End If
        On Error GoTo FatalError

        For Each wsSrc In wbSrc.Worksheets
            If Application.WorksheetFunction.CountA(wsSrc.Cells) > 0 Then
                Set headers = HeaderIndex(wsSrc)
                If Not headers.Exists("TICKETNUMBER") Then
                    errCount = errCount + 1
                    wsE.Cells(wsE.Rows.Count, 1).End(xlUp).Offset(1, 0).Resize(1, 3).Value = Array(fileName, wsSrc.Name, "Ticket Number/Number column not found")
                    GoTo NextSheet
                End If

                lastRow = wsSrc.Cells(wsSrc.Rows.Count, 1).End(xlUp).Row
                For r = 2 To lastRow
                    total = total + 1
                    ticket = Trim$(CStr(GetValue(wsSrc, headers, r, "TICKETNUMBER")))
                    key = UCase$(ticket)

                    If Len(key) = 0 Then
                        invalid = invalid + 1
                        wsI.Cells(wsI.Rows.Count, 1).End(xlUp).Offset(1, 0).Resize(1, 4).Value = Array(fileName, r, "", "Missing Ticket Number")
                        GoTo NextRow
                    End If

                    If seen.Exists(key) Then
                        dup = dup + 1
                        wsD.Cells(wsD.Rows.Count, 1).End(xlUp).Offset(1, 0).Resize(1, 4).Value = Array(ticket, fileName, seen(key), "Duplicate Ticket Number")
                        GoTo NextRow
                    End If
                    seen.Add key, fileName

                    company = NormalizeCompany(GetValue(wsSrc, headers, r, "COMPANYACCOUNT"))
                    caller = Trim$(CStr(GetValue(wsSrc, headers, r, "CALLER")))
                    tower = ""
                    track = ""
                    reason = ""
                    If map.Exists(UCase$(company)) Then
                        v = map(UCase$(company))
                        tower = CStr(v(0))
                        track = CStr(v(1))
                    ElseIf Len(company) > 0 Then
                        unmapped = unmapped + 1
                        wsU.Cells(wsU.Rows.Count, 1).End(xlUp).Offset(1, 0).Resize(1, 3).Value = Array(company, ticket, fileName)
                    End If

                    If IsMonitoringCaller(caller) Then
                        monitoring = monitoring + 1
                    Else
                        userTickets = userTickets + 1
                    End If

                    CopyNormalizedRecord wsSrc, headers, r, wsL, outRow, fileName, company, tower, track
                    outRow = outRow + 1
                    loaded = loaded + 1
NextRow:
                Next r
            End If
NextSheet:
        Next wsSrc
        wbSrc.Close SaveChanges:=False
        Set wbSrc = Nothing
NextFile:
    Next path

    WriteSummary wsS, files.Count, total, loaded, dup, invalid, unmapped, monitoring, userTickets, errCount
    wsC.Range("B5").Value = "Completed"
    wsC.Range("B6").Value = Now
    wsC.Range("B7").Value = loaded
    FormatReportSheets
    MsgBox "QBR load completed." & vbCrLf & vbCrLf & _
           "Input records: " & total & vbCrLf & _
           "Loaded: " & loaded & vbCrLf & _
           "Duplicates: " & dup & vbCrLf & _
           "Invalid: " & invalid & vbCrLf & _
           "Unmapped company: " & unmapped & vbCrLf & _
           "Monitoring (EMS/CMSP): " & monitoring, vbInformation

CleanExit:
    Application.EnableEvents = True
    Application.ScreenUpdating = True
    Exit Sub

FatalError:
    errCount = errCount + 1
    On Error Resume Next
    wsE.Cells(wsE.Rows.Count, 1).End(xlUp).Offset(1, 0).Resize(1, 3).Value = Array("Loader", "Runtime", Err.Number & " - " & Err.Description)
    MsgBox "Loader stopped: " & Err.Description, vbCritical
    Resume CleanExit
End Sub

Private Sub CopyNormalizedRecord(ByVal src As Worksheet, ByVal h As Object, ByVal r As Long, ByVal dst As Worksheet, ByVal outRow As Long, ByVal sourceFile As String, ByVal company As String, ByVal tower As String, ByVal track As String)
    Dim fields As Variant, i As Long, val As Variant
    fields = Array("TicketNumber", "ParentTicketNumber", "TicketType", "ProjectName", "TrackName", "AssignmentGroup", "CompanyAccount", "CustomerName", "TowerName", "ConfigurationItem", "Service", "Device", "Caller", "Priority", "State", "Impact", "ShortDescription", "OpenedAt", "CreatedAt", "UpdatedAt", "ClosedAt", "CandidateForVE", "VETimeSavedMinutes", "ResolutionCode", "CauseCode", "SourceFile", "IsMonitoringGenerated")
    For i = LBound(fields) To UBound(fields)
        val = GetValue(src, h, r, UCase$(CStr(fields(i))))
        Select Case UCase$(CStr(fields(i)))
            Case "COMPANYACCOUNT": val = company
            Case "TOWERNAME": val = tower
            Case "TRACKNAME": If Len(track) > 0 Then val = track
            Case "SOURCEFILE": val = sourceFile
            Case "ISMONITORINGGENERATED": val = IsMonitoringCaller(CStr(GetValue(src, h, r, "CALLER")))
            Case "DEVICE": If Len(CStr(val)) = 0 Then val = GetValue(src, h, r, "PART")
            Case "TICKETTYPE": If Len(CStr(val)) = 0 Then val = IIf(Len(CStr(GetValue(src, h, r, "PARENTTICKETNUMBER"))) > 0, "Child", "Parent")
        End Select
        dst.Cells(outRow, i + 1).Value = val
    Next i
End Sub

Private Function HeaderIndex(ByVal ws As Worksheet) As Object
    Dim d As Object, c As Long, lastCol As Long, name As String
    Set d = CreateObject("Scripting.Dictionary")
    lastCol = ws.Cells(1, ws.Columns.Count).End(xlToLeft).Column
    For c = 1 To lastCol
        name = UCase$(Trim$(CStr(ws.Cells(1, c).Value)))
        If Len(name) > 0 Then
            d(name) = c
            Select Case name
                Case "NUMBER", "TICKETNUMBER", "TICKET NUMBER", "TICKET_NUMBER", "INCIDENT NUMBER", "INCIDENTNUMBER": d("TICKETNUMBER") = c
                Case "PARENT INCIDENT", "PARENTINCIDENT", "PARENT INCIDENT NUMBER", "PARENTTICKETNUMBER", "PARENT": d("PARENTTICKETNUMBER") = c
                Case "ASSIGNMENT GROUP", "ASSIGNMENTGROUP", "ASSIGNMENT_GROUP": d("ASSIGNMENTGROUP") = c
                Case "COMPANY ACCOUNT", "COMPANYACCOUNT", "COMPANY", "CUSTOMER": d("COMPANYACCOUNT") = c
                Case "SHORT DESCRIPTION", "SHORTDESCRIPTION", "SHORT_DESCRIPTION", "DESCRIPTION": d("SHORTDESCRIPTION") = c
                Case "CONFIGURATION ITEM", "CONFIGURATIONITEM", "CI": d("CONFIGURATIONITEM") = c
                Case "PART", "DEVICE": d("DEVICE") = c
            End Select
        End If
    Next c
    Set HeaderIndex = d
End Function

Private Function GetValue(ByVal ws As Worksheet, ByVal h As Object, ByVal r As Long, ByVal fieldName As String) As Variant
    If h.Exists(fieldName) Then GetValue = ws.Cells(r, h(fieldName)).Value Else GetValue = ""
End Function

Private Function NormalizeCompany(ByVal raw As Variant) As String
    Dim s As String
    s = Trim$(CStr(raw))
    If InStr(1, s, "Home", vbTextCompare) > 0 Then
        NormalizeCompany = "Home Depot"
    Else
        NormalizeCompany = s
    End If
End Function

Private Function IsMonitoringCaller(ByVal caller As String) As Boolean
    Dim s As String
    s = UCase$(Trim$(caller))
    IsMonitoringCaller = (InStr(1, s, "EMS", vbTextCompare) > 0 Or InStr(1, s, "CMSP", vbTextCompare) > 0)
End Function

Private Function LoadMapping() As Object
    Dim d As Object, ws As Worksheet, lastRow As Long, r As Long, k As String
    Dim a(1) As String
    Set d = CreateObject("Scripting.Dictionary")
    Set ws = ThisWorkbook.Worksheets(SHEET_MAP)
    lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
    For r = 2 To lastRow
        k = UCase$(Trim$(CStr(ws.Cells(r, 1).Value)))
        If Len(k) > 0 Then
            a(0) = CStr(ws.Cells(r, 3).Value)
            a(1) = CStr(ws.Cells(r, 4).Value)
            d(k) = a
        End If
    Next r
    Set LoadMapping = d
End Function

Private Function GetSelectedFiles(ByVal ws As Worksheet) As Collection
    Dim c As New Collection, r As Long, p As String
    For r = 9 To 20
        p = Trim$(CStr(ws.Cells(r, 2).Value))
        If Len(p) > 0 Then c.Add p
    Next r
    Set GetSelectedFiles = c
End Function

Private Sub BuildControlSheet()
    Dim ws As Worksheet
    Set ws = ThisWorkbook.Worksheets(SHEET_CONTROL)
    ws.Cells.Clear
    ws.Range("A1").Value = "QBR DATA LOADER"
    ws.Range("A2").Value = "Ticket & Alert Processing"
    ws.Range("A4").Value = "Customer"
    ws.Range("B4").Value = "Home Depot"
    ws.Range("A5").Value = "Status"
    ws.Range("B5").Value = "Ready"
    ws.Range("A6").Value = "Last Load"
    ws.Range("A7").Value = "Loaded Records"
    ws.Range("A8").Value = "Selected Files"
    ws.Range("A22").Value = "Use the buttons below. Customer/Tower/Track can be controlled through Customer Mapping."
    AddButton ws, "B2", "SELECT FILES", "SelectQBRFiles"
    AddButton ws, "D2", "LOAD DATA", "LoadQBRData"
    AddButton ws, "F2", "SETUP / RESET", "SetupQBRLoader"
    ws.Columns("A:F").AutoFit
    ws.Rows(1).Font.Bold = True
    ws.Rows(1).Font.Size = 18
End Sub

Private Sub BuildCustomerMapping()
    Dim ws As Worksheet, data, i As Long
    Set ws = ThisWorkbook.Worksheets(SHEET_MAP)
    ws.Cells.Clear
    ws.Range("A1:D1").Value = Array("CompanyAccount", "CustomerName", "TowerName", "TrackName")
    data = Array( _
        Array("Home Depot", "Home Depot", "Foundation", "THD Data"), _
        Array("Jio Platforms", "Jio Platforms", "", ""), _
        Array("HSBC", "HSBC", "Collaboration", "HSBC"), _
        Array("Bank of America", "Bank of America", "Collaboration", "BOA EV"), _
        Array("Reliance", "Reliance", "", ""), _
        Array("Problem Management", "Problem Management", "Collaboration", "Problem Management"), _
        Array("BOA TP", "BOA TP", "Collaboration", "BOA TP"), _
        Array("GTM TP", "GTM TP", "Collaboration", "GTM TP"), _
        Array("HD Voice (Bgl)", "HD Voice (Bgl)", "Collaboration", "HD Voice (Bgl)"), _
        Array("SCNOC", "SCNOC", "Collaboration", "SCNOC"), _
        Array("SFNOC", "SFNOC", "Foundation", "SFNOC"), _
        Array("HSBC Data", "HSBC Data", "Foundation", "HSBC Data"), _
        Array("RIL", "RIL", "Non-CMS", "RIL"), _
        Array("Cybersecurity", "Cybersecurity", "Security", "Cybersecurity"), _
        Array("DC-ACI", "DC-ACI", "Security", "DC-ACI"), _
        Array("Infra", "Infra", "Security", "Infra"), _
        Array("SOC", "SOC", "Security", "SOC"))
    For i = LBound(data) To UBound(data)
        ws.Cells(i + 2, 1).Resize(1, 4).Value = data(i)
    Next i
    ws.Columns("A:D").AutoFit
End Sub

Private Sub PrepareReportSheets()
    Dim ws As Worksheet, headers
    Set ws = ThisWorkbook.Worksheets(SHEET_LOADED)
    ws.Cells.Clear
    headers = Array("TicketNumber", "ParentTicketNumber", "TicketType", "ProjectName", "TrackName", "AssignmentGroup", "CompanyAccount", "CustomerName", "TowerName", "ConfigurationItem", "Service", "Device", "Caller", "Priority", "State", "Impact", "ShortDescription", "OpenedAt", "CreatedAt", "UpdatedAt", "ClosedAt", "CandidateForVE", "VETimeSavedMinutes", "ResolutionCode", "CauseCode", "SourceFile", "IsMonitoringGenerated")
    ws.Range("A1").Resize(1, UBound(headers) + 1).Value = headers
    ThisWorkbook.Worksheets(SHEET_DUP).Cells.Clear: ThisWorkbook.Worksheets(SHEET_DUP).Range("A1:D1").Value = Array("TicketNumber", "SourceFile", "FirstSeenInFile", "Reason")
    ThisWorkbook.Worksheets(SHEET_INVALID).Cells.Clear: ThisWorkbook.Worksheets(SHEET_INVALID).Range("A1:D1").Value = Array("SourceFile", "Row", "TicketNumber", "Reason")
    ThisWorkbook.Worksheets(SHEET_UNMAPPED).Cells.Clear: ThisWorkbook.Worksheets(SHEET_UNMAPPED).Range("A1:C1").Value = Array("CompanyAccount", "TicketNumber", "SourceFile")
    ThisWorkbook.Worksheets(SHEET_ERRORS).Cells.Clear: ThisWorkbook.Worksheets(SHEET_ERRORS).Range("A1:C1").Value = Array("File", "Sheet/Stage", "Error")
End Sub

Private Sub WriteSummary(ByVal ws As Worksheet, ByVal files As Long, ByVal total As Long, ByVal loaded As Long, ByVal dup As Long, ByVal invalid As Long, ByVal unmapped As Long, ByVal monitoring As Long, ByVal userTickets As Long, ByVal errors As Long)
    ws.Cells.Clear
    ws.Range("A1:B1").Value = Array("Metric", "Value")
    ws.Range("A2:B10").Value = Array( _
        Array("Files processed", files), _
        Array("Input records", total), _
        Array("Loaded records", loaded), _
        Array("Duplicate records", dup), _
        Array("Invalid records", invalid), _
        Array("Unmapped company", unmapped), _
        Array("Monitoring tickets (EMS/CMSP)", monitoring), _
        Array("User tickets", userTickets), _
        Array("Errors", errors))
    ws.Range("A12").Value = "Status"
    ws.Range("B12").Value = IIf(errors > 0 Or invalid > 0 Or unmapped > 0, "COMPLETED WITH WARNINGS", "COMPLETED")
    ws.Columns("A:B").AutoFit
End Sub

Private Sub FormatReportSheets()
    Dim n, ws As Worksheet
    For Each n In Array(SHEET_SUMMARY, SHEET_LOADED, SHEET_DUP, SHEET_INVALID, SHEET_UNMAPPED, SHEET_ERRORS, SHEET_MAP)
        Set ws = ThisWorkbook.Worksheets(CStr(n))
        If ws.Cells(1, 1).Value <> "" Then
            ws.Rows(1).Font.Bold = True
            ws.Rows(1).AutoFilter
            ws.Columns.AutoFit
        End If
    Next n
End Sub

Private Sub EnsureSheet(ByVal sheetName As String)
    Dim ws As Worksheet
    On Error Resume Next
    Set ws = ThisWorkbook.Worksheets(sheetName)
    On Error GoTo 0
    If ws Is Nothing Then
        ThisWorkbook.Worksheets.Add(After:=ThisWorkbook.Worksheets(ThisWorkbook.Worksheets.Count)).Name = sheetName
    End If
End Sub

Private Sub AddButton(ByVal ws As Worksheet, ByVal anchor As String, ByVal caption As String, ByVal macroName As String)
    Dim b As Button
    On Error Resume Next
    ws.Buttons(caption).Delete
    On Error GoTo 0
    Set b = ws.Buttons.Add(ws.Range(anchor).Left, ws.Range(anchor).Top, 110, 28)
    b.Caption = caption
    b.OnAction = macroName
End Sub
