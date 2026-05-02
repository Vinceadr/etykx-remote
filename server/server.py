import os, io, time, subprocess, json, threading
from flask import Flask, Response, request, jsonify, render_template_string
from dotenv import load_dotenv
import mss
from PIL import Image
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyboardController

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')
AI_MODEL     = os.getenv('AI_MODEL', 'gpt-4o-mini')
PORT         = int(os.getenv('PORT', 5000))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'remotecontrol-secret'

mouse_ctrl    = MouseController()
keyboard_ctrl = KeyboardController()

with mss.mss() as sct:
    monitor  = sct.monitors[1]
    SCREEN_W = monitor['width']
    SCREEN_H = monitor['height']

_web_history = []

AI_SYSTEM = f"Tu es Interception, assistant IA expert en informatique connecte au PC ({SCREEN_W}x{SCREEN_H}). Reponds en markdown, en francais."

_frame_cache = b''
_frame_lock  = __import__('threading').Lock()

def _capture_loop():
    global _frame_cache
    with mss.mss() as s:
        mon = s.monitors[1]
        while True:
            try:
                shot = s.grab(mon)
                img  = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                if img.width > 960:
                    r = 960 / img.width
                    img = img.resize((960, int(img.height * r)), Image.BILINEAR)
                b = io.BytesIO()
                img.save(b, format="JPEG", quality=40)
                with _frame_lock:
                    _frame_cache = b.getvalue()
            except Exception:
                pass
            time.sleep(0.08)

__import__('threading').Thread(target=_capture_loop, daemon=True).start()

@app.route("/screenshot")
def screenshot():
    with _frame_lock:
        data = _frame_cache
    if not data:
        time.sleep(0.15)
        with _frame_lock:
            data = _frame_cache
    return Response(data, mimetype="image/jpeg", headers={"Cache-Control":"no-store"})

MEDIA_KEYS = {
    "play_pause": Key.media_play_pause, "next": Key.media_next,
    "prev": Key.media_previous, "mute": Key.media_volume_mute,
    "vol_up": Key.media_volume_up, "vol_down": Key.media_volume_down,
}

@app.route("/media/<action>")
def media(action):
    k = MEDIA_KEYS.get(action)
    if k: keyboard_ctrl.press(k); keyboard_ctrl.release(k)
    return ("", 204)

SPECIAL_KEYS = {
    "Enter":Key.enter,"Backspace":Key.backspace,"Tab":Key.tab,"Escape":Key.esc,
    "Delete":Key.delete,"Home":Key.home,"End":Key.end,"PageUp":Key.page_up,
    "PageDown":Key.page_down,"ArrowUp":Key.up,"ArrowDown":Key.down,
    "ArrowLeft":Key.left,"ArrowRight":Key.right," ":Key.space,
    "F1":Key.f1,"F2":Key.f2,"F3":Key.f3,"F4":Key.f4,"F5":Key.f5,"F6":Key.f6,
    "F7":Key.f7,"F8":Key.f8,"F9":Key.f9,"F10":Key.f10,"F11":Key.f11,"F12":Key.f12,
}

@app.route("/ctrl/move", methods=["POST"])
def ctrl_move():
    d = request.json or {}
    mouse_ctrl.position = (int(d["x"]*SCREEN_W), int(d["y"]*SCREEN_H))
    return ("", 204)

@app.route("/ctrl/click", methods=["POST"])
def ctrl_click():
    d = request.json or {}
    x, y = int(d["x"]*SCREEN_W), int(d["y"]*SCREEN_H)
    btn  = Button.right if d.get("right") else Button.left
    mouse_ctrl.position = (x, y)
    mouse_ctrl.click(btn, 2 if d.get("double") else 1)
    return ("", 204)

@app.route("/ctrl/drag", methods=["POST"])
def ctrl_drag():
    d = request.json or {}
    x, y = int(d["x"]*SCREEN_W), int(d["y"]*SCREEN_H)
    if d.get("start"):
        mouse_ctrl.position = (x, y); mouse_ctrl.press(Button.left)
    elif d.get("end"):
        mouse_ctrl.release(Button.left)
    else:
        mouse_ctrl.position = (x, y)
    return ("", 204)

@app.route("/ctrl/scroll", methods=["POST"])
def ctrl_scroll():
    d = request.json or {}
    mouse_ctrl.scroll(0, d.get("dy", -3))
    return ("", 204)

@app.route("/ctrl/key", methods=["POST"])
def ctrl_key():
    d = request.json or {}
    combo = d.get("combo", "")
    key   = d.get("key", "")
    if combo:
        parts = combo.split("+")
        mods  = []
        for p in parts[:-1]:
            p = p.strip().lower()
            if p=="ctrl": mods.append(Key.ctrl)
            elif p=="alt": mods.append(Key.alt)
            elif p=="shift": mods.append(Key.shift)
            elif p in("win","cmd"): mods.append(Key.cmd)
        final = parts[-1].strip()
        for m in mods: keyboard_ctrl.press(m)
        k = SPECIAL_KEYS.get(final, final)
        keyboard_ctrl.press(k); keyboard_ctrl.release(k)
        for m in reversed(mods): keyboard_ctrl.release(m)
        return ("", 204)
    k = SPECIAL_KEYS.get(key, key if len(key)==1 else None)
    if k: keyboard_ctrl.press(k); keyboard_ctrl.release(k)
    return ("", 204)

@app.route("/ctrl/type", methods=["POST"])
def ctrl_type():
    d = request.json or {}
    keyboard_ctrl.type(d.get("text", ""))
    return ("", 204)

@app.route("/ai", methods=["POST"])
def ai_chat():
    if not GITHUB_TOKEN:
        return jsonify({"reply": "GITHUB_TOKEN non configure"}), 500
    try:
        from openai import OpenAI
        msg = (request.json or {}).get("message", "").strip()
        if not msg: return jsonify({"reply": ""}), 400
        _web_history.append({"role":"user","content":msg})
        if len(_web_history) > 30: del _web_history[:-30]
        client = OpenAI(base_url="https://models.inference.ai.azure.com", api_key=GITHUB_TOKEN)
        resp = client.chat.completions.create(
            model=AI_MODEL,
            messages=[{"role":"system","content":AI_SYSTEM}] + _web_history,
            temperature=0.4, max_tokens=2000,
        )
        reply = resp.choices[0].message.content
        _web_history.append({"role":"assistant","content":reply})
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"reply": f"Erreur IA : {e}"}), 500

@app.route("/ai/clear", methods=["POST"])
def ai_clear():
    _web_history.clear()
    return jsonify({"ok": True})

_UI_PATH = __file__.replace("server.py","ui.html")


@app.route("/apk")
def download_apk():
    apk = os.path.join(os.path.dirname(__file__), "interception.apk")
    if not os.path.exists(apk):
        return ("APK non trouve", 404)
    return Response(
        open(apk, "rb").read(),
        mimetype="application/vnd.android.package-archive",
        headers={"Content-Disposition": "attachment; filename=interception.apk"}
    )
@app.route("/")
def index():
    return open(_UI_PATH, encoding="utf-8").read()


def _get_lan_ip():
    """Return the real LAN (Wi-Fi/Ethernet) IP, ignoring WSL/VPN/loopback."""
    import socket as _sock
    candidates = []
    try:
        for iface in _sock.getaddrinfo(_sock.gethostname(), None):
            ip = iface[4][0]
            if ip.startswith(("192.168.", "10.", "172.1", "172.2", "172.3")) \
               and not ip.startswith("172.25.") and ip != "127.0.0.1":
                candidates.append(ip)
    except Exception:
        pass
    # Prefer 192.168.x.x (typical home Wi-Fi)
    for ip in candidates:
        if ip.startswith("192.168."):
            return ip
    return candidates[0] if candidates else "127.0.0.1"

def _udp_broadcast():
    """Broadcast server presence on LAN so the Android app can auto-discover the IP."""
    import socket as _sock
    while True:
        try:
            lan_ip = _get_lan_ip()
            # Derive subnet broadcast (e.g. 192.168.1.255)
            parts = lan_ip.split(".")
            bcast = ".".join(parts[:3]) + ".255"
            s = _sock.socket(_sock.AF_INET, _sock.SOCK_DGRAM)
            s.setsockopt(_sock.SOL_SOCKET, _sock.SO_BROADCAST, 1)
            s.setsockopt(_sock.SOL_SOCKET, _sock.SO_REUSEADDR, 1)
            s.bind((lan_ip, 0))
            payload = json.dumps({"service": "interception", "port": PORT}).encode()
            s.sendto(payload, (bcast, 5001))
            s.close()
        except Exception:
            pass
        time.sleep(4)

threading.Thread(target=_udp_broadcast, daemon=True).start()

if __name__ == "__main__":
    import socket as sock
    local_ip = sock.gethostbyname(sock.gethostname())
    print(f"Interception Remote - http://{local_ip}:{PORT}")
    app.run(host="0.0.0.0", port=PORT, threaded=True, debug=False)
