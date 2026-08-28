import json
import re
import time
import requests
import websocket
import threading
import random
import os
from flask import Flask, render_template_string, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "marshall_secret_key_secure_panel"

USERS = {
    "Marshall": "oopp0099",
    "Bolana": "oopp00998",
    "Osama": "oopp009987"
}

SERVER_ID = "1272600775331414159"
API = "https://discord.com/api/v9/channels"
BASE_MSG = """مرحبا بك انا Moderator 𝕭𝖔𝕷𝖆𝖓𝖆 من فريق الإدارة ONESTATE وسأكون مسؤول عن تذكرتك 
# • من فضلك ارفق دليل 
# • اسم المخالف 
# • الخادم الخاص بك"""

DEVICE_PROFILES = [
    {
        "User-Agent": "Discord/188215 CFNetwork/1498.700.2 Darwin/23.4.0",
        "X-Super-Properties": "eyJvcyI6IiOSyIsImJyb3dzZXIiOiJEaXNjb3JkIENsaWVudCIsImRldmljZSI6ImlQaG9uZSAxMyBwcm8gbWF4Iiwic3lzdGVtX3ZlcnNpb24iOiIxNy41In0="
    },
    {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
        "X-Super-Properties": "eyJvcyI6ImlPUyIsImRyb3dzZXIiOiJkaXNjb3JkIiwiZGV2aWNlIjoiaVBob25lIiwic3lzdGVtX3ZlcnNpb24iOiIxNy40LjEif="
    }
]

user_tokens = {}
bot_running = False
bot_thread = None
active_tickets = set()
MAX_TICKETS = 3
current_speed = 0.3  # السرعة الافتتاحية
received_tickets_log = []
state_lock = threading.Lock()

def get_secure_headers(token):
    profile = random.choice(DEVICE_PROFILES)
    return {
        "Authorization": token,
        "Content-Type": "application/json",
        "User-Agent": profile["User-Agent"],
        "X-Super-Properties": profile["X-Super-Properties"],
        "X-Discord-Locale": "ar"
    }

def safe_post(token, url, payload):
    try:
        headers = get_secure_headers(token)
        res = requests.post(url, json=payload, headers=headers, timeout=5)
        if res.status_code == 429:
            retry_after = res.json().get("retry_after", current_speed)
            time.sleep(retry_after)
            return safe_post(token, url, payload)
        return res
    except Exception:
        return None

def process_ticket(token, ch_id, name):
    with state_lock:
        if len(active_tickets) >= MAX_TICKETS or ch_id in active_tickets:
            return
        active_tickets.add(ch_id)

    time.sleep(current_speed)
    res = safe_post(token, f"{API}/{ch_id}/messages", {"content": BASE_MSG})
    
    if res and res.status_code in [200, 201]:
        with state_lock:
            if len(received_tickets_log) >= 10:
                received_tickets_log.pop(0)
            received_tickets_log.append(f"تم استلام التكت (سرعة {current_speed}ث): #{name}")
        
    with state_lock:
        if ch_id in active_tickets:
            active_tickets.remove(ch_id)

def run_discord_bot(token):
    global bot_running
    def on_message(ws, msg):
        if not bot_running:
            ws.close()
            return
        try:
            raw = json.loads(msg)
            if raw.get("op") == 10:
                ws.send(json.dumps({"op": 1, "d": None}))
                
            if raw.get("t") == "CHANNEL_CREATE":
                d = raw.get("d", {})
                if d.get("guild_id") == SERVER_ID and d.get("type") == 0:
                    name = d.get("name", "")
                    if any(w in name for w in ["شكوي", "شكوى", "تكت", "ticket"]):
                        ch_id = d.get("id")
                        created_at = ((int(ch_id) >> 22) + 1420070400000) / 1000.0
                        if time.time() - created_at > 60:
                            return
                        with state_lock:
                            if len(active_tickets) >= MAX_TICKETS:
                                return
                        threading.Thread(target=process_ticket, args=(token, ch_id, name)).start()
        except Exception:
            pass

    def on_open(ws):
        payload = {
            "op": 2,
            "d": {
                "token": token,
                "properties": {"os": "ios", "browser": "discord", "device": "phone"},
                "intents": 1 << 0
            }
        }
        ws.send(json.dumps(payload))

    ws_url = "wss://gateway.discord.gg/?v=9&encoding=json"
    while bot_running:
        try:
            ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message)
            ws.run_forever()
        except Exception:
            time.sleep(1)

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تسجيل الدخول - لوحة مرشال</title>
    <style>
        body { background-color: #050505; color: #ffffff; font-family: Tahoma, sans-serif; text-align: center; margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; height: 100vh; }
        .login-card { background: #121212; width: 350px; padding: 30px; border-radius: 12px; border: 1px solid #222; box-shadow: 0 10px 30px rgba(0,0,0,0.8); }
        h2 { color: #38bdf8; margin-bottom: 5px; }
        .dev-tag { font-size: 11px; color: #ef4444; margin-bottom: 20px; font-weight: bold; }
        input { width: 100%; padding: 12px; margin: 10px 0; background: #1a1a1a; border: 1px solid #333; color: white; border-radius: 6px; box-sizing: border-box; text-align: center; }
        .btn { width: 100%; padding: 12px; margin-top: 15px; background: #2563eb; color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; }
        .error { color: #ef4444; font-size: 12px; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="login-card">
        <h2>تسجيل الدخول</h2>
        <div class="dev-tag">المطور مرشال احذر ⚠️</div>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
        <form method="POST">
            <input type="text" name="username" placeholder="اسم المستخدم" required>
            <input type="password" name="password" placeholder="الرمز السري" required>
            <button type="submit" class="btn">دخول</button>
        </form>
    </div>
</body>
</html>
"""

TOKEN_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>إدخال التوكن</title>
    <style>
        body { background-color: #050505; color: #ffffff; font-family: Tahoma, sans-serif; text-align: center; margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; height: 100vh; }
        .card { background: #121212; width: 380px; padding: 30px; border-radius: 12px; border: 1px solid #222; }
        h2 { color: #22c55e; margin-bottom: 5px; }
        .welcome { font-size: 15px; color: #38bdf8; margin-bottom: 20px; }
        textarea { width: 100%; height: 80px; padding: 10px; background: #1a1a1a; border: 1px solid #333; color: white; border-radius: 6px; box-sizing: border-box; resize: none; font-size: 12px; text-align: center; }
        .btn { width: 100%; padding: 12px; margin-top: 15px; background: #22c55e; color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; }
    </style>
</head>
<body>
    <div class="card">
        <h2>أهلاً بك مع المعلم مرشال 🤍</h2>
        <div class="welcome">المستخدم: {{ username }}</div>
        <form method="POST">
            <textarea name="token" placeholder="الصق توكن الحساب هنا..." required></textarea>
            <button type="submit" class="btn">حفظ والبدء 🚀</button>
        </form>
    </div>
</body>
</html>
"""

PANEL_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>لوحة التحكم الآمنة</title>
    <style>
        body { background-color: #050505; color: #f8fafc; font-family: Tahoma, sans-serif; text-align: center; margin: 0; padding: 15px; }
        .dev-banner { color: #ef4444; font-size: 14px; font-weight: bold; margin-bottom: 15px; background: #121212; padding: 8px; border-radius: 6px; border: 1px solid #222; display: inline-block; width: 100%; max-width: 400px; box-sizing: border-box; }
        .card { background: #121212; max-width: 400px; margin: 0 auto; padding: 25px; border-radius: 12px; border: 1px solid #222; box-shadow: 0 10px 30px rgba(0,0,0,0.8); }
        h1 { color: #38bdf8; font-size: 20px; margin-bottom: 5px; }
        .user-tag { color: #22c55e; font-size: 13px; margin-bottom: 15px; }
        .speed-badge { background: #1a1a1a; border: 1px solid #333; padding: 8px; border-radius: 6px; font-size: 13px; color: #38bdf8; margin-bottom: 15px; }
        .btn { display: block; width: 100%; padding: 14px; margin: 10px 0; font-size: 16px; font-weight: bold; border: none; border-radius: 8px; cursor: pointer; text-decoration: none; }
        .btn-start { background: #22c55e; color: white; }
        .btn-stop { background: #ef4444; color: white; }
        .speed-row { display: flex; gap: 10px; margin-bottom: 10px; }
        .btn-speed-up { background: #10b981; color: white; flex: 1; padding: 12px; font-size: 14px; font-weight: bold; border: none; border-radius: 8px; cursor: pointer; }
        .btn-speed-down { background: #f59e0b; color: white; flex: 1; padding: 12px; font-size: 14px; font-weight: bold; border: none; border-radius: 8px; cursor: pointer; }
        .log-box { background: #0a0a0a; border: 1px solid #222; border-radius: 6px; padding: 10px; height: 110px; overflow-y: auto; text-align: right; font-size: 12px; color: #a1a1aa; margin-top: 15px; }
        .log-title { color: #38bdf8; font-size: 13px; margin-bottom: 5px; text-align: right; font-weight: bold; }
    </style>
</head>
<body>
    <div class="dev-banner">⚠️ المطور مرشال احذر ⚠️</div>
    <div class="card">
        <h1>لوحة تحكم التكتات</h1>
        <div class="user-tag">أهلاً بك، {{ username }}</div>
        
        <div class="speed-badge">السرعة الحالية: <b>{{ speed }} ثانية</b></div>
        
        <!-- زر التشغيل / الإيقاف -->
        <form action="/toggle" method="post">
            {% if running %}
                <button type="submit" class="btn btn-stop">إيقاف البوت 🛑</button>
            {% else %}
                <button type="submit" class="btn btn-start">بدء البوت 🚀</button>
            {% endif %}
        </form>

        <!-- أزرار زيادة وتقليل السرعة تحت زر البدء مباشرة -->
        <div class="speed-row">
            <form action="/speed/up" method="post" style="flex: 1; margin:0;">
                <button type="submit" class="btn-speed-up" style="width: 100%;">⚡ زيادة السرعة</button>
            </form>
            <form action="/speed/down" method="post" style="flex: 1; margin:0;">
                <button type="submit" class="btn-speed-down" style="width: 100%;">⏳ تقليل السرعة</button>
            </form>
        </div>

        <div class="log-title">التكتات المستلمة:</div>
        <div class="log-box">
            {% for item in logs %}
                <div>• {{ item }}</div>
            {% else %}
                <div style="color: #555; text-align: center; margin-top: 30px;">لا توجد تكتات مستلمة بعد...</div>
            {% endfor %}
        </div>
        
        <a href="/logout" style="color: #ef4444; font-size: 11px; display: block; margin-top: 15px; text-decoration: none;">تسجيل خروج</a>
    </div>
    <script>
        setTimeout(() => { location.reload(); }, 3000);
    </script>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username in USERS and USERS[username] == password:
            session['user'] = username
            if username not in user_tokens:
                return redirect(url_for('set_token'))
            return redirect(url_for('panel'))
        else:
            error = "اسم المستخدم أو الرمز غير صحيح!"
    return render_template_string(LOGIN_HTML, error=error)

@app.route('/token', methods=['GET', 'POST'])
def set_token():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        token = request.form.get('token').strip()
        user_tokens[session['user']] = token
        return redirect(url_for('panel'))
        
    return render_template_string(TOKEN_HTML, username=session['user'])

@app.route('/panel')
def panel():
    if 'user' not in session or session['user'] not in user_tokens:
        return redirect(url_for('login'))
        
    return render_template_string(PANEL_HTML, username=session['user'], running=bot_running, speed=current_speed, logs=received_tickets_log)

@app.route('/toggle', methods=['POST'])
def toggle():
    global bot_running, bot_thread
    if 'user' not in session:
        return redirect(url_for('login'))
        
    current_user = session['user']
    token = user_tokens.get(current_user)
    
    if not bot_running:
        if token:
            bot_running = True
            bot_thread = threading.Thread(target=run_discord_bot, args=(token,))
            bot_thread.daemon = True
            bot_thread.start()
    else:
        bot_running = False
        
    return redirect(url_for('panel'))

@app.route('/speed/up', methods=['POST'])
def speed_up():
    global current_speed
    if current_speed > 0.1:
        current_speed = round(current_speed - 0.1, 1)  # تسريع الاستجابة
    return redirect(url_for('panel'))

@app.route('/speed/down', methods=['POST'])
def speed_down():
    global current_speed
    if current_speed < 3.0:
        current_speed = round(current_speed + 0.1, 1)  # إبطاء الاستجابة للأمان
    return redirect(url_for('panel'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
