# Copies the secrets from the local .env files to the Fly.io app, without printing them.
# Run from anywhere: powershell -ExecutionPolicy Bypass -File deploy\fly-secrets.ps1
Set-Location (Join-Path $PSScriptRoot "..")
$names = 'DATABASE_URL', 'APP_SECRET', 'ANTHROPIC_API_KEY', 'OPENAI_API_KEY'
$pairs = @(Get-Content backend\.env, chatbot\.env | ForEach-Object { $_.Trim([char]0xFEFF).Trim() } |
    Where-Object { $_ -match '^([A-Z_]+)=(.+)$' -and $names -contains $Matches[1] })
$found = $pairs | ForEach-Object { ($_ -split '=', 2)[0] }
$missing = $names | Where-Object { $found -notcontains $_ }
if ($missing) { Write-Host "Not found in the .env files: $($missing -join ', ')" -ForegroundColor Yellow }
$pairs += 'CORS_ORIGINS=http://localhost:3000'
fly secrets set --stage @pairs
if ($LASTEXITCODE -eq 0) { Write-Host "Done: $($pairs.Count) secrets saved on Fly.io." -ForegroundColor Green }
