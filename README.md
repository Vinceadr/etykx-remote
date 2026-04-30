# 📱 Interception — Contrôle ton PC depuis ton téléphone

Contrôle ton PC Windows à distance depuis ton téléphone Android, avec streaming d'écran, souris/clavier tactile, bot **Telegram** et assistant **IA** intégré.

---

## ⬇️ Télécharger l'app Android

### Étape 1 — Autoriser les sources inconnues (une seule fois)
> **Paramètres** → **Sécurité** → **Installer des applis inconnues** → autorise ton navigateur Chrome/Firefox

### Étape 2 — Télécharger l'APK
Ouvre ce lien **directement sur ton téléphone** :

👉 **https://github.com/Vinceadr/etykx-remote/releases/latest**

Appuie sur **`app-debug.apk`** pour télécharger.

### Étape 3 — Installer
Ouvre le fichier téléchargé et appuie sur **Installer**.

### Étape 4 — Configurer
Lance l'app → entre :
- **IP de ton PC** : `10.0.108.63`
- **Port** : `5000`

> 💡 Ton PC et ton téléphone doivent être sur le **même Wi-Fi**.

---

## 🌐 Interface Web (alternative sans APK)

Ouvre directement dans le navigateur de ton téléphone :

```
http://10.0.108.63:5000
```

- **Touch** → déplace la souris
- **Tap** → clic gauche
- **Double tap** → double clic
- **Appui long** → clic droit
- **2 doigts** → scroll
- **⌨️** → ouvre le clavier virtuel
- **🤖** → chat avec l'assistant IA

---

## 💬 Bot Telegram — @interception_bot

Parle naturellement à ton bot depuis n'importe où :

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
| `explique-moi Python` | 🤖 Assistant IA (n'importe quelle question) |

> ⚠️ Les actions sensibles demandent une **confirmation** via boutons Telegram.

---

## 🔄 Démarrage automatique

Le serveur et le bot Telegram **se lancent automatiquement** à chaque démarrage de Windows.
Tu n'as rien à faire — l'app est toujours disponible dès que le PC est allumé et connecté au Wi-Fi.

---

## 📁 Structure du projet

```
RemoteControl/
├── server/
│   ├── server.py          # Serveur web Flask (streaming + contrôle)
│   ├── telegram_bot.py    # Bot Telegram + IA GitHub Models
│   ├── requirements.txt
│   ├── .env               # Tes secrets (ne pas partager !)
│   └── .env.example       # Modèle de configuration
├── android/               # Projet Android (build auto via GitHub Actions)
└── .github/workflows/     # CI/CD → APK auto-buildé à chaque push
```
