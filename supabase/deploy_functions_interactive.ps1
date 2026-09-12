$ErrorActionPreference = "Stop"

Write-Host "Implantacao segura das Edge Functions" -ForegroundColor Cyan
Write-Host "Cole o token de acesso do Supabase abaixo. Os caracteres ficarao ocultos."
$secureToken = Read-Host "Token" -AsSecureString

$tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
try {
    $env:SUPABASE_ACCESS_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPointer)
    & (Join-Path $PSScriptRoot "deploy_functions_safe.ps1") -FunctionName "billing-api"
}
finally {
    Remove-Item Env:\SUPABASE_ACCESS_TOKEN -ErrorAction SilentlyContinue
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPointer)
    $secureToken.Dispose()
    Write-Host "Token removido da memoria deste processo." -ForegroundColor Green
}
