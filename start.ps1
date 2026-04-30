# ────────────────────────────────────────────────────────────────────────
#  RemoteControl PC — Script de démarrage
# ────────────────────────────────────────────────────────────────────────
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ServerDir = Join-Path $ScriptDir "server"

Write-Host ""
Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║       RemoteControl PC — Démarrage       ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── Vérification de Python ──────────────────────────────────────────────
try {
    $pyVersion = python --version 2>&1
    Write-Host "✅ Python : $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python non trouvé. Installe Python 3.10+ depuis https://python.org" -ForegroundColor Red
    Read-Host "Appuie sur Entrée pour quitter"
    exit 1
}

# ── Vérification du fichier .env ────────────────────────────────────────
$envFile = Join-Path $ServerDir ".env"
if (-not (Test-Path $envFile)) {
    Write-Host ""
    Write-Host "⚠️  Fichier .env manquant !" -ForegroundColor Yellow
    Write-Host "   Copie '$ServerDir\.env.example' en '$envFile'" -ForegroundColor Yellow
    Write-Host "   et remplis les tokens." -ForegroundColor Yellow
    Write-Host ""
    $choice = Read-Host "Veux-tu le créer maintenant depuis l'exemple ? (o/n)"
    if ($choice -eq "o") {
        Copy-Item "$ServerDir\.env.example" $envFile
        Write-Host "✅ .env créé. Ouvre-le et remplis tes tokens :" -ForegroundColor Green
        Write-Host "   $envFile" -ForegroundColor White
        Start-Process notepad.exe $envFile
        Read-Host "Appuie sur Entrée une fois le .env rempli pour continuer"
    } else {
        Write-Host "❌ .env requis pour continuer." -ForegroundColor Red
        exit 1
    }
}

# ── Installation des dépendances ────────────────────────────────────────
$reqFile = Join-Path $ServerDir "requirements.txt"
Write-Host ""
Write-Host "📦 Installation des dépendances Python…" -ForegroundColor Cyan
pip install -r $reqFile --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Erreur lors de l'installation. Lance manuellement :" -ForegroundColor Red
    Write-Host "   pip install -r $reqFile" -ForegroundColor White
    exit 1
}
Write-Host "✅ Dépendances installées" -ForegroundColor Green

# ── Démarrage du serveur web ────────────────────────────────────────────
Write-Host ""
Write-Host "🌐 Démarrage du serveur web (interface téléphone)…" -ForegroundColor Cyan
$serverJob = Start-Process -FilePath "python" `
    -ArgumentList (Join-Path $ServerDir "server.py") `
    -WorkingDirectory $ServerDir `
    -PassThru `
    -NoNewWindow

Start-Sleep -Seconds 3

# ── Démarrage du bot Telegram ───────────────────────────────────────────
Write-Host "🤖 Démarrage du bot Telegram…" -ForegroundColor Cyan
$botJob = Start-Process -FilePath "python" `
    -ArgumentList (Join-Path $ServerDir "telegram_bot.py") `
    -WorkingDirectory $ServerDir `
    -PassThru `
    -NoNewWindow

Write-Host ""
Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║              ✅ Tout est lancé !          ║" -ForegroundColor Green
Write-Host "╠══════════════════════════════════════════╣" -ForegroundColor Green
Write-Host "║  • Serveur web  : http://localhost:5000   ║" -ForegroundColor Green
Write-Host "║  • Bot Telegram : actif                   ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "Appuie sur Ctrl+C pour tout arrêter." -ForegroundColor Yellow
Write-Host ""

# Garde le script actif
try {
    Wait-Process -Id $serverJob.Id
} catch {
    # Nettoyage
    if (-not $serverJob.HasExited) { Stop-Process -Id $serverJob.Id -Force }
    if (-not $botJob.HasExited)    { Stop-Process -Id $botJob.Id -Force }
    Write-Host "Arrêté." -ForegroundColor Yellow
}
