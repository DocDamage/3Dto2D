param([int]$Port = 8895)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Artifacts = Join-Path $Root 'output\playwright'
New-Item -ItemType Directory -Force -Path $Artifacts | Out-Null
$ProjectDir = Join-Path $Root 'app\projects\AAA_Browser_Test'
$Server = $null
$Pushed = $false

$BrowserCode = @'
async page => {
  const check = async (label, fn) => {
    try { await page.waitForFunction(fn, null, {timeout: 5000}); }
    catch (error) { throw new Error(label + ': ' + error.message); }
  };
  await check('app-ready', () => document.querySelector('#projectSelect')?.options.length > 1);
  await page.evaluate(() => { localStorage.setItem('uiMode', 'expert'); setUiMode('expert'); });
  await page.evaluate(async () => {
    await api('/api/projects/create', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name: 'AAA Browser Test'})
    });
  });
  await page.reload();
  await check('project-created', () => document.querySelector('#projectSelect')?.selectedOptions[0]?.textContent === 'AAA_Browser_Test');
  await page.evaluate(() => showView('aaa_studio'));
  await page.getByRole('button', {name: 'New', exact: true}).click();
  await check('document-created', () => document.querySelectorAll('#aaaLayerTree .aaa-layer-row').length === 1);
  await page.getByLabel('Layered sprite editing canvas').click({position: {x: 140, y: 120}});
  await page.getByRole('button', {name: 'Add', exact: true}).click();
  await check('layer-added', () => document.querySelectorAll('#aaaLayerTree .aaa-layer-row').length === 2);
  await page.getByRole('button', {name: 'Add key'}).click();
  await page.getByRole('button', {name: 'Save revision'}).click();
  await check('revision-saved', () => document.querySelector('#aaaCanvasStatus')?.textContent === 'Saved just now.');
  await page.getByRole('button', {name: 'Save workspace'}).click();
  await check('workspace-saved', () => document.querySelector('#aaaCanvasStatus')?.textContent === 'Workspace saved.');
  await page.locator('#view-aaa_studio').screenshot({path: 'aaa-studio.png'});
  return await page.locator('#view-aaa_studio').innerText();
}
'@
$BrowserCode = $BrowserCode -replace '\r?\n', ' '

try {
  if (Test-Path $ProjectDir) { Remove-Item -LiteralPath $ProjectDir -Recurse -Force }
  $Server = Start-Process -FilePath python -ArgumentList @('-m', 'spriteforge_web', '--port', "$Port", '--no-browser') -WorkingDirectory (Join-Path $Root 'app') -WindowStyle Hidden -PassThru
  $Ready = $false
  for ($i = 0; $i -lt 40; $i++) {
    try { $Ready = (Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$Port/" -TimeoutSec 2).StatusCode -eq 200 }
    catch { $Ready = $false }
    if ($Ready) { break }
    Start-Sleep -Milliseconds 250
  }
  if (-not $Ready) { throw 'Server did not start.' }
  Push-Location $Artifacts
  $Pushed = $true
  $OpenOutput = npx --yes --package @playwright/cli playwright-cli open "http://127.0.0.1:$Port/"
  if ($LASTEXITCODE -ne 0) { throw "Playwright open failed: $($OpenOutput -join ' ')" }
  $RunOutput = npx --yes --package @playwright/cli playwright-cli run-code $BrowserCode
  if ($LASTEXITCODE -ne 0 -or ($RunOutput | Select-String -SimpleMatch '### Error')) {
    throw "AAA browser interaction failed: $($RunOutput -join ' ')"
  }
  $Snapshot = $RunOutput
  $Snapshot | Set-Content -LiteralPath (Join-Path $Artifacts 'aaa-studio.snapshot.txt') -Encoding UTF8
  foreach ($Expected in @('Animation Studio', 'renderer: webgl2', 'Layer 2', 'Animation frames', 'Workspace saved.')) {
    if (-not ($Snapshot | Select-String -SimpleMatch $Expected)) { throw "AAA browser snapshot is missing: $Expected" }
  }
  [ordered]@{
    schema = 'spriteforge.aaa_browser_test.v1'
    passed = $true
    checked_at = (Get-Date).ToUniversalTime().ToString('o')
  } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Artifacts 'aaa-studio-result.json') -Encoding UTF8
}
finally {
  npx --yes --package @playwright/cli playwright-cli close 2>$null | Out-Null
  if ($Pushed) { Pop-Location }
  if ($Server) { Stop-Process -Id $Server.Id -Force -ErrorAction SilentlyContinue }
  if (Test-Path $ProjectDir) {
    $Resolved = (Resolve-Path $ProjectDir).Path
    if ($Resolved.StartsWith((Join-Path $Root 'app\projects'), [System.StringComparison]::OrdinalIgnoreCase)) {
      Remove-Item -LiteralPath $Resolved -Recurse -Force
    }
  }
}
