$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$form = New-Object System.Windows.Forms.Form
$form.Text = "Publicar correcao no Supabase"
$form.StartPosition = "CenterScreen"
$form.Size = New-Object System.Drawing.Size(560, 220)
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.TopMost = $true

$label = New-Object System.Windows.Forms.Label
$label.Location = New-Object System.Drawing.Point(24, 22)
$label.Size = New-Object System.Drawing.Size(500, 44)
$label.Text = "Cole o Personal Access Token do Supabase. O valor ficara oculto e sera removido da memoria ao terminar."
$form.Controls.Add($label)

$tokenBox = New-Object System.Windows.Forms.TextBox
$tokenBox.Location = New-Object System.Drawing.Point(24, 76)
$tokenBox.Size = New-Object System.Drawing.Size(500, 28)
$tokenBox.UseSystemPasswordChar = $true
$form.Controls.Add($tokenBox)

$publishButton = New-Object System.Windows.Forms.Button
$publishButton.Location = New-Object System.Drawing.Point(348, 122)
$publishButton.Size = New-Object System.Drawing.Size(176, 38)
$publishButton.Text = "Publicar billing-api"
$publishButton.DialogResult = [System.Windows.Forms.DialogResult]::OK
$form.AcceptButton = $publishButton
$form.Controls.Add($publishButton)

$cancelButton = New-Object System.Windows.Forms.Button
$cancelButton.Location = New-Object System.Drawing.Point(238, 122)
$cancelButton.Size = New-Object System.Drawing.Size(100, 38)
$cancelButton.Text = "Cancelar"
$cancelButton.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
$form.CancelButton = $cancelButton
$form.Controls.Add($cancelButton)

$form.Add_Shown({ $tokenBox.Focus() })
$result = $form.ShowDialog()
if ($result -ne [System.Windows.Forms.DialogResult]::OK) {
    $tokenBox.Clear()
    $form.Dispose()
    exit 2
}

$token = $tokenBox.Text
$tokenBox.Clear()
$form.Dispose()
if ([string]::IsNullOrWhiteSpace($token) -or -not $token.StartsWith("sbp_")) {
    [System.Windows.Forms.MessageBox]::Show(
        "O token informado nao possui o formato esperado.",
        "Token invalido",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Warning
    ) | Out-Null
    exit 3
}

try {
    $env:SUPABASE_ACCESS_TOKEN = $token
    $token = $null
    & (Join-Path $PSScriptRoot "deploy_functions_safe.ps1") -FunctionName "billing-api"
    $deployExitCode = $LASTEXITCODE
}
finally {
    $token = $null
    Remove-Item Env:\SUPABASE_ACCESS_TOKEN -ErrorAction SilentlyContinue
    [GC]::Collect()
}

if ($deployExitCode -eq 0) {
    [System.Windows.Forms.MessageBox]::Show(
        "A funcao billing-api foi publicada com sucesso.",
        "Publicacao concluida",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Information
    ) | Out-Null
} else {
    [System.Windows.Forms.MessageBox]::Show(
        "A publicacao falhou. O relatorio sanitizado foi salvo para diagnostico.",
        "Falha na publicacao",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
}
exit $deployExitCode
