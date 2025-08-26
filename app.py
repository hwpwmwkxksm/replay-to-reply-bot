from flask import Flask, request, render_template_string
import requests
import time

app = Flask(__name__)

HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>🔥 FB Convo Bot Panel 🔥</title>
<style>
    body {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
        color: #fff;
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 100vh;
    }
    .container {
        background: rgba(0,0,0,0.7);
        padding: 30px;
        border-radius: 15px;
        box-shadow: 0 0 20px rgba(0,0,0,0.5);
        width: 450px;
    }
    h2 {
        text-align: center;
        color: #ff6f61;
        margin-bottom: 20px;
        text-shadow: 1px 1px 5px #000;
    }
    textarea, input[type=text], input[type=number], input[type=file] {
        width: 100%;
        padding: 10px;
        border-radius: 8px;
        border: none;
        margin-bottom: 15px;
    }
    input[type=submit] {
        background: #ff6f61;
        border: none;
        padding: 12px 20px;
        color: #fff;
        font-weight: bold;
        border-radius: 10px;
        width: 100%;
        cursor: pointer;
        transition: 0.3s;
    }
    input[type=submit]:hover {
        background: #ff3b2e;
    }
    .message {
        background: rgba(255,255,255,0.1);
        padding: 10px;
        border-radius: 10px;
        text-align: center;
        margin-top: 15px;
        color: #00ffea;
        font-weight: bold;
    }
</style>
</head>
<body>
<div class="container">
<h2>💬 FB Convo Bot Panel</h2>
<form method="post" enctype="multipart/form-data">
  FBState Cookies (c_user,xs):<br>
  <textarea name="cookies" rows="3" placeholder="c_user=...; xs=..."></textarea>
  
  Target Thread ID or Username:<br>
  <input type="text" name="thread" placeholder="Enter thread ID or username">
  
  Message (or upload .txt file):<br>
  <textarea name="message" rows="2" placeholder="Type your message here"></textarea>
  OR upload file: <input type="file" name="file">
  
  Delay between messages (seconds):<br>
  <input type="number" name="delay" value="5" min="1">
  
  <input type="submit" value="🚀 Send Messages">
</form>

{% if message %}
<div class="message">{{ message }}</div>
{% endif %}
</div>
</body>
</html>
"""

def send_message(cookies, thread_id, msg):
    url = f'https://www.facebook.com/messages/send/?thread_id={thread_id}'
    headers = {'User-Agent': 'Mozilla/5.0'}
    data = {'body': msg}
    r = requests.post(url, cookies=cookies, headers=headers, data=data)
    return r.status_code == 200

@app.route("/", methods=["GET","POST"])
def index():
    message = ""
    if request.method == "POST":
        cookie_text = request.form.get("cookies")
        thread_id = request.form.get("thread")
        msg = request.form.get("message")
        file = request.files.get("file")
        delay = int(request.form.get("delay",5))
        
        cookies = {}
        for part in cookie_text.split(';'):
            if '=' in part:
                k,v = part.strip().split('=',1)
                cookies[k] = v
        
        messages = []
        if file:
            messages = [line.strip() for line in file.read().decode().splitlines() if line.strip()]
        if msg:
            messages.append(msg)
        
        success_count = 0
        for m in messages:
            try:
                if send_message(cookies, thread_id, m):
                    success_count += 1
                time.sleep(delay)
            except:
                continue
        
        message = f"✅ Sent {success_count}/{len(messages)} messages to {thread_id}."
    
    return render_template_string(HTML, message=message)

if __name__ == "__main__":
    app.run(debug=True)
