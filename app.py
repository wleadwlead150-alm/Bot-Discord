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
app.secret_key = "marshall_secret_key_luxury_gold_v4"

USERS = {
    "Marshall": "oopp0099",
    "Bolana": "oopp00998",
    "Osama": "oopp009987"
}

SERVER_ID = "1272600775331414159"
API = "https://discord.com/api/v9/channels"

DEVICE_PROFILES = [
    {
        "User-Agent": "Discord/188215 CFNetwork/1498.700.2 Darwin/23.4.0",
        "X-Super-Properties": "eyJvcyI6IiOSyIsImJyb3dzZXIiOiJEaXNjb3JkIENsaWVudCIsImRldmljZSI6ImlQaG9uZSAxMyBwcm8gbWF4Iiwic3lzdGVtX3ZlcnNpb24iOiIxNy41In0="
    },
    {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
        "X-Super-Properties": "eyJvcyI6ImlPUyIsImRldmljZXIiOiJkaXNjb3JkIiwiZGV2aWNlIjoiaVBob25lIiwic3lzdGVtX3ZlcnNpb24iOiIxNy40LjEif="
    }
]

user_sessions = {
    "Marshall": {
        "running": False, 
        "speed": 0.3, 
        "thread": None, 
        "token": "",
        "message": "مرحباً عزيزي لاعب معك مرشال من فريق لإداري كيف يمكني مساعدتك"
    },
    "Bolana": {
        "running": False, 
        "speed": 0.3, 
        "thread": None, 
        "token": "",
        "message": "** اهلاً بك معك بولانا من فريق لاداره كيف اساعدك **\n\n<a:animatedarroworange:1330113117354463318>  *** __أهلا معك Moderator 𝕭𝖔𝕷𝖆𝖓𝖆 <a:firer:1280210368224034907> _ <a:100i:1423339524251189412>  مأهي مشكلتك؟__  ***"
    },
    "Osama": {
        "running": False, 
        "speed": 0.3, 
        "thread": None, 
        "token": "",
        "message": "** اهلاً بك معك أسامة من فريق لاداره كيف اساعدك **\n\n<a:animatedarroworange:1330113117354463318>  *** __أهلا معك Moderator 𝕭𝖔𝕷𝖆𝖓𝖆 <a:firer:1280210368224034907> _ <a:100i:1423339524251189412>  مأهي مشكلتك؟__  ***"
    }
}

active_tickets = set()
MAX_TICKETS = 3
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

def safe_post(token, url, payload, current_speed):
    try:
        headers = get_secure_headers(token)
        res = requests.post(url, json=payload, headers=headers, timeout=5)
        if res.status_code == 429:
            retry_after = res.json().get("retry_after", current_speed)
            time.sleep(retry_after)
            return safe_post(token, url, payload, current_speed)
        return res
    except Exception:
        return None

def process_ticket(username, token, ch_id, name):
    with state_lock:
        if len(active_tickets) >= MAX_TICKETS or ch_id in active_tickets:
            return
        active_tickets.add(ch_id)

    current_speed = user_sessions[username]["speed"]
    custom_msg = user_sessions[username]["message"]
    
    time.sleep(current_speed)
    
    res = safe_post(token, f"{API}/{ch_id}/messages", {"content": custom_msg}, current_speed)
    
    if res and res.status_code in [200, 201]:
        with state_lock:
            if len(received_tickets_log) >= 10:
                received_tickets_log.pop(0)
            received_tickets_log.append(f"[{username}] استلم تكت (سرعة {current_speed}ث): #{name}")
        
    with state_lock:
        if ch_id in active_tickets:
            active_tickets.remove(ch_id)

def run_discord_bot(username):
    token = user_sessions[username]["token"]
    
    def on_message(ws, msg):
        if not user_sessions[username]["running"]:
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
                        threading.Thread(target=process_ticket, args=(username, token, ch_id, name)).start()
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
    while user_sessions[username]["running"]:
        try:
            ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message)
            ws.run_forever()
        except Exception:
            time.sleep(1)

PANEL_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>لوحة التحكم الملكية</title>
    <style>
        body { background-color: #080808; color: #e2e8f0; font-family: Tahoma, sans-serif; text-align: center; margin: 0; padding: 15px; }
        .dev-banner { color: #f59e0b; font-size: 13px; font-weight: bold; margin-bottom: 15px; background: linear-gradient(135deg, #171717, #0d0d0d); padding: 10px; border-radius: 8px; border: 1px solid #332711; display: inline-block; width: 100%; max-width: 400px; box-sizing: border-box; box-shadow: 0 4px 15px rgba(245, 158, 11, 0.1); }
        .card { background: linear-gradient(180deg, #121212, #0a0a0a); max-width: 400px; margin: 0 auto; padding: 25px; border-radius: 14px; border: 1px solid #262015; box-shadow: 0 15px 35px rgba(0,0,0,0.9), 0 0 20px rgba(245, 158, 11, 0.05); }
        h1 { color: #f59e0b; font-size: 21px; margin-bottom: 5px; text-shadow: 0 2px 10px rgba(245, 158, 11, 0.2); }
        .user-tag { color: #34d399; font-size: 13px; margin-bottom: 15px; font-weight: bold; }
        .speed-badge { background: #161616; border: 1px solid #2d2414; padding: 10px; border-radius: 8px; font-size: 14px; color: #facc15; margin-bottom: 15px; }
        .btn { display: block; width: 100%; padding: 14px; margin: 12px 0; font-size: 16px; font-weight: bold; border: none; border-radius: 8px; cursor: pointer; text-decoration: none; transition: 0.2s; }
        .btn-start { background: linear-gradient(135deg, #059669, #047857); color: white; box-shadow: 0 4px 12px rgba(5, 150, 105, 0.3); }
        .btn-stop { background: linear-gradient(135deg, #dc2626, #b91c1c); color: white; box-shadow: 0 4px 12px rgba(220, 38, 38, 0.3); }
        .btn-speed-up { display: block; width: 100%; padding: 12px; margin: 8px 0; background: #18181b; border: 1px solid #059669; color: #34d399; font-size: 14px; font-weight: bold; border-radius: 8px; cursor: pointer; }
        .btn-speed-down { display: block; width: 100%; padding: 12px; margin: 8px 0; background: #18181b; border: 1px solid #d97706; color: #fbbf24; font-size: 14px; font-weight: bold; border-radius: 8px; cursor: pointer; }
        
        .msg-section { text-align: right; margin-top: 15px; }
        .msg-title { color: #f59e0b; font-size: 13px; margin-bottom: 5px; font-weight: bold; }
        textarea { width: 100%; height: 75px; padding: 8px; background: #0f0f11; border: 1px solid #2a2212; color: #e2e8f0; border-radius: 8px; box-sizing: border-box; resize: none; font-size: 11px; text-align: right; }
        textarea:focus { border-color: #f59e0b; outline: none; }
        .btn-save-msg { width: 100%; padding: 9px; margin-top: 6px; background: linear-gradient(135deg, #d97706, #b45309); color: white; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; font-size: 13px; box-shadow: 0 4px 10px rgba(217, 119, 6, 0.2); }

        .log-box { background: #050505; border: 1px solid #221a0d; border-radius: 8px; padding: 10px; height: 100px; overflow-y: auto; text-align: right; font-size: 12px; color: #94a3b8; margin-top: 5px; }
        .log-title { color: #f59e0b; font-size: 13px; margin-bottom: 5px; text-align: right; font-weight: bold; }
    </style>
</head>
<body>
    <div class="dev-banner">✨ لوحة المطور الملكية - مرشال ✨</div>
    <div class="card">
        <h1>لوحة تحكم التكتات</h1>
        <div class="user-tag">أهلاً بك، {{ username }}</div>
        
        <div class="speed-badge">سرعتك الحالية: <b>{{ speed }} ثانية</b></div>
        
        <form action="/toggle" method="post">
            {% if running %}
                <button type="submit" class="btn btn-stop">إيقاف بوتك 🛑</button>
            {% else %}
                <button type="submit" class="btn btn-start">بدء بوتك 🚀</button>
            {% endif %}
        </form>

        <form action="/speed/up" method="post">
            <button type="submit" class="btn-speed-up">⚡ زيادة سرعة الرد</button>
        </form>
        
        <form action="/speed/down" method="post">
            <button type="submit" class="btn-speed-down">⏳ تخفيف سرعة الرد</button>
        </form>

        <div class="msg-section">
            <div class="msg-title">رسالة التكت الخاصة بك:</div>
            <form action="/update_msg" method="post">
                <textarea name="custom_msg">{{ message }}</textarea>
                <button type="submit" class="btn-save-msg">حفظ التعديلات 💾</button>
            </form>
        </div>

        <div class="log-title" style="margin-top: 15px;">التكتات المستلمة:</div>
        <div class="log-box">
            {% for item in logs %}
                <div>• {{ item }}</div>
            {% else %}
                <div style="color: #444; text-align: center; margin-top: 25px;">لا توجد تكتات مستلمة بعد...</div>
            {% endfor %}
        </div>
        
        <a href="/logout" style="color: #ef4444; font-size: 11px; display: block; margin-top: 18px; text-decoration: none;">تسجيل خروج</a>
    </div>
</body>
</html>
"""

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تسجيل الدخول - لوحة مرشال</title>
    <style>
        body { background-color: #080808; color: #ffffff; font-family: Tahoma, sans-serif; text-align: center; margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; height: 100vh; }
        .login-card { background: linear-gradient(180deg, #121212, #0a0a0a); width: 350px; padding: 30px; border-radius: 14px; border: 1px solid #262015; box-shadow: 0 15px 35px rgba(0,0,0,0.9), 0 0 20px rgba(245, 158, 11, 0.05); }
        h2 { color: #f59e0b; margin-bottom: 5px; text-shadow: 0 2px 10px rgba(245, 158, 11, 0.2); }
        .dev-tag { font-size: 11px; color: #f59e0b; margin-bottom: 20px; font-weight: bold; }
        input { width: 100%; padding: 12px; margin: 10px 0; background: #0f0f11; border: 1px solid #2a2212; color: white; border-radius: 8px; box-sizing: border-box; text-align: center; }
        input:focus { border-color: #f59e0b; outline: none; }
        .btn { width: 100%; padding: 12px; margin-top: 15px; background: linear-gradient(135deg, #d97706, #b45309); color: white; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; box-shadow: 0 4px 10px rgba(217, 119, 6, 0.3); }
        .error { color: #ef4444; font-size: 12px; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="login-card">
        <h2>تسجيل الدخول الملكي</h2>
        <div class="dev-tag">✨ لوحة مرشال الأمنة ✨</div>
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
        body { background-color: #080808; color: #ffffff; font-family: Tahoma, sans-serif; text-align: center; margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; height: 100vh; }
        .card { background: linear-gradient(180deg, #121212, #0a0a0a); width: 380px; padding: 30px; border-radius: 14px; border: 1px solid #262015; box-shadow: 0 15px 35px rgba(0,0,0,0.9); }
        h2 { color: #f59e0b; margin-bottom: 5px; }
        .welcome { font-size: 14px; color: #34d399; margin-bottom: 20px; font-weight: bold; }
        textarea { width: 100%; height: 80px; padding: 10px; background: #0f0f11; border: 1px solid #2a2212; color: white; border-radius: 8px; box-sizing: border-box; resize: none; font-size: 12px; text-align: center; }
        textarea:focus { border-color: #f59e0b; outline: none; }
        .btn { width: 100%; padding: 12px; margin-top: 15px; background: linear-gradient(135deg, #059669, #047857); color: white; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; box-shadow: 0 4px 10px rgba(5, 150, 105, 0.3); }
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

@app.route('/', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username in USERS and USERS[username] == password:
            session['user'] = username
            if not user_sessions[username]["token"]:
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
        user_sessions[session['user']]["token"] = token
        return redirect(url_for('panel'))
        
    return render_template_string(TOKEN_HTML, username=session['user'])

@app.route('/panel')
def panel():
    if 'user' not in session or not user_sessions[session['user']]["token"]:
        return redirect(url_for('login'))
        
    username = session['user']
    user_data = user_sessions[username]
    return render_template_string(
        PANEL_HTML, 
        username=username, 
        running=user_data["running"], 
        speed=user_data["speed"], 
        message=user_data["message"],
        logs=received_tickets_log
    )

@app.route('/toggle', methods=['POST'])
def toggle():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    username = session['user']
    user_data = user_sessions[username]
    
    if not user_data["running"]:
        if user_data["token"]:
            user_data["running"] = True
            t = threading.Thread(target=run_discord_bot, args=(username,))
            t.daemon = True
            t.start()
            user_data["thread"] = t
    else:
        user_data["running"] = False
        
    return redirect(url_for('panel'))

@app.route('/speed/up', methods=['POST'])
def speed_up():
    if 'user' in session:
        username = session['user']
        if user_sessions[username]["speed"] > 0.1:
            user_sessions[username]["speed"] = round(user_sessions[username]["speed"] - 0.1, 1)
    return redirect(url_for('panel'))

@app.route('/speed/down', methods=['POST'])
def speed_down():
    if 'user' in session:
        username = session['user']
        if user_sessions[username]["speed"] < 3.0:
            user_sessions[username]["speed"] = round(user_sessions[username]["speed"] + 0.1, 1)
    return redirect(url_for('panel'))

@app.route('/update_msg', methods=['POST'])
def update_msg():
    if 'user' in session:
        username = session['user']
        new_msg = request.form.get('custom_msg', '').strip()
        if new_msg:
            user_sessions[username]["message"] = new_msg
    return redirect(url_for('panel'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
