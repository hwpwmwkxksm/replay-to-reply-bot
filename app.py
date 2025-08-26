from flask import Flask, request, jsonify, render_template_string
import threading, time, requests, os
import random

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2 MB upload limit

---------------------- Globals ----------------------

EAAD_TOKEN = ""
THREAD_ID = ""
POLL_INTERVAL = 5
HATER_NAME = ""  # optional prefix
MESSAGE_LIST = []
seen_messages = set()
bot_thread = None
bot_stop_event = threading.Event()
logs = []
logs_lock = threading.Lock()
state_lock = threading.Lock()

---------------------- Helpers ----------------------

def add_log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] {msg}"
    with logs_lock:
        logs.append(entry)
        if len(logs) > 1000:
            del logs[0: len(logs)-1000]
    print(entry)

# Graph API helpers using EAAD token
GRAPH_BASE = "https://graph.facebook.com/v18.0"

def graph_get(path, params=None):
    if params is None:
        params = {}
    params['access_token'] = EAAD_TOKEN
    try:
        r = requests.get(f"{GRAPH_BASE}/{path}", params=params, timeout=15)
        return r.json()
    except Exception as e:
        add_log(f"GET error {path}: {e}")
        return {}

def graph_post(path, data=None):
    if data is None:
        data = {}
    params = {'access_token': EAAD_TOKEN}
    try:
        r = requests.post(f"{GRAPH_BASE}/{path}", params=params, json=data, timeout=15)
        return r.json()
    except Exception as e:
        add_log(f"POST error {path}: {e}")
        return {}

---------------------- Bot Logic ----------------------

def handle_new_message(msg):
    msg_id = msg.get('id')
    if not msg_id or msg_id in seen_messages:
        return
    seen_messages.add(msg_id)
    sender = msg.get('from', {})
    sender_id = sender.get('id')
    text = msg.get('message', '')

    if sender_id is None:
        return

    # Select message from MESSAGE_LIST
    if MESSAGE_LIST:
        reply_text = random.choice(MESSAGE_LIST)
    else:
        reply_text = f"I got your reply: {text[:400]}"

    if HATER_NAME:
        reply_text = f"[{HATER_NAME}] {reply_text}"

    payload = {
        'recipient': {'id': sender_id},
        'message': {'text': reply_text}
    }
    resp = graph_post('me/messages', payload)
    add_log(f"Replied to {sender_id}: {reply_text} | API Response: {resp}")

def poll_loop(stop_event, interval_getter):
    add_log("Bot thread started")
    while not stop_event.is_set():
        if not EAAD_TOKEN or not THREAD_ID:
            add_log("EAAD_TOKEN or THREAD_ID not set; sleeping")
            time.sleep(2)
            continue
        try:
            params = {'fields': 'messages.limit(5){message,from,id}'}
            data = graph_get(f'{THREAD_ID}', params=params)
            if 'data' in data or 'messages' in data:
                messages = data.get('messages', {}).get('data', [])
                for msg in reversed(messages):
                    try:
                        if 'from' in msg and msg['from'].get('id') != 'me':
                            handle_new_message(msg)
                    except Exception as e:
                        add_log(f"Error handling message: {e}")
            time.sleep(interval_getter())
        except Exception as e:
            add_log(f"Poll loop exception: {e}")
            time.sleep(5)
    add_log("Bot thread stopped")

---------------------- Flask Routes / UI ----------------------

TEMPLATE = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Messenger EAAD Bot Panel</title>
<style>
body {
    font-family: 'Courier New', monospace;
    background: #1a1a1a;
    color: #ff0000;
    margin: 20px;
    text-align: center;
}
h2 {
    color: #ff0000;
    text-shadow: 0 0 10px #ff0000, 0 0 20px #ff0000, 0 0 30px #ff0000;
    font-size: 2.5em;
    margin-bottom: 30px;
}
input, button {
    padding: 10px;
    margin: 8px;
    border: 2px solid #ff0000;
    background: #2a2a2a;
    color: #ff0000;
    font-family: 'Courier New', monospace;
    border-radius: 5px;
    box-shadow: 0 0 10px #ff0000, 0 0 20px #ff0000;
    transition: all 0.3s ease;
}
input:focus, button:hover {
    outline: none;
    box-shadow: 0 0 15px #ff0000, 0 0 25px #ff0000, 0 0 35px #ff0000;
    background: #3a3a3a;
}
textarea {
    width: 90%;
    height: 250px;
    background: #2a2a2a;
    color: #ff0000;
    border: 2px solid #ff0000;
    border-radius: 5px;
    padding: 10px;
    font-family: 'Courier New', monospace;
    box-shadow: 0 0 10px #ff0000;
    resize: none;
}
label {
    color: #ff0000;
    text-shadow: 0 0 5px #ff0000;
    font-size: 1.2em;
}
div {
    margin: 15px 0;
}
#status {
    color: #ff0000;
    text-shadow: 0 0 5px #ff0000;
    font-weight: bold;
}
button {
    cursor: pointer;
    font-size: 1.1em;
}
</style>
</head>
<body>
<h2>Messenger Reply-to-Reply Bot Panel</h2>
<div>
    <label>EAAD Token:</label><br>
    <input id="token" style="width:80%" placeholder="Paste EAAD token">
    <button onclick="saveToken()">Save Token</button>
</div>
<div>
    <label>Thread ID:</label><br>
    <input id="thread" style="width:300px">
</div>
<div>
    <label>Hater Name (Prefix):</label><br>
    <input id="hater" style="width:200px">
</div>
<div>
    <label>Polling Interval (sec):</label>
    <input id="interval" type="number" min="1" value="5" style="width:80px">
</div>
<div>
    <label>Message File (.txt):</label><br>
    <input type="file" id="msgfile">
</div>
<div>
    <button onclick="startBot()">Start</button>
    <button onclick="stopBot()">Stop</button>
    <span id="status">Status: Stopped</span>
</div>
<h3>Logs</h3>
<textarea id="logs" readonly></textarea>
<script>
function saveToken(){
    const t=document.getElementById('token').value
    fetch('/set_token',{method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({token:t})})
    .then(r=>r.json()).then(j=>alert(j.msg))
}
function startBot(){
    const interval=document.getElementById('interval').value
    const thread=document.getElementById('thread').value
    const hater=document.getElementById('hater').value
    const fileInput=document.getElementById('msgfile')
    const file=fileInput.files[0]
    const formData=new FormData()
    formData.append('file', file)
    formData.append('interval', interval)
    formData.append('thread', thread)
    formData.append('hater', hater)
    fetch('/start',{method:'POST', body:formData}).then(r=>r.json()).then(j=>document.getElementById('status').innerText='Status: Running')
}
function stopBot(){
    fetch('/stop',{method:'POST'}).then(r=>r.json()).then(j=>document.getElementById('status').innerText='Status: Stopped')
}
async function refreshLogs(){
    const r=await fetch('/logs')
    const j=await r.json()
    document.getElementById('logs').value=j.logs.join('\n')
}
setInterval(refreshLogs,2000)
window.onload=refreshLogs
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(TEMPLATE)

@app.route('/set_token', methods=['POST'])
def set_token():
    global EAAD_TOKEN
    data = request.get_json() or {}
    token = data.get('token','').strip()
    with state_lock:
        EAAD_TOKEN = token
        seen_messages.clear()
        add_log('EAAD_TOKEN updated via UI')
    return jsonify({'ok':True,'msg':'Token saved'})

@app.route('/start', methods=['POST'])
def start():
    global bot_thread, bot_stop_event, THREAD_ID, POLL_INTERVAL, HATER_NAME, MESSAGE_LIST
    form = request.form
    THREAD_ID = form.get('thread','').strip()
    HATER_NAME = form.get('hater','').strip()
    POLL_INTERVAL = int(form.get('interval',5))
    file = request.files.get('file')
    if file:
        MESSAGE_LIST = [line.strip() for line in file.read().decode('utf-8').splitlines() if line.strip()]

    with state_lock:
        if bot_thread and bot_thread.is_alive():
            return jsonify({'ok':False,'msg':'Bot already running'})
        bot_stop_event = threading.Event()
        bot_thread = threading.Thread(target=poll_loop, args=(bot_stop_event, lambda: POLL_INTERVAL), daemon=True)
        bot_thread.start()
    add_log('Bot started')
    return jsonify({'ok':True,'msg':'Bot started'})

@app.route('/stop', methods=['POST'])
def stop():
    global bot_thread, bot_stop_event
    with state_lock:
        if bot_thread and bot_thread.is_alive():
            bot_stop_event.set()
            bot_thread.join(timeout=10)
            add_log('Stop requested')
        return jsonify({'ok':True,'msg':'Bot stopping'})
    else:
        return jsonify({'ok':False,'msg':'Bot not running'})

@app.route('/logs')
def get_logs():
    with logs_lock:
        return jsonify({'logs': list(logs)})

if __name__ == '__main__':
    add_log('Starting Flask EAAD Bot Panel')
    app.run(host='0.0.0.0', port=5000, debug=False)
