param([int]$Port = 8894, [string]$GoldenScreenshot = "")

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Artifacts = Join-Path $Root "output\playwright"
New-Item -ItemType Directory -Force -Path $Artifacts | Out-Null
$Server = $null
$Pushed = $false

try {
    if (-not (Get-Command npx -ErrorAction SilentlyContinue)) { throw "npx is required for browser tests." }
    $Server = Start-Process -FilePath python -ArgumentList @('-m','spriteforge_web','--port',"$Port",'--no-browser') -WorkingDirectory (Join-Path $Root 'app') -WindowStyle Hidden -PassThru
    $Ready = $false
    for ($Attempt = 0; $Attempt -lt 40; $Attempt++) {
        try { $Ready = (Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$Port/" -TimeoutSec 2).StatusCode -eq 200 } catch { $Ready = $false }
        if ($Ready) { break }
        Start-Sleep -Milliseconds 250
    }
    if (-not $Ready) { throw "SpriteForge browser-test server did not start." }
    Push-Location $Artifacts
    $Pushed = $true
    npx --yes --package @playwright/cli playwright-cli open "http://127.0.0.1:$Port/#production" | Out-Null
    npx --yes --package @playwright/cli playwright-cli run-code "async page => { await page.waitForFunction(()=>document.querySelector('#projectSelect')?.options.length>1); await page.evaluate(()=>{localStorage.setItem('uiMode','expert');setUiMode('expert');showView('production');}); await page.getByRole('button',{name:'Add node'}).click(); await page.getByLabel('Anchor and hitbox editor').click({position:{x:120,y:100}}); await page.getByRole('button',{name:'Add hitbox'}).click(); }" | Out-Null
    $Snapshot = npx --yes --package @playwright/cli playwright-cli snapshot
    $Snapshot | Set-Content -LiteralPath (Join-Path $Artifacts 'production-studio.snapshot.txt') -Encoding UTF8
    foreach ($Expected in @('Production Studio','Animation workspace','Batch matrix','Workflow builder','Recovery snapshots','hitbox_1','source.asset','qa.asset')) {
        if (-not ($Snapshot | Select-String -SimpleMatch $Expected)) { throw "Browser snapshot is missing: $Expected" }
    }
    npx --yes --package @playwright/cli playwright-cli screenshot | Out-Null
    npx --yes --package @playwright/cli playwright-cli run-code "async page => { await page.locator('#view-production').screenshot({path:'production-studio.png'}); }" | Out-Null
    if ($GoldenScreenshot) {
        $Golden = (Resolve-Path -LiteralPath $GoldenScreenshot).Path
        $env:SPRITEFORGE_UI_CURRENT = (Join-Path $Artifacts 'production-studio.png')
        $env:SPRITEFORGE_UI_GOLDEN = $Golden
        & python -c "import os,sys; from pathlib import Path; sys.path.insert(0, str(Path(r'$Root')/'app')); from services.visual_regression_service import compare_ui_screenshot; r=compare_ui_screenshot(Path(os.environ['SPRITEFORGE_UI_CURRENT']),Path(os.environ['SPRITEFORGE_UI_GOLDEN']),report_path=Path(os.environ['SPRITEFORGE_UI_CURRENT']).with_suffix('.visual.json')); raise SystemExit(0 if r['ok'] else 1)"
        if ($LASTEXITCODE -ne 0) { throw "Production Studio visual regression exceeded tolerance." }
    }
    [ordered]@{schema='spriteforge.browser_test.v1';passed=$true;url="http://127.0.0.1:$Port/#production";checked_at=(Get-Date).ToUniversalTime().ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Artifacts 'production-studio-result.json') -Encoding UTF8
} finally {
    npx --yes --package @playwright/cli playwright-cli close 2>$null | Out-Null
    if ($Pushed) { Pop-Location }
    if ($Server) { Stop-Process -Id $Server.Id -Force -ErrorAction SilentlyContinue }
}
