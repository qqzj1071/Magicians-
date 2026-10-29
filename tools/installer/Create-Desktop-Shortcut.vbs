Option Explicit
Dim shell, fso, folder, shortcut
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
If Not fso.FileExists(fso.BuildPath(folder, "Magicians.exe")) Then
    MsgBox "Please extract the whole game folder first.", 16, "Magicians!"
    WScript.Quit 1
End If
Set shortcut = shell.CreateShortcut(fso.BuildPath(shell.SpecialFolders("Desktop"), "Magicians! Single Player.lnk"))
shortcut.TargetPath = fso.BuildPath(folder, "Magicians.exe")
shortcut.WorkingDirectory = folder
shortcut.IconLocation = shortcut.TargetPath & ",0"
shortcut.Save
MsgBox "Desktop shortcut created. Keep the game folder in this location.", 64, "Magicians!"
