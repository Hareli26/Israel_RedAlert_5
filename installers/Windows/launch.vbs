Dim fso, wsh, installDir, localDir, exe, py, pythonw, cmd

Set fso = CreateObject("Scripting.FileSystemObject")
Set wsh = CreateObject("WScript.Shell")

' ── נתיב התקנה קבוע (גבוה) ואחר-כך נתיב הסקריפט (גיבוי) ──────
installDir = "C:\RedAlertIDF"
localDir   = fso.GetParentFolderName(WScript.ScriptFullName)

' ── 1. חפש EXE ב-C:\RedAlertIDF קודם, אחר-כך ליד הסקריפט ──────
exe = ""
If fso.FileExists(installDir & "\RedAlertMonitor.exe") Then
    exe = installDir & "\RedAlertMonitor.exe"
ElseIf fso.FileExists(localDir & "\RedAlertMonitor.exe") Then
    exe = localDir & "\RedAlertMonitor.exe"
End If

If exe <> "" Then
    wsh.Run """" & exe & """", 0, False
    WScript.Quit
End If

' ── 2. חפש red_alert.py ב-C:\RedAlertIDF קודם, אחר-כך ליד הסקריפט
py = ""
If fso.FileExists(installDir & "\red_alert.py") Then
    py = installDir & "\red_alert.py"
ElseIf fso.FileExists(localDir & "\red_alert.py") Then
    py = localDir & "\red_alert.py"
End If

If py = "" Then
    MsgBox "RedAlertMonitor.exe לא נמצא." & vbCrLf & _
           "הרץ build_exe.bat ליצירת ה-EXE, או install.bat להתקנה מלאה.", _
           16, "Red Alert Monitor"
    WScript.Quit
End If

' ── 3. מצא pythonw.exe (ללא חלון console) ──────────────────────
pythonw = ""

On Error Resume Next
Dim oExec, pyLine, pyDir
Set oExec = wsh.Exec("cmd /c where python 2>nul")
pyLine = Trim(oExec.StdOut.ReadLine())
If pyLine <> "" Then
    pyDir   = fso.GetParentFolderName(pyLine)
    pythonw = pyDir & "\pythonw.exe"
    If Not fso.FileExists(pythonw) Then pythonw = ""
End If
On Error GoTo 0

If pythonw = "" Then
    On Error Resume Next
    Set oExec = wsh.Exec("cmd /c where py 2>nul")
    pyLine = Trim(oExec.StdOut.ReadLine())
    On Error GoTo 0
    If pyLine <> "" Then pythonw = pyLine
End If

' ── 4. הפעל ────────────────────────────────────────────────────
If pythonw <> "" Then
    cmd = """" & pythonw & """ """ & py & """"
Else
    cmd = "python """ & py & """"
End If

wsh.Run cmd, 0, False
