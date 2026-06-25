$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PackageRoot = Split-Path -Parent $Root
$Target = Join-Path $PackageRoot "START_HERE.bat"
$ShortcutPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "SpriteForge Studio.lnk"
$WScriptShell = New-Object -ComObject WScript.Shell
$Shortcut = $WScriptShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Target
$Shortcut.WorkingDirectory = $PackageRoot
$Shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,44"
$Shortcut.Description = "Launch SpriteForge Studio Easy Mode"
$Shortcut.Save()
Write-Host "Created desktop shortcut: $ShortcutPath"
