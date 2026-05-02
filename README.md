# 📱 Interception — Contrôle ton PC depuis ton téléphone

Contrôle ton PC Windows à distance depuis ton téléphone Android, avec streaming d'écran, souris/clavier tactile, bot **Telegram** et assistant **IA** intégré.

---

## ⬇️ Télécharger l'app Android

### Étape 1 — Autoriser les sources inconnues (une seule fois)
> **Paramètres** → **Sécurité** → **Installer des applis inconnues** → autorise ton navigateur

### Étape 2 — Télécharger l'APK
Ouvre ce lien **directement sur ton téléphone** :

👉 **https://github.com/Vinceadr/etykx-remote/releases/latest**

Appuie sur **`app-debug.apk`** pour télécharger.

### Étape 3 — Installer & Configurer
Lance l'app → appuie sur **🔍 Détecter le PC automatiquement**

> L'app trouve ton PC toute seule, peu importe l'IP. PC et téléphone doivent être sur le **même Wi-Fi**.

> Si la détection échoue, lance `start.ps1` sur le PC d'abord, puis réessaie.

---

## 🖥️ Démarrer le serveur PC

```powershell
.\start.ps1
```

L'IP à utiliser s'affiche dans le terminal. Le serveur **diffuse son IP automatiquement** sur le réseau local — l'app Android la détecte sans configuration manuelle.

---

## 🌐 Interface Web (alternative sans APK)

Lance `start.ps1` → l'IP s'affiche → ouvre dans le navigateur du téléphone :

```
http://<IP-affichée>:5000
```

- **Touch** → déplace la souris
- **Tap** → clic gauche
- **Double tap** → double clic
- **Appui long (650ms)** → clic droit
- **Appui très long (950ms)** → drag & drop
- **2 doigts** → scroll
- **KB** → ouvre le clavier virtuel
- **AI** → chat avec l'assistant IA

---

## 💬 Bot Telegram — @interception_bot

| Ce que tu écris | Ce que ça fait |
|---|---|
| `ouvre Chrome` | Lance Google Chrome |
| `prends un screenshot` | Capture + envoie l'écran |
| `mets en pause la musique` | ⏯ Media play/pause |
| `tape Bonjour dans la fenêtre` | ⌨️ Tape le texte |
| `appuie sur Ctrl+Z` | Raccourci clavier |
| `monte le volume` | 🔊 Volume + |
| `ferme la fenêtre active` | Alt+F4 |
| `/screenshot` | Screenshot immédiat |
| `/clear` | Efface l'historique IA |

---

## 🔄 Démarrage automatique

Le serveur et le bot Telegram **se lancent automatiquement** à chaque démarrage de Windows.

---

## 📁 Structure du projet

```
RemoteControl/
├── server/
│   ├── server.py          # Serveur web Flask (streaming + contrôle + broadcast UDP)
│   ├── telegram_bot.py    # Bot Telegram + IA GitHub Models
│   ├── requirements.txt
│   ├── .env               # Tes secrets (ne pas partager !)
│   └── .env.example       # Modèle de configuration
├── android/               # Projet Android (build auto via GitHub Actions)
└── .github/workflows/     # CI/CD → APK auto-buildé à chaque push
```
