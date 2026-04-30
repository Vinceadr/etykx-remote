import os, io, time, subprocess, json
from flask import Flask, Response, request, jsonify, render_template_string
from flask_socketio import SocketIO, emit
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
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet')

mouse_ctrl    = MouseController()
keyboard_ctrl = KeyboardController()

with mss.mss() as sct:
    monitor  = sct.monitors[1]
    SCREEN_W = monitor['width']
    SCREEN_H = monitor['height']

# ── Conversation history for web chat ──────────────────────────────────
_web_history = []

AI_SYSTEM = f"""Tu es ETYKX, un assistant IA personnel expert en informatique et cybersécurité,
connecté au PC Windows de ton propriétaire (résolution {SCREEN_W}x{SCREEN_H}).
Tu peux répondre à toutes les questions : code, scripts, cybersécurité, architecture, etc.
Réponds en markdown. Sois expert, précis et concis. Parle en français sauf si on te parle autrement."""

# ── MJPEG Stream ───────────────────────────────────────────────────────
def capture_frames(quality=50, fps=20):
    delay = 1.0 / fps
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        while True:
            start = time.time()
            shot  = sct.grab(monitor)
            img   = Image.frombytes('RGB', shot.size, shot.bgra, 'raw', 'BGRX')
            buf   = io.BytesIO()
            img.save(buf, format='JPEG', quality=quality)
            yield buf.getvalue()
            rem = delay - (time.time() - start)
            if rem > 0: time.sleep(rem)

def mjpeg_generator():
    for frame in capture_frames():
        yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'

@app.route('/stream')
def stream():
    return Response(mjpeg_generator(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/screenshot')
def screenshot():
    with mss.mss() as sct:
        shot = sct.grab(sct.monitors[1])
        img  = Image.frombytes('RGB', shot.size, shot.bgra, 'raw', 'BGRX')
        buf  = io.BytesIO()
        img.save(buf, format='JPEG', quality=60)
        return Response(buf.getvalue(), mimetype='image/jpeg')

@app.route('/screen-info')
def screen_info():
    return jsonify({'width': SCREEN_W, 'height': SCREEN_H})

# ── Media ───────────────────────────────────────────────────────────────
MEDIA_KEYS = {
    'play_pause': Key.media_play_pause, 'next': Key.media_next,
    'prev': Key.media_previous, 'mute': Key.media_volume_mute,
    'vol_up': Key.media_volume_up, 'vol_down': Key.media_volume_down,
}

@app.route('/media/<action>')
def media(action):
    key = MEDIA_KEYS.get(action)
    if key:
        keyboard_ctrl.press(key); keyboard_ctrl.release(key)
        return jsonify({'ok': True})
    return jsonify({'ok': False}), 400

# ── Launch ──────────────────────────────────────────────────────────────
@app.route('/launch', methods=['POST'])
def launch():
    cmd = (request.json or {}).get('cmd', '')
    if not cmd: return jsonify({'ok': False}), 400
    try:
        subprocess.Popen(cmd, shell=True)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

# ── System info ─────────────────────────────────────────────────────────
@app.route('/system')
def system_info():
    import psutil
    bat = psutil.sensors_battery()
    return jsonify({
        'cpu': psutil.cpu_percent(interval=0.5),
        'ram': psutil.virtual_memory().percent,
        'battery': bat._asdict() if bat else None,
    })

# ── AI Chat endpoint ────────────────────────────────────────────────────
@app.route('/ai', methods=['POST'])
def ai_chat():
    if not GITHUB_TOKEN:
        return jsonify({'reply': '❌ GITHUB_TOKEN non configuré dans .env'}), 500
    try:
        from openai import OpenAI
        message = (request.json or {}).get('message', '').strip()
        if not message:
            return jsonify({'reply': ''}), 400

        _web_history.append({'role': 'user', 'content': message})
        if len(_web_history) > 30:
            del _web_history[:-30]

        client = OpenAI(
            base_url='https://models.inference.ai.azure.com',
            api_key=GITHUB_TOKEN,
        )
        resp = client.chat.completions.create(
            model=AI_MODEL,
            messages=[{'role': 'system', 'content': AI_SYSTEM}] + _web_history,
            temperature=0.4,
            max_tokens=2000,
        )
        reply = resp.choices[0].message.content
        _web_history.append({'role': 'assistant', 'content': reply})
        return jsonify({'reply': reply})
    except Exception as e:
        return jsonify({'reply': f'❌ Erreur IA : {e}'}), 500

@app.route('/ai/clear', methods=['POST'])
def ai_clear():
    _web_history.clear()
    return jsonify({'ok': True})

# ── WebSocket ───────────────────────────────────────────────────────────
@socketio.on('mouse_move')
def on_mouse_move(data):
    mouse_ctrl.position = (int(data['x']*SCREEN_W), int(data['y']*SCREEN_H))

@socketio.on('mouse_click')
def on_mouse_click(data):
    x, y = int(data['x']*SCREEN_W), int(data['y']*SCREEN_H)
    btn  = Button.right if data.get('right') else Button.left
    mouse_ctrl.position = (x, y)
    mouse_ctrl.click(btn, 2 if data.get('double') else 1)

@socketio.on('mouse_scroll')
def on_mouse_scroll(data):
    mouse_ctrl.scroll(0, data.get('dy', -3))

@socketio.on('mouse_drag')
def on_mouse_drag(data):
    x, y = int(data['x']*SCREEN_W), int(data['y']*SCREEN_H)
    if data.get('start'):
        mouse_ctrl.position = (x, y); mouse_ctrl.press(Button.left)
    elif data.get('end'):
        mouse_ctrl.release(Button.left)
    else:
        mouse_ctrl.position = (x, y)

SPECIAL_KEYS = {
    'Enter':Key.enter,'Backspace':Key.backspace,'Tab':Key.tab,'Escape':Key.esc,
    'Delete':Key.delete,'Home':Key.home,'End':Key.end,'PageUp':Key.page_up,
    'PageDown':Key.page_down,'ArrowUp':Key.up,'ArrowDown':Key.down,
    'ArrowLeft':Key.left,'ArrowRight':Key.right,' ':Key.space,
    'F1':Key.f1,'F2':Key.f2,'F3':Key.f3,'F4':Key.f4,'F5':Key.f5,'F6':Key.f6,
    'F7':Key.f7,'F8':Key.f8,'F9':Key.f9,'F10':Key.f10,'F11':Key.f11,'F12':Key.f12,
}

@socketio.on('key_press')
def on_key_press(data):
    combo = data.get('combo','')
    key   = data.get('key','')
    if combo:
        parts = combo.split('+')
        mods  = []
        for p in parts[:-1]:
            p = p.strip().lower()
            if p=='ctrl': mods.append(Key.ctrl)
            elif p=='alt': mods.append(Key.alt)
            elif p=='shift': mods.append(Key.shift)
            elif p in('win','cmd'): mods.append(Key.cmd)
        final = parts[-1].strip()
        for m in mods: keyboard_ctrl.press(m)
        k = SPECIAL_KEYS.get(final, final)
        keyboard_ctrl.press(k); keyboard_ctrl.release(k)
        for m in reversed(mods): keyboard_ctrl.release(m)
        return
    k = SPECIAL_KEYS.get(key, key if len(key)==1 else None)
    if k:
        keyboard_ctrl.press(k); keyboard_ctrl.release(k)

@socketio.on('type_text')
def on_type_text(data):
    keyboard_ctrl.type(data.get('text',''))

# ── Web UI ──────────────────────────────────────────────────────────────
HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
<title>ETYKX Remote</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{background:#1a1a2e;color:#eee;font-family:sans-serif;overflow:hidden;height:100vh;display:flex;flex-direction:column}
#toolbar{display:flex;gap:5px;padding:6px 8px;background:#16213e;flex-wrap:wrap;align-items:center;z-index:10;flex-shrink:0}
.btn{padding:7px 10px;border:none;border-radius:8px;background:#0f3460;color:#fff;font-size:12px;cursor:pointer;touch-action:manipulation;user-select:none;flex-shrink:0}
.btn:active,.btn.active{background:#e94560}
#screen-wrap{flex:1;position:relative;overflow:hidden;touch-action:none}
#screen{width:100%;height:100%;object-fit:contain;display:block;pointer-events:none}
#keyboard-area{display:none;padding:8px;background:#16213e;flex-shrink:0}
#textinput{width:100%;padding:8px;background:#0f3460;border:1px solid #e94560;border-radius:8px;color:#fff;font-size:16px}
#overlay{position:absolute;top:0;left:0;width:100%;height:100%;z-index:5}
#cursor{position:absolute;width:12px;height:12px;border:2px solid #e94560;border-radius:50%;pointer-events:none;transform:translate(-50%,-50%);z-index:6;display:none}

/* ── AI Chat Panel ── */
#chat-fab{position:fixed;bottom:20px;right:20px;width:52px;height:52px;border-radius:50%;background:#e94560;border:none;color:#fff;font-size:22px;cursor:pointer;z-index:100;box-shadow:0 4px 16px rgba(233,69,96,.5);touch-action:manipulation}
#chat-panel{position:fixed;bottom:0;left:0;right:0;height:70vh;background:#16213e;border-radius:20px 20px 0 0;z-index:99;transform:translateY(100%);transition:transform .3s ease;display:flex;flex-direction:column}
#chat-panel.open{transform:translateY(0)}
#chat-header{display:flex;align-items:center;justify-content:space-between;padding:14px 16px;border-bottom:1px solid #0f3460;flex-shrink:0}
#chat-header h3{font-size:15px;color:#e94560}
#chat-close{background:none;border:none;color:#aaa;font-size:20px;cursor:pointer}
#chat-messages{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:10px}
.msg{max-width:90%;padding:10px 12px;border-radius:12px;font-size:13px;line-height:1.5;word-break:break-word}
.msg.user{background:#0f3460;align-self:flex-end;border-bottom-right-radius:4px}
.msg.bot{background:#1a1a2e;border:1px solid #0f3460;align-self:flex-start;border-bottom-left-radius:4px}
.msg.bot pre{background:#0a0a1a;padding:8px;border-radius:6px;overflow-x:auto;margin:6px 0;font-size:11px}
.msg.bot code{background:#0a0a1a;padding:2px 5px;border-radius:4px;font-size:11px}
.msg.typing span{display:inline-block;width:6px;height:6px;border-radius:50%;background:#e94560;margin:0 2px;animation:bounce .8s infinite}
.msg.typing span:nth-child(2){animation-delay:.15s}
.msg.typing span:nth-child(3){animation-delay:.3s}
@keyframes bounce{0%,80%,100%{transform:translateY(0)}40%{transform:translateY(-6px)}}
#chat-input-area{display:flex;gap:8px;padding:10px 12px;border-top:1px solid #0f3460;flex-shrink:0}
#chat-input{flex:1;background:#0f3460;border:1px solid #1a4080;border-radius:10px;color:#fff;padding:10px;font-size:14px;outline:none}
#chat-send{background:#e94560;border:none;color:#fff;border-radius:10px;padding:10px 14px;font-size:16px;cursor:pointer}
#chat-clear-btn{background:#0f3460;border:none;color:#aaa;border-radius:10px;padding:10px;font-size:14px;cursor:pointer}
</style>
</head>
<body>

<div id="toolbar">
  <button class="btn" onclick="toggleKB()">⌨️</button>
  <button class="btn" onclick="sendKey('Escape')">ESC</button>
  <button class="btn" onclick="sendCombo('ctrl+alt+Delete')">CAD</button>
  <button class="btn" onclick="sendCombo('ctrl+c')">Copy</button>
  <button class="btn" onclick="sendCombo('ctrl+v')">Paste</button>
  <button class="btn" onclick="sendCombo('ctrl+z')">Undo</button>
  <button class="btn" onclick="sendCombo('alt+F4')">✕</button>
  <button class="btn" onclick="sendMedia('play_pause')">⏯</button>
  <button class="btn" onclick="sendMedia('prev')">⏮</button>
  <button class="btn" onclick="sendMedia('next')">⏭</button>
  <button class="btn" onclick="sendMedia('vol_down')">🔉</button>
  <button class="btn" onclick="sendMedia('vol_up')">🔊</button>
  <button class="btn" onclick="sendMedia('mute')">🔇</button>
</div>

<div id="screen-wrap">
  <img id="screen" src="/stream" alt="screen">
  <div id="overlay"></div>
  <div id="cursor"></div>
</div>

<div id="keyboard-area">
  <input id="textinput" type="text" placeholder="Taper ici puis Entrée..." autocomplete="off">
</div>

<!-- AI Chat FAB -->
<button id="chat-fab" onclick="toggleChat()">🤖</button>

<!-- AI Chat Panel -->
<div id="chat-panel">
  <div id="chat-header">
    <h3>🤖 ETYKX — Assistant IA</h3>
    <div style="display:flex;gap:8px;align-items:center">
      <button id="chat-clear-btn" onclick="clearChat()" title="Effacer">🗑️</button>
      <button id="chat-close" onclick="toggleChat()">✕</button>
    </div>
  </div>
  <div id="chat-messages">
    <div class="msg bot">👋 Salut ! Je suis ETYKX, ton assistant IA.<br>Pose-moi n'importe quelle question en informatique, code, cybersécurité...</div>
  </div>
  <div id="chat-input-area">
    <input id="chat-input" type="text" placeholder="Demande-moi quelque chose..." autocomplete="off">
    <button id="chat-send" onclick="sendAI()">➤</button>
  </div>
</div>

<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<script>
const socket = io();
const overlay = document.getElementById('overlay');
const cursor  = document.getElementById('cursor');
let dragging = false, lastTouch = null, twoFinger = false, lastDist = 0;

function getRelPos(e) {
  const imgRect = document.getElementById('screen').getBoundingClientRect();
  const touch = e.touches ? e.touches[0] : e;
  return {
    x: Math.max(0, Math.min(1, (touch.clientX - imgRect.left) / imgRect.width)),
    y: Math.max(0, Math.min(1, (touch.clientY - imgRect.top)  / imgRect.height))
  };
}

overlay.addEventListener('touchstart', e => {
  e.preventDefault();
  if (e.touches.length === 2) {
    twoFinger = true;
    const dx = e.touches[1].clientX-e.touches[0].clientX;
    const dy = e.touches[1].clientY-e.touches[0].clientY;
    lastDist  = Math.sqrt(dx*dx+dy*dy);
    return;
  }
  twoFinger = false;
  const pos = getRelPos(e);
  lastTouch = pos;
  cursor.style.display = 'block';
  moveCursor(e);
  socket.emit('mouse_move', pos);
}, {passive:false});

overlay.addEventListener('touchmove', e => {
  e.preventDefault();
  if (e.touches.length===2) {
    const dx = e.touches[1].clientX-e.touches[0].clientX;
    const dy = e.touches[1].clientY-e.touches[0].clientY;
    const dist = Math.sqrt(dx*dx+dy*dy);
    const delta = lastDist - dist;
    if (Math.abs(delta)>5) { socket.emit('mouse_scroll',{dy:delta>0?-3:3}); lastDist=dist; }
    return;
  }
  const pos = getRelPos(e);
  moveCursor(e);
  if (dragging) socket.emit('mouse_drag', pos);
  else socket.emit('mouse_move', pos);
  lastTouch = pos;
}, {passive:false});

overlay.addEventListener('touchend', e => {
  e.preventDefault();
  cursor.style.display = 'none';
  if (dragging) { socket.emit('mouse_drag',{...lastTouch,end:true}); dragging=false; }
}, {passive:false});

let tapTimer=null, tapCount=0;
overlay.addEventListener('click', e => {
  const pos = getRelPos(e);
  tapCount++;
  if (tapCount===1) {
    tapTimer = setTimeout(()=>{ socket.emit('mouse_click',pos); tapCount=0; }, 250);
  } else {
    clearTimeout(tapTimer);
    socket.emit('mouse_click',{...pos,double:true});
    tapCount=0;
  }
});
overlay.addEventListener('contextmenu', e => {
  e.preventDefault();
  socket.emit('mouse_click',{...getRelPos(e),right:true});
});

let longPressTimer=null;
overlay.addEventListener('touchstart', e=>{
  if (e.touches.length!==1) return;
  const pos = getRelPos(e);
  longPressTimer = setTimeout(()=>{ socket.emit('mouse_click',{...pos,right:true}); navigator.vibrate&&navigator.vibrate(50); }, 600);
},{passive:true});
overlay.addEventListener('touchend',()=>clearTimeout(longPressTimer),{passive:true});
overlay.addEventListener('touchmove',()=>clearTimeout(longPressTimer),{passive:true});

function moveCursor(e) {
  const imgRect = document.getElementById('screen').getBoundingClientRect();
  const touch   = e.touches?e.touches[0]:e;
  cursor.style.left = (touch.clientX-imgRect.left)+'px';
  cursor.style.top  = (touch.clientY-imgRect.top)+'px';
}

function sendKey(k)   { socket.emit('key_press',{key:k}); }
function sendCombo(c) { socket.emit('key_press',{combo:c}); }
function sendMedia(a) { fetch('/media/'+a); }

function toggleKB() {
  const area = document.getElementById('keyboard-area');
  area.style.display = area.style.display==='block'?'none':'block';
  if (area.style.display==='block') document.getElementById('textinput').focus();
}
const textInput = document.getElementById('textinput');
let prevVal = '';
textInput.addEventListener('input', ()=>{
  const val = textInput.value;
  if (val.length < prevVal.length) socket.emit('key_press',{key:'Backspace'});
  else { const c=val.slice(prevVal.length); if(c) socket.emit('type_text',{text:c}); }
  prevVal = val;
});
textInput.addEventListener('keydown', e=>{ if(e.key==='Enter') socket.emit('key_press',{key:'Enter'}); });

// ── AI Chat ─────────────────────────────────────────────────────────────
let chatOpen = false;
function toggleChat() {
  chatOpen = !chatOpen;
  document.getElementById('chat-panel').classList.toggle('open', chatOpen);
  if (chatOpen) document.getElementById('chat-input').focus();
}

function appendMsg(role, html) {
  const msgs = document.getElementById('chat-messages');
  const div  = document.createElement('div');
  div.className = 'msg ' + role;
  div.innerHTML  = html;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div;
}

function markdownToHtml(md) {
  return md
    .replace(/```([\s\S]*?)```/g, (_,c)=>'<pre><code>'+escHtml(c.trim())+'</code></pre>')
    .replace(/`([^`]+)`/g, (_,c)=>'<code>'+escHtml(c)+'</code>')
    .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
    .replace(/\*(.+?)\*/g,'<em>$1</em>')
    .replace(/^#{1,3} (.+)$/gm,'<strong>$1</strong>')
    .replace(/\n/g,'<br>');
}

function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

async function sendAI() {
  const input = document.getElementById('chat-input');
  const msg   = input.value.trim();
  if (!msg) return;
  input.value = '';
  appendMsg('user', escHtml(msg));
  const typing = appendMsg('bot typing', '<span></span><span></span><span></span>');
  try {
    const res  = await fetch('/ai', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({message:msg})
    });
    const data = await res.json();
    typing.remove();
    appendMsg('bot', markdownToHtml(data.reply || '...'));
  } catch(e) {
    typing.remove();
    appendMsg('bot', '❌ Erreur de connexion au serveur');
  }
}

async function clearChat() {
  await fetch('/ai/clear', {method:'POST'});
  const msgs = document.getElementById('chat-messages');
  msgs.innerHTML = '<div class="msg bot">🗑️ Historique effacé !</div>';
}

document.getElementById('chat-input').addEventListener('keydown', e=>{
  if (e.key==='Enter') sendAI();
});
</script>
</body>
</html>"""

@app.route('/')
def index():
    return render_template_string(HTML)

if __name__ == '__main__':
    import socket as sock
    hostname = sock.gethostname()
    local_ip = sock.gethostbyname(hostname)
    print(f"""
╔══════════════════════════════════════════╗
║           ETYKX Remote — Serveur         ║
╠══════════════════════════════════════════╣
║  Ouvre sur ton téléphone :               ║
║  http://{local_ip}:{PORT:<27} ║
╚══════════════════════════════════════════╝
""")
    socketio.run(app, host='0.0.0.0', port=PORT, debug=False)
