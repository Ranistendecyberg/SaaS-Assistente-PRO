param([switch]$CheckTools)
$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $PSScriptRoot
$toolsDir = Join-Path $projectDir '.build_tools\postgres-backup\runtime\pgsql\bin'
$dumpTool = Join-Path $toolsDir 'pg_dump.exe'
$restoreTool = Join-Path $toolsDir 'pg_restore.exe'
$caFile = Join-Path $projectDir '.build_tools\postgres-backup\prod-ca-2021.crt'
foreach ($tool in @($dumpTool, $restoreTool)) {
    if (-not (Test-Path -LiteralPath $tool -PathType Leaf)) { throw "Ferramenta ausente: $tool" }
    & $tool --version
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao iniciar ferramenta PostgreSQL.' }
}
if (-not (Test-Path -LiteralPath $caFile -PathType Leaf)) { throw "Certificado Supabase ausente: $caFile" }
$expectedCaHash = '700723581420DD1AC98FD7E9AC529F0EF210EADCAF87FC868A3AD7D114C2F3B7'
if ((Get-FileHash -LiteralPath $caFile -Algorithm SHA256).Hash -ne $expectedCaHash) {
    throw 'O certificado Supabase local nao corresponde ao arquivo oficial validado. Nao conectar.'
}
if ($CheckTools) { return }

# Never accept a password argument, save credentials, or run migration/restore here.
$outputDir = Join-Path $projectDir ('private_db_backups\pre020_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '_' + [guid]::NewGuid().ToString('N').Substring(0,8))
New-Item -ItemType Directory -Path $outputDir | Out-Null
$ownerSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
& icacls.exe $outputDir /inheritance:r /grant:r "*${ownerSid}:(OI)(CI)F" '*S-1-5-18:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel restringir acesso a pasta de backup.' }
$partial = Join-Path $outputDir 'database.partial.dump'
$completed = Join-Path $outputDir 'database.dump'
$catalog = Join-Path $outputDir 'archive_contents.txt'
$connection = 'host=aws-0-sa-east-1.pooler.supabase.com port=5432 dbname=postgres user=postgres.hnwvtoiiuqagzmuqygkw sslmode=verify-full gssencmode=disable connect_timeout=20'
Write-Host 'Projeto: saas-assistente-desktop-v2-prod (hnwvtoiiuqagzmuqygkw)'
Write-Host 'Digite a senha do BANCO no prompt Password. Os caracteres nao serao exibidos.'
Write-Host 'Somente leitura remota. Nenhuma migracao sera aplicada.'
# Full logical database dump. Any privilege/version/TLS error fails closed.
$previousCa = $env:PGSSLROOTCERT
try {
    $env:PGSSLROOTCERT = $caFile
    $dumpArgs = @("--dbname=$connection", '--password', '--format=custom', '--lock-wait-timeout=30000', "--file=$partial")
    & $dumpTool $dumpArgs
    if ($LASTEXITCODE -ne 0) { throw "Backup falhou. Arquivo parcial NAO e backup valido: $partial" }
} finally {
    if ($null -eq $previousCa) { Remove-Item Env:PGSSLROOTCERT -ErrorAction SilentlyContinue }
    else { $env:PGSSLROOTCERT = $previousCa }
}
$restoreArgs = @('--list', "--file=$catalog", $partial)
& $restoreTool $restoreArgs
if ($LASTEXITCODE -ne 0) { throw 'Falha ao ler o catalogo do backup. Nao prosseguir com implantacao.' }
Move-Item -LiteralPath $partial -Destination $completed
$digest = (Get-FileHash -LiteralPath $completed -Algorithm SHA256).Hash
@("Project: hnwvtoiiuqagzmuqygkw", "Created: $([DateTimeOffset]::Now.ToString('o'))", "SHA256: $digest", 'Logical database archive; listing verified; isolated restore test still required.', 'Does not include Storage file contents, Edge Functions, secrets or platform settings.') | Set-Content -LiteralPath (Join-Path $outputDir 'verification.txt') -Encoding UTF8
Write-Host "Backup gerado: $completed" -ForegroundColor Green
Write-Host "SHA256: $digest"
Write-Host 'Ainda falta teste de restauracao isolada. Nao envie o dump ou a senha no chat.'
