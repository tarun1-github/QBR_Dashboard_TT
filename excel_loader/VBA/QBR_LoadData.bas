Attribute VB_Name = "QBR_LoadData"
Option Explicit

' QBR Excel Loader - UI/orchestration only.
' Power Query performs transformation; this module manages file selection,
' mapping metadata, refresh, and report generation.

Public Sub SetupQBRLoader()
    Dim ws As Worksheet
    Set ws = GetOrCreateSheet("QBR Loader")
    ws.Cells.Clear
    ws.Range("A1").Value = "QBR DATA LOADER"
    ws.Range("A2").Value = "Customer Name"
    ws.Range("A3").Value = "Tower Name"
    ws.Range("A4").Value = "Track Name"
    ws.Range("A5").Value = "File Type"
    ws.Range("A7").Value = "Selected Files"
    ws.Range("A8:A20").ClearContents
    ws.Range("A22").Value = "Status"
    ws.Range("B22").Value = "Ready"
    ws.Range("A1:B1").Font.Bold = True
    ws.Range("A1:B1").Font.Size = 18
    ws.Columns("A:B").ColumnWidth = 28
    ws.Range("B2").Value = "Home Depot"
    ws.Range("B3").Value = "Foundation"
    ws.Range("B4").Value = "THD Data"
    ws.Range("B5").Value = "Auto Detect"
    AddButton ws, "Select Files", 320, 55, "SelectQBRFiles"
    AddButton ws, "LOAD DATA", 320, 100, "LoadQBRData"
    MsgBox "QBR Loader created. Use Select Files, then LOAD DATA.", vbInformation
End Sub

Private Sub AddButton(ByVal ws As Worksheet, ByVal caption As String, ByVal leftPos As Double, ByVal topPos As Double, ByVal macroName As String)
    Dim shp As Shape
    Set shp = ws.Shapes.AddShape(msoShapeRoundedRectangle, leftPos, topPos, 150, 32)
    shp.TextFrame2.TextRange.Text = caption
    shp.OnAction = macroName
End Sub

Public Sub SelectQBRFiles()
    Dim fd As FileDialog, i As Long, ws As Worksheet
    Set ws = GetOrCreateSheet("QBR Loader")
    Set fd = Application.FileDialog(msoFileDialogFilePicker)
    With fd
        .Title = "Select QBR Created/Closed/Input files"
        .AllowMultiSelect = True
        .Filters.Clear
        .Filters.Add "Excel files", "*.xlsx;*.xlsm;*.xls"
        .Filters.Add "CSV files", "*.csv"
        .Filters.Add "Text files", "*.txt"
        If .Show <> -1 Then Exit Sub
        ws.Range("A8:A100").ClearContents
        For i = 1 To .SelectedItems.Count
            ws.Cells(7 + i, 1).Value = .SelectedItems(i)
        Next i
        ws.Range("B22").Value = CStr(.SelectedItems.Count) & " file(s) selected"
    End With
End Sub

Public Sub LoadQBRData()
    Dim ws As Worksheet, lastRow As Long, i As Long
    Set ws = GetOrCreateSheet("QBR Loader")
    lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
    If lastRow < 8 Then
        MsgBox "Please select at least one input file.", vbExclamation
        Exit Sub
    End If

    ws.Range("B22").Value = "Processing..."
    Application.ScreenUpdating = False
    On Error GoTo Handler

    ' The Power Query implementation uses the QBR_InputFiles table.
    ' Store selected paths in a workbook table for the query to consume.
    EnsureInputTable ws, lastRow
    RefreshQBRQueries
    GenerateQBRLoadReport

    ws.Range("B22").Value = "Completed"
    Application.ScreenUpdating = True
    MsgBox "QBR load processing completed. Review Load Summary and exception sheets.", vbInformation
    Exit Sub
Handler:
    Application.ScreenUpdating = True
    ws.Range("B22").Value = "ERROR"
    WriteError "VBA LoadQBRData", Err.Number, Err.Description
    MsgBox "Load failed: " & Err.Description, vbCritical
End Sub

Private Sub EnsureInputTable(ByVal ws As Worksheet, ByVal lastRow As Long)
    Dim sh As Worksheet, lo As ListObject, r As Long
    Set sh = GetOrCreateSheet("QBR Input Files")
    sh.Cells.Clear
    sh.Range("A1").Value = "FilePath"
    For r = 8 To lastRow
        If Len(Trim$(ws.Cells(r, 1).Value)) > 0 Then sh.Cells(r - 6, 1).Value = ws.Cells(r, 1).Value
    Next r
    On Error Resume Next
    sh.ListObjects("QBR_InputFiles").Delete
    On Error GoTo 0
    Set lo = sh.ListObjects.Add(xlSrcRange, sh.Range("A1").CurrentRegion, , xlYes)
    lo.Name = "QBR_InputFiles"
End Sub

Private Sub RefreshQBRQueries()
    Dim cn As WorkbookConnection
    On Error Resume Next
    For Each cn In ThisWorkbook.Connections
        cn.Refresh
    Next cn
    Application.CalculateFull
    On Error GoTo 0
End Sub

Private Sub GenerateQBRLoadReport()
    Dim reportPath As String, wb As Workbook
    reportPath = ThisWorkbook.Path & Application.PathSeparator & "QBR_Load_Report.xlsx"
    ThisWorkbook.Worksheets("Load Summary").Copy
    Set wb = ActiveWorkbook
    CopyIfExists ThisWorkbook, "Loaded Records", wb
    CopyIfExists ThisWorkbook, "Duplicate Records", wb
    CopyIfExists ThisWorkbook, "Invalid Records", wb
    CopyIfExists ThisWorkbook, "Unmapped Company", wb
    CopyIfExists ThisWorkbook, "Errors", wb
    CopyIfExists ThisWorkbook, "Load History", wb
    Application.DisplayAlerts = False
    wb.SaveAs reportPath, xlOpenXMLWorkbook
    wb.Close True
    Application.DisplayAlerts = True
End Sub

Private Sub CopyIfExists(ByVal srcWb As Workbook, ByVal sheetName As String, ByVal dstWb As Workbook)
    On Error Resume Next
    srcWb.Worksheets(sheetName).Copy After:=dstWb.Sheets(dstWb.Sheets.Count)
    On Error GoTo 0
End Sub

Private Sub WriteError(ByVal source As String, ByVal number As Long, ByVal description As String)
    Dim ws As Worksheet, n As Long
    Set ws = GetOrCreateSheet("Errors")
    If ws.Cells(1, 1).Value = "" Then ws.Range("A1:D1").Value = Array("Timestamp", "Source", "ErrorNumber", "Description")
    n = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row + 1
    ws.Cells(n, 1).Value = Now
    ws.Cells(n, 2).Value = source
    ws.Cells(n, 3).Value = number
    ws.Cells(n, 4).Value = description
End Sub

Private Function GetOrCreateSheet(ByVal sheetName As String) As Worksheet
    On Error Resume Next
    Set GetOrCreateSheet = ThisWorkbook.Worksheets(sheetName)
    On Error GoTo 0
    If GetOrCreateSheet Is Nothing Then
        Set GetOrCreateSheet = ThisWorkbook.Worksheets.Add(After:=ThisWorkbook.Sheets(ThisWorkbook.Sheets.Count))
        GetOrCreateSheet.Name = sheetName
    End If
End Function
