$ErrorActionPreference = "Continue"

$projectRoot = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $projectRoot "app_data"
$logPath = Join-Path $logDir "supabase_deploy_sanitized.log"

New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$rawOutput = (& npx --yes supabase@latest functions deploy `
    --project-ref hnwvtoiiuqagzmuqygkw --use-api 2>&1 | Out-String)
$exitCode = $LASTEXITCODE

$sanitized = $rawOutput
$sanitized = $sanitized -replace 'sbp_[A-Za-z0-9_-]+', '[ACCESS_TOKEN_REMOVIDO]'
$sanitized = $sanitized -replace 'sb_(?:secret|publishable)_[A-Za-z0-9_-]+', '[API_KEY_REMOVIDA]'
$sanitized = $sanitized -replace 'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', '[JWT_REMOVIDO]'
$sanitized = $sanitized -replace '(?im)(access[_ -]?token|service[_ -]?role(?:[_ -]?key)?)\s*[:=]\s*\S+', '$1=[SEGREDO_REMOVIDO]'

$report = @(
    "ExitCode: $exitCode"
    "Timestamp: $([DateTimeOffset]::Now.ToString('o'))"
    ""
    $sanitized.Trim()
) -join [Environment]::NewLine

[System.IO.File]::WriteAllText($logPath, $report, [System.Text.UTF8Encoding]::new($false))

Write-Host ""
Write-Host "Resultado sanitizado:" -ForegroundColor Cyan
Write-Host $report
Write-Host ""
Write-Host "Diagnostico salvo sem credenciais em: $logPath" -ForegroundColor Green
