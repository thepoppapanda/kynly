$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $repoRoot '.env'
if (Test-Path $envPath) {
    Write-Host '.env already exists; keeping existing credentials.'
    return
}
function New-RandomHex {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return ([BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
}
$lines = @(
    '# Local secrets. Never commit or share this file.'
    "POSTGRES_PASSWORD=$(New-RandomHex)"
    "N8N_ENCRYPTION_KEY=$(New-RandomHex)"
)
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($envPath, $lines, $utf8)
Write-Host 'Created local .env with random credentials. Back it up securely.'
