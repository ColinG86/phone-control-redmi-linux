$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Control Phone.lnk')
$Shortcut.TargetPath = 'python.exe'
$Shortcut.Arguments = 'C:\Projects\scrcpy\phone_control_gui.py'
$Shortcut.WorkingDirectory = 'C:\Projects\scrcpy'
$Shortcut.IconLocation = 'C:\Windows\System32\shell32.dll,41'
$Shortcut.Description = 'Phone Control GUI - Connect to Redmi 10 2022'
$Shortcut.Save()

Write-Host 'Desktop shortcut updated to use python.exe!'
Write-Host 'Double-click "Control Phone" on your desktop to launch the GUI'
