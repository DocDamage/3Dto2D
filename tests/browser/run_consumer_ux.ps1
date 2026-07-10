param([int]$Port = 8897)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Artifacts = Join-Path $Root 'output\playwright'
New-Item -ItemType Directory -Force -Path $Artifacts | Out-Null
$Server = $null
$Pushed = $false

$BrowserCode = @'
async page => {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.waitForFunction(() => document.body.classList.contains('mode-simple') && document.querySelectorAll('.nav.consumer-primary').length === 6);
  await page.evaluate(() => setTheme('dark'));

  const primary = await page.locator('.nav.consumer-primary').evaluateAll(nodes => nodes.filter(node => getComputedStyle(node).display !== 'none').map(node => node.getAttribute('aria-label')));
  assert(JSON.stringify(primary) === JSON.stringify(['Home', 'Projects', 'Create', 'Studio', 'Review', 'Export']), 'Unexpected Creator navigation: ' + primary.join(', '));
  const visibleText = await page.locator('body').innerText();
  ['Architecture Guardrails', 'Batch matrix', 'Worker pool', 'immutable revision', 'typed DAG'].forEach(term => assert(!visibleText.includes(term), 'Creator mode exposes: ' + term));
  await page.locator('#view-guide').screenshot({path: 'consumer-home-dark.png'});

  const create = page.locator('[data-workflow="single"]');
  await create.focus();
  await create.click();
  await page.waitForFunction(() => !document.querySelector('#wizardModal')?.classList.contains('hidden'));
  assert(await page.locator('#wizardModal').getAttribute('role') === 'dialog', 'Creator is not a dialog.');
  assert(await page.locator('#wizardModal').evaluate(modal => modal.contains(document.activeElement)), 'Focus did not enter the creator.');
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => document.querySelector('#wizardModal')?.classList.contains('hidden'));
  assert(await create.evaluate(button => document.activeElement === button), 'Creator did not restore focus.');

  await page.getByRole('button', {name: 'Studio', exact: true}).click();
  await page.waitForFunction(() => document.body.dataset.activeView === 'aaa_studio');
  const visibleViews = await page.locator('.shell > .view').evaluateAll(nodes => nodes.filter(node => !node.hidden).length);
  assert(visibleViews === 1, 'Expected exactly one visible top-level view.');
  assert(await page.locator('#view-aaa_studio .aaa-inspector-panel').isHidden(), 'Infrastructure inspector is visible in Creator mode.');

  await page.setViewportSize({width: 390, height: 844});
  await page.evaluate(() => { setTheme('light'); showView('guide'); });
  await page.waitForFunction(() => document.body.dataset.activeView === 'guide');
  const mobileMetrics = await page.evaluate(() => {
    const toggle = document.querySelector('#mobileRailToggle').getBoundingClientRect();
    return {scrollWidth: document.documentElement.scrollWidth, viewport: innerWidth, width: toggle.width, height: toggle.height};
  });
  assert(mobileMetrics.scrollWidth <= mobileMetrics.viewport, 'Home has horizontal page overflow.');
  assert(mobileMetrics.width >= 44 && mobileMetrics.height >= 44, 'Mobile navigation target is smaller than 44px.');
  await page.locator('#mobileRailToggle').click();
  await page.waitForFunction(() => document.querySelector('#mobileRailToggle').getAttribute('aria-expanded') === 'true');
  await page.waitForFunction(() => document.querySelector('.rail')?.contains(document.activeElement));
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => document.querySelector('#mobileRailToggle').getAttribute('aria-expanded') === 'false');
  assert(await page.locator('#mobileRailToggle').evaluate(toggle => document.activeElement === toggle), 'Mobile menu did not restore focus.');
  await page.locator('#view-guide').screenshot({path: 'consumer-home-mobile.png'});

  return {passed: true, primary, mobileMetrics};
}
'@
$BrowserCode = $BrowserCode -replace '\r?\n', ' '

try {
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
    throw "Consumer UX browser acceptance failed: $($RunOutput -join ' ')"
  }
  $RunOutput | Set-Content -LiteralPath (Join-Path $Artifacts 'consumer-ux-result.txt') -Encoding UTF8
  if (-not ($RunOutput | Select-String -SimpleMatch 'passed')) { throw 'Consumer UX result was not returned.' }
}
finally {
  npx --yes --package @playwright/cli playwright-cli close 2>$null | Out-Null
  if ($Pushed) { Pop-Location }
  if ($Server) { Stop-Process -Id $Server.Id -Force -ErrorAction SilentlyContinue }
}
