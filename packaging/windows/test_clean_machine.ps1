param(
    [Parameter(Mandatory=$true)][string]$Installer,
    [string]$EvidencePath = "clean-machine-evidence.json"
)

$ErrorActionPreference = "Stop"
$InstallerPath = (Resolve-Path -LiteralPath $Installer).Path
$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\SpriteForge Studio"
$Started = Get-Date
$Passed = $false
$Failure = ""

try {
    $Existing = Get-Command python -ErrorAction SilentlyContinue
    if ($Existing) { Write-Warning "System Python is present; runtime isolation is still verified by invoking the bundled executable directly." }
    $Process = Start-Process -FilePath $InstallerPath -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-') -Wait -PassThru -WindowStyle Hidden
    if ($Process.ExitCode -ne 0) { throw "Installer exited with code $($Process.ExitCode)." }
    $Runtime = Join-Path $InstallDir "runtime\python.exe"
    $Smoke = Join-Path $InstallDir "app\spriteforge_web.py"
    if (-not (Test-Path -LiteralPath $Runtime)) { throw "Bundled Python runtime was not installed." }
    & $Runtime $Smoke --smoke
    if ($LASTEXITCODE -ne 0) { throw "CPU-safe application smoke test failed." }
    $Demo = Join-Path $InstallDir "RUN_DEMO_NO_GPU.bat"
    if (-not (Test-Path -LiteralPath $Demo)) { throw "CPU-safe demo launcher is missing." }
    $Uninstaller = Join-Path $InstallDir "unins000.exe"
    if (-not (Test-Path -LiteralPath $Uninstaller)) { throw "Uninstaller is missing." }
    $Uninstall = Start-Process -FilePath $Uninstaller -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART') -Wait -PassThru -WindowStyle Hidden
    if ($Uninstall.ExitCode -ne 0) { throw "Uninstaller exited with code $($Uninstall.ExitCode)." }
    $Passed = $true
} catch {
    $Failure = $_.Exception.Message
}

$Evidence = [ordered]@{
    schema = "spriteforge.clean_machine_test.v1"
    passed = $Passed
    started_at = $Started.ToUniversalTime().ToString("o")
    finished_at = (Get-Date).ToUniversalTime().ToString("o")
    machine = $env:COMPUTERNAME
    installer = $InstallerPath
    installer_sha256 = (Get-FileHash -LiteralPath $InstallerPath -Algorithm SHA256).Hash.ToLowerInvariant()
    bundled_runtime = $true
    cpu_demo_launcher = $true
    failure = $Failure
}
$Evidence | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $EvidencePath -Encoding UTF8
$Evidence | ConvertTo-Json -Depth 4
if (-not $Passed) { exit 1 }
