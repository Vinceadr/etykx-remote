# 🖥️ RemoteControl PC

Contrôle ton PC depuis ton téléphone via **Wi-Fi** + chat **Telegram**.

---

## 🚀 Démarrage rapide

### 1. Configurer les tokens

```bash
cd server
copy .env.example .env
# Ouvre .env et remplis les 3 valeurs
```

### 2. Créer ton bot Telegram

1. Ouvre Telegram, cherche **@BotFather**
2. Envoie `/newbot` → donne un nom et un username
3. Copie le **token** dans `.env` → `TELEGRAM_TOKEN`

### 3. Obtenir ton GitHub Token (IA)

1. Va sur https://github.com/settings/tokens
2. **Generate new token (classic)** — pas besoin de scope particulier
3. Copie dans `.env` → `GITHUB_TOKEN`

### 4. Trouver ton Telegram User ID

1. Lance le serveur : `.\start.ps1`
2. Envoie `/start` à ton bot depuis Telegram
3. Ton ID s'affiche dans la console → copie dans `.env` → `ALLOWED_USER_ID`
4. Relance : `.\start.ps1`

### 5. Lancer tout

```powershell
.\start.ps1
```

---

## 📱 App Android (APK)

### Prérequis
- **Android Studio** (https://developer.android.com/studio)

### Build
```bash
cd android
# Windows:
gradlew assembleDebug
# L'APK est dans : app/build/outputs/apk/debug/app-debug.apk
```

### Installer sur le téléphone
```bash
adb install app/build/outputs/apk/debug/app-debug.apk
```
Ou transfère le fichier APK sur ton téléphone et installe-le.

---

## 💬 Commandes Telegram

Parle naturellement à ton bot :

| Ce que tu écris | Ce que ça fait |
|---|---|
| `ouvre Chrome` | Lance Google Chrome |
| `prends un screenshot` | Capture + envoie l'écran |
| `mets en pause la musique` | ⏯ Media play/pause |
| `tape Bonjour dans la fenêtre` | ⌨️ Type le texte |
| `appuie sur Ctrl+Z` | Raccourci clavier |
| `monte le volume` | 🔊 Volume + |
| `ferme la fenêtre active` | Alt+F4 |
| `/screenshot` | Screenshot immédiat |
| `/clear` | Efface l'historique de conversation |

> ⚠️ Les actions sensibles (lancer des apps, commandes shell) demandent **confirmation** via boutons Telegram.

---

## 🌐 Interface Web (téléphone)

Ouvre `http://[IP_DU_PC]:5000` dans le navigateur de ton téléphone.

- **Touch** → déplace la souris
- **Tap** → clic gauche
- **Double tap** → double clic
- **Appui long** → clic droit
- **2 doigts** → scroll
- **⌨️** → ouvre le clavier virtuel

---

## 📁 Structure

```
RemoteControl/
├── start.ps1              # Lance tout
├── server/
│   ├── server.py          # Serveur web Flask (streaming + contrôle)
│   ├── telegram_bot.py    # Bot Telegram + IA GitHub Models
│   ├── requirements.txt
│   ├── .env               # Tes secrets (ne pas partager !)
│   └── .env.example       # Modèle de configuration
└── android/               # Projet Android Studio
```
