# RemoteControl PC -- Script de demarrage
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ServerDir = Join-Path $ScriptDir "server"
$PORT = 5000

Write-Host "" 
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "       RemoteControl PC -- Demarrage        " -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Tuer les instances precedentes (evite 409 Conflict)
Write-Host "[*] Verification des instances existantes..." -ForegroundColor Yellow
$oldProcs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "server\.py|telegram_bot\.py" }
foreach ($p in $oldProcs) {
    Write-Host "  [!] Instance trouvee (PID $($p.ProcessId)) -- fermeture..." -ForegroundColor Yellow
    try { (Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue).Kill() } catch {}
}
if ($oldProcs.Count -gt 0) { Start-Sleep -Milliseconds 600 }

# Obtenir l IP LAN reelle (Wi-Fi en priorite, exclure WSL/vEthernet)
$LAN_IP = $null
$LAN_IP = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.InterfaceAlias -match "Wi-Fi" -and $_.IPAddress -notmatch "^169\." -and $_.IPAddress -ne "127.0.0.1" } |
    Select-Object -First 1).IPAddress
if (-not $LAN_IP) {
    $LAN_IP = (Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object { $_.InterfaceAlias -notmatch "vEthernet|Loopback|Tunnel|Teredo|WSL|Virtual" -and $_.IPAddress -notmatch "^169\.|^172\." -and $_.IPAddress -ne "127.0.0.1" } |
        Select-Object -First 1).IPAddress
}
if (-not $LAN_IP) { $LAN_IP = "127.0.0.1" }

# Verification de Python
try {
    $pyVersion = python --version 2>&1
    Write-Host "[OK] Python : $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERR] Python non trouve." -ForegroundColor Red; exit 1
}

# Verification du fichier .env
$envFile = Join-Path $ServerDir ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "[!] Fichier .env manquant !" -ForegroundColor Yellow
    $choice = Read-Host "Creer depuis .env.example ? (o/n)"
    if ($choice -eq "o") {
        Copy-Item "$ServerDir\.env.example" $envFile
        Start-Process notepad.exe $envFile
        Read-Host "Remplis le .env puis appuie sur Entree"
    } else { Write-Host "[ERR] .env requis." -ForegroundColor Red; exit 1 }
}

# Installation des dependances
$reqFile = Join-Path $ServerDir "requirements.txt"
Write-Host "[*] Installation des dependances Python..." -ForegroundColor Cyan
pip install -r $reqFile --quiet
if ($LASTEXITCODE -ne 0) { Write-Host "[ERR] Echec pip install." -ForegroundColor Red; exit 1 }
Write-Host "[OK] Dependances installees" -ForegroundColor Green

# Demarrage du serveur web
Write-Host "[*] Demarrage du serveur web..." -ForegroundColor Cyan
$serverJob = Start-Process -FilePath "python" -ArgumentList (Join-Path $ServerDir "server.py") -WorkingDirectory $ServerDir -PassThru -NoNewWindow
Start-Sleep -Seconds 3

# Demarrage du bot Telegram
Write-Host "[*] Demarrage du bot Telegram..." -ForegroundColor Cyan
$botJob = Start-Process -FilePath "python" -ArgumentList (Join-Path $ServerDir "telegram_bot.py") -WorkingDirectory $ServerDir -PassThru -NoNewWindow
Start-Sleep -Seconds 2

$serverOK = -not $serverJob.HasExited
$botOK    = -not $botJob.HasExited

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "           TOUT EST LANCE !" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Ouvre sur ton telephone :" -ForegroundColor White
Write-Host ""
Write-Host "    http://$($LAN_IP):$PORT" -ForegroundColor Yellow
Write-Host ""
Write-Host "  App Android --> IP a entrer : $LAN_IP" -ForegroundColor Cyan
if ($serverOK) { Write-Host "  Serveur web  : [OK] actif" -ForegroundColor Green } else { Write-Host "  Serveur web  : [ERR] PLANTE" -ForegroundColor Red }
if ($botOK)    { Write-Host "  Bot Telegram : [OK] actif" -ForegroundColor Green } else { Write-Host "  Bot Telegram : [ERR] PLANTE" -ForegroundColor Red }
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "[!] Telephone sur le MEME Wi-Fi - Ctrl+C pour arreter" -ForegroundColor Yellow
Write-Host ""

# Boucle de supervision avec auto-redemarrage du bot
try {
    while ($true) {
        Start-Sleep -Seconds 5
        if ($botJob.HasExited -and (-not $serverJob.HasExited)) {
            Write-Host "[!] Bot arrete -- redemarrage..." -ForegroundColor Yellow
            $botJob = Start-Process -FilePath "python" -ArgumentList (Join-Path $ServerDir "telegram_bot.py") -WorkingDirectory $ServerDir -PassThru -NoNewWindow
            Write-Host "[OK] Bot redemarre (PID $($botJob.Id))" -ForegroundColor Green
        }
        if ($serverJob.HasExited) { Write-Host "[ERR] Serveur arrete." -ForegroundColor Red; break }
    }
} finally {
    Write-Host "[*] Arret..." -ForegroundColor Yellow
    try { if (-not $serverJob.HasExited) { $serverJob.Kill() } } catch {}
    try { if (-not $botJob.HasExited)    { $botJob.Kill()    } } catch {}
    Write-Host "[OK] Tout est arrete." -ForegroundColor Green
}
