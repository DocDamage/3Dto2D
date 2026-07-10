param(
    [string]$Version = "1.2.0",
    [string]$OutputDir = "dist",
    [string]$CertificateThumbprint = "",
    [Parameter(Mandatory=$true)][string]$PythonRuntimeZip,
    [Parameter(Mandatory=$true)][string]$PythonRuntimeSha256,
    [string]$BuilderPython = "python"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$BuilderPythonPath = (Get-Command $BuilderPython -ErrorAction Stop).Source
$Dist = Join-Path $RepoRoot $OutputDir
$PortableStage = Join-Path $Dist "SpriteForgeStudio-$Version-portable"
$PortableZip = Join-Path $Dist "SpriteForgeStudio-$Version-portable.zip"

New-Item -ItemType Directory -Force -Path $Dist | Out-Null
if (Test-Path $PortableStage) { Remove-Item -LiteralPath $PortableStage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $PortableStage | Out-Null

$ExcludedDirectories = @(".git", ".venv", ".pytest_cache", "dist", "output", "projects", "models", "logs", "releases", "scratch", "state", "__pycache__", "vendor", "lpc_assets")
$ExcludedFiles = @("dist_release.zip", "qa_server_*.log", "*.pyc")
# Copy through Robocopy so exclusions apply recursively. In particular, do not
# ship development virtual environments, vendor checkouts, generated output,
# or a previous portable archive inside the next installer.
$RoboArgs = @($RepoRoot, $PortableStage, "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/XD") + $ExcludedDirectories + @("/XF") + $ExcludedFiles
& robocopy @RoboArgs | Out-Host
if ($LASTEXITCODE -gt 7) { throw "Release staging copy failed with Robocopy exit code $LASTEXITCODE." }
$RuntimeArchive = (Resolve-Path -LiteralPath $PythonRuntimeZip).Path
$RuntimeHash = (Get-FileHash -LiteralPath $RuntimeArchive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($RuntimeHash -ne $PythonRuntimeSha256.ToLowerInvariant()) { throw "Python runtime SHA-256 mismatch." }
$RuntimeDir = Join-Path $PortableStage "runtime"
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
Expand-Archive -LiteralPath $RuntimeArchive -DestinationPath $RuntimeDir -Force
$RuntimePython = Join-Path $RuntimeDir "python.exe"
$BuilderVersion = (& $BuilderPythonPath -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
$RuntimeVersion = (& $RuntimePython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
if ($BuilderVersion -ne $RuntimeVersion) {
    throw "Builder Python $BuilderVersion does not match embedded runtime $RuntimeVersion. Use a matching BuilderPython."
}
$Pth = Get-ChildItem -LiteralPath $RuntimeDir -Filter "python*._pth" | Select-Object -First 1
if (-not $Pth) { throw "The supplied archive is not a Windows embeddable Python runtime." }
$PthLines = Get-Content -LiteralPath $Pth.FullName
$PthLines = @($PthLines | ForEach-Object { if ($_ -eq '#import site') { 'import site' } else { $_ } }) + 'Lib\site-packages' + '..\app'
$PthLines | Select-Object -Unique | Set-Content -LiteralPath $Pth.FullName -Encoding ASCII
$SitePackages = Join-Path $RuntimeDir "Lib\site-packages"
New-Item -ItemType Directory -Force -Path $SitePackages | Out-Null
& $BuilderPythonPath -m pip install --requirement (Join-Path $RepoRoot "requirements-lock.txt") --target $SitePackages --no-compile
if ($LASTEXITCODE -ne 0) { throw "Dependency installation into bundled runtime failed." }
& (Join-Path $RuntimeDir "python.exe") (Join-Path $PortableStage "app\spriteforge_web.py") --smoke
if ($LASTEXITCODE -ne 0) { throw "Bundled runtime smoke test failed." }
$CscCandidates = @(
    (Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"),
    (Join-Path $env:WINDIR "Microsoft.NET\Framework\v4.0.30319\csc.exe")
)
$Csc = $CscCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $Csc) { throw "The Windows .NET Framework C# compiler is required to build the launcher." }
& $Csc /nologo /target:winexe /reference:System.Windows.Forms.dll "/out:$($PortableStage)\SpriteForgeStudio.exe" (Join-Path $PSScriptRoot "SpriteForgeLauncher.cs")
if ($LASTEXITCODE -ne 0) { throw "SpriteForge launcher compilation failed." }
if (Test-Path $PortableZip) { Remove-Item -LiteralPath $PortableZip -Force }
Compress-Archive -Path (Join-Path $PortableStage "*") -DestinationPath $PortableZip -CompressionLevel Optimal

$IsccCandidates = @(
    (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source,
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
)
$Iscc = $IsccCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if (-not $Iscc) { throw "Inno Setup 6 (ISCC.exe) is required to build the installer." }
& $Iscc "/DAppVersion=$Version" "/DSourceRoot=$PortableStage" "/O$Dist" (Join-Path $PSScriptRoot "SpriteForgeStudio.iss")
if ($LASTEXITCODE -ne 0) { throw "Installer compilation failed with exit code $LASTEXITCODE." }

$Installer = Get-ChildItem -LiteralPath $Dist -Filter "SpriteForgeStudio-*-Setup.exe" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $Installer) { throw "Installer compilation completed without producing a setup executable." }
if ($CertificateThumbprint) {
    $SignTool = (Get-Command signtool.exe -ErrorAction SilentlyContinue).Source
    if (-not $SignTool) { throw "signtool.exe is required when CertificateThumbprint is supplied." }
    & $SignTool sign /sha1 $CertificateThumbprint /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $Installer.FullName
}

$Artifacts = @($PortableZip, $Installer.FullName)
$Manifest = [ordered]@{
    schema = "spriteforge.release_manifest.v1"
    version = $Version
    created_at = (Get-Date).ToUniversalTime().ToString("o")
    artifacts = @($Artifacts | ForEach-Object {
        $File = Get-Item -LiteralPath $_
        [ordered]@{ name = $File.Name; size_bytes = $File.Length; sha256 = (Get-FileHash -LiteralPath $File.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
    })
}
$Manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Dist "release-manifest.json") -Encoding UTF8
$SourceRevision = (git -C $RepoRoot rev-parse HEAD 2>$null)
if (-not $SourceRevision) { $SourceRevision = "unknown" }
$env:PYTHONPATH = Join-Path $RepoRoot "app"
& $BuilderPythonPath -m tools.release_trust --requirements (Join-Path $RepoRoot "requirements-lock.txt") --sbom (Join-Path $Dist "sbom.cdx.json") --provenance (Join-Path $Dist "provenance.intoto.jsonl") --source-revision $SourceRevision --builder-id "spriteforge-windows-builder" $PortableZip $Installer.FullName
if ($LASTEXITCODE -ne 0) { throw "SBOM/provenance generation failed." }
$Manifest | ConvertTo-Json -Depth 5
