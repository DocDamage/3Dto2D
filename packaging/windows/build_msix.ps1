param(
  [Parameter(Mandatory=$true)][string]$PackageRoot,
  [Parameter(Mandatory=$true)][string]$Publisher,
  [Parameter(Mandatory=$true)][string]$Version,
  [Parameter(Mandatory=$true)][string]$CertificateThumbprint,
  [string]$Output = "dist\SpriteForgeStudio.msix"
)
$ErrorActionPreference = "Stop"
$MakeAppx=(Get-Command makeappx.exe -ErrorAction SilentlyContinue).Source
$SignTool=(Get-Command signtool.exe -ErrorAction SilentlyContinue).Source
if(-not $MakeAppx -or -not $SignTool){throw "Windows SDK makeappx.exe and signtool.exe are required."}
$Root=(Resolve-Path -LiteralPath $PackageRoot).Path
$Assets=Join-Path $Root 'Assets'; New-Item -ItemType Directory -Force -Path $Assets | Out-Null
Add-Type -AssemblyName System.Drawing
foreach($Logo in @(@('StoreLogo.png',50),@('Square44x44Logo.png',44),@('Square150x150Logo.png',150))){
  $Bitmap=New-Object System.Drawing.Bitmap($Logo[1],$Logo[1]);$Graphics=[System.Drawing.Graphics]::FromImage($Bitmap);$Graphics.Clear([System.Drawing.Color]::FromArgb(15,23,42));$Font=New-Object System.Drawing.Font('Segoe UI',([float]$Logo[1]/4),[System.Drawing.FontStyle]::Bold);$Graphics.DrawString('SF',$Font,[System.Drawing.Brushes]::DeepSkyBlue,2,([float]$Logo[1]/3));$Bitmap.Save((Join-Path $Assets $Logo[0]),[System.Drawing.Imaging.ImageFormat]::Png);$Graphics.Dispose();$Bitmap.Dispose()
}
$ManifestTemplate=Get-Content -Raw (Join-Path $PSScriptRoot 'AppxManifest.xml')
$ManifestTemplate=$ManifestTemplate.Replace('CN=SPRITEFORGE_PUBLISHER',$Publisher).Replace('1.2.0.0',$Version)
$ManifestTemplate | Set-Content -LiteralPath (Join-Path $Root 'AppxManifest.xml') -Encoding UTF8
& $MakeAppx pack /d $Root /p $Output /o
if($LASTEXITCODE -ne 0){throw "MSIX packaging failed."}
& $SignTool sign /sha1 $CertificateThumbprint /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $Output
if($LASTEXITCODE -ne 0){throw "MSIX signing failed."}
