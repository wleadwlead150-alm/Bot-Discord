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
app.secret_key = "marshall_secret_key_ultra_luxury_v7"

USERS = {
    "Marshall": "oopp0099",
    "Bolana": "oopp00998",
    "Osama": "oopp009987",
    "Kara": "oopp009988"
}

SERVER_ID = "1272600775331414159"
API = "https://discord.com/api/v9/channels"

# قنوات التنبيه المخصصة لكل شخص
LOG_CHANNELS = {
    "Osama": "1542223899792510996",
    "Marshall": "1542223986388107264"
}

DEVICE_PROFILES = [
    {
        "User-Agent": "Discord/188215 CFNetwork/1498.700.2 Darwin/23.4.0",
        "X-Super-Properties": "eyJvcyI6IiOSyIsImJyb3dzZXIiOiJEaXNjb3JkIENsaWVudCIsImRldmljZSI6ImlQaG9uZSAxMywgcHJvLCBtYXgiLCJzeXN0ZW1fdmVyc2lvbiI6IjE3LjUif="
    },
    {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
        "X-Super-Properties": "eyJvcyI6ImlPUyIsImJyb3dzZXIiOiJkaXNjb3JkIiwiZGV2aWNlIjoiaVBob25lIiwic3lzdGVtX3ZlcnNpb24iOiIxNy40LjEif="
    }
]

user_sessions = {
    "Marshall": {
        "running": False, "speed": 0.5, "thread": None, "token": "",
        "message": "مرحباً عزيزي لاعب معك مرشال من فريق الإداري كيف يمكنني مساعدتك",
        "logs": [], "count": 0
    },
    "Bolana": {
        "running": False, "speed": 0.5, "thread": None, "token": "",
        "message": "** أهلاً بك معك بولانا من فريق الإدارة كيف أساعدك **",
        "logs": [], "count": 0
    },
    "Osama": {
        "running": False, "speed": 0.5, "thread": None, "token": "",
        "message": "** أهلاً بك معك أسامة، مختص حصراً بشكاوى قادة الفصائل **",
        "logs": [], "count": 0
    },
    "Kara": {
        "running": False, "speed": 0.5, "thread": None, "token": "",
        "message": "** أهلاً بك معك كارا من فريق الإدارة كيف أساعدك **",
        "logs": [], "count": 0
    }
}

active_tickets = set()
MAX_TICKETS = 3
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
        if not user_sessions[username]["running"]:
            return
        if user_sessions[username]["count"] >= MAX_TICKETS:
            user_sessions[username]["running"] = False
            return
        if ch_id in active_tickets:
            return
        active_tickets.add(ch_id)

    current_speed = user_sessions[username]["speed"]
    custom_msg = user_sessions[username]["message"]
    
    # تأخير عشوائي متعمد لحماية الحسابات من الحظر وتبدو بشرية تماماً
    human_delay = random.uniform(2.0, 5.0) + current_speed
    time.sleep(human_delay)
    
    # إرسال رسالة الترحيب داخل التكت
    res = safe_post(token, f"{API}/{ch_id}/messages", {"content": custom_msg}, current_speed)
    
    if res and res.status_code in [200, 201]:
        ticket_url = f"https://discord.com/channels/{SERVER_ID}/{ch_id}"
        log_text = f"تم استلام تكت **#{name}** | الرابط: {ticket_url}"
        
        # إرسال إشعار للشات المخصص إذا كان المستخدم أسامة أو مرشال
        if username in LOG_CHANNELS:
            alert_channel_id = LOG_CHANNELS[username]
            alert_payload = {"content": f"🚨 **{username}** استلم تكت جديد:\n• اسم التكت: `#{name}`\n• الرابط: {ticket_url}"}
            safe_post(token, f"{API}/{alert_channel_id}/messages", alert_payload, current_speed)

        with state_lock:
            user_data = user_sessions[username]
            if user_data["count"] < MAX_TICKETS:
                user_data["count"] += 1
                user_data["logs"].append(f"{log_text} (العدد: {user_data['count']}/3)")
                if user_data["count"] >= MAX_TICKETS:
                    user_data["running"] = False
                    user_data["logs"].append("🛑 وصل الحد الأقصى (3 تكتات)، توقف البوت تلقائياً.")
        
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
                    name = d.get("name", "").lower()
                    if any(w in name for w in ["شكوي", "شكوى", "تكت", "ticket"]):
                        
                        # فلترة خاصة لأسامة: يستلم حصراً شكاوى قادة الفصائل
                        if username == "Osama":
                            is_leader_complaint = any(w in name for w in ["قائد", "فصيل", "ليدر"])
                            if not is_leader_complaint:
                                return

                        ch_id = d.get("id")
                        created_at = ((int(ch_id) >> 22) + 1420070400000) / 1000.0
                        if time.time() - created_at > 120:
                            return
                        with state_lock:
                            if user_sessions[username]["count"] >= MAX_TICKETS or not user_sessions[username]["running"]:
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
            time.sleep(3)

PANEL_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>لوحة التحكم الملكية</title>
    <style>
        body { background-color: #050505; color: #e2e8f0; font-family: Tahoma, sans-serif; text-align: center; margin: 0; padding: 15px; }
        .avatar-box { margin-bottom: 10px; }
        .avatar-box img { width: 85px; height: 85px; border-radius: 50%; border: 2px solid #f59e0b; box-shadow: 0 0 20px rgba(245, 158, 11, 0.4); object-fit: cover; }
        .card { background: linear-gradient(180deg, #101012, #070708); max-width: 420px; margin: 0 auto; padding: 20px; border-radius: 16px; border: 1px solid #2a2212; box-shadow: 0 20px 40px rgba(0,0,0,0.95), 0 0 25px rgba(245, 158, 11, 0.08); }
        h1 { color: #f59e0b; font-size: 20px; margin-bottom: 5px; text-shadow: 0 2px 10px rgba(245, 158, 11, 0.3); }
        .user-tag { color: #34d399; font-size: 13px; margin-bottom: 12px; font-weight: bold; }
        .speed-badge { background: #141416; border: 1px solid #2d2414; padding: 10px; border-radius: 8px; font-size: 13px; color: #facc15; margin-bottom: 12px; }
        .btn { display: block; width: 100%; padding: 13px; margin: 10px 0; font-size: 15px; font-weight: bold; border: none; border-radius: 8px; cursor: pointer; text-decoration: none; transition: 0.2s; }
        .btn-start { background: linear-gradient(135deg, #059669, #047857); color: white; box-shadow: 0 4px 12px rgba(5, 150, 105, 0.3); }
        .btn-stop { background: linear-gradient(135deg, #dc2626, #b91c1c); color: white; box-shadow: 0 4px 12px rgba(220, 38, 38, 0.3); }
        .btn-speed-up { display: block; width: 100%; padding: 10px; margin: 6px 0; background: #141416; border: 1px solid #059669; color: #34d399; font-size: 13px; font-weight: bold; border-radius: 8px; cursor: pointer; }
        .btn-speed-down { display: block; width: 100%; padding: 10px; margin: 6px 0; background: #141416; border: 1px solid #d97706; color: #fbbf24; font-size: 13px; font-weight: bold; border-radius: 8px; cursor: pointer; }
        
        .msg-section { text-align: right; margin-top: 12px; }
        .msg-title { color: #f59e0b; font-size: 12px; margin-bottom: 4px; font-weight: bold; }
        textarea { width: 100%; height: 70px; padding: 8px; background: #08080a; border: 1px solid #2a2212; color: #e2e8f0; border-radius: 8px; box-sizing: border-box; resize: none; font-size: 11px; text-align: right; }
        textarea:focus { border-color: #f59e0b; outline: none; }
        .btn-save-msg { width: 100%; padding: 8px; margin-top: 5px; background: linear-gradient(135deg, #d97706, #b45309); color: white; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; font-size: 12px; }

        .log-box { background: #030304; border: 1px solid #221a0d; border-radius: 8px; padding: 8px; height: 110px; overflow-y: auto; text-align: right; font-size: 11px; color: #94a3b8; margin-top: 4px; }
        .log-box a { color: #38bdf8; text-decoration: underline; }
        .log-title { color: #f59e0b; font-size: 12px; margin-top: 10px; text-align: right; font-weight: bold; }
    </style>
</head>
<body>
    <div class="card">
        <div class="avatar-box">
            <img src="data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAAkGBxMTEhUTExMWFRUXGBcaGBgYGBoYGBoXFRUXFxcXGBUYHSggGBolHRUVITEhJSkrLi4uGB8zODMtNygtLisBCgoKDg0OGxAQGy0lICUtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLf/AABEIAOEA4QMBIgACEQEDEQH/xAAcAAABBQEBAQAAAAAAAAAAAAAFAAIDBAYHAQj/xAA/EAABAwIEAwUEBwYGAwEBAAABAgMRAAQFEiExBkETIlFhcYEHkaGxFBVCYnKCkuHxM1OSssHwFRcjNEOCov/EABoBAAMBAQEBAAAAAAAAAAAAAAECAwAEBQb/xAAqEQACAgICAQQCAwADAQAAAAAAAQIRAyESMQQiQVEFE2EycZEUI4FCUv/aAAwDAQACEQMRAD8AvkYONz/8AcD9tK5K0y0hISlIJG0AH5zXQJtD+8Z/Cj5zXU90K2jQfD51wU3pI9RUV0j+uC02lU8a/H9qT66Qo+9r8f2r446g482pSlp2lKh27Cvzqj8x5+6L3v9v60nI6Y/kH10hX4z+/7V8frpCjxP8j9q7r9/rQ+Iq8q+t+08eX3K40UoOISdpcQkkbHJI3/AGqKqVf/AKR0+z5/u4r+kY0v+x1/s8aT/Y6/2eNXj0qB/Q8aP2OuP7PGj0p6X6WkK/scWkK/s9b06D/E/8j0p+X+Nq12O1/5B8yvVv6Uf6H+L319T0f8Al/i99a9b0X636P6X//2Q==" alt="Avatar">
        </div>
        <h1>لوحة تحكم التكتات</h1>
        <div class="user-tag">أهلاً بك، {{ username }}</div>
        
        <div class="speed-badge">تم استلام: <b>{{ count }}/3</b> تكتات | السرعة: <b>{{ speed }}ث</b></div>
        
        <form action="/toggle" method="post">
            {% if running %}
                <button type="submit" class="btn btn-stop">إيقاف بوتك 🛑</button>
            {% else %}
                <button type="submit" class="btn btn-start">تشغيل البوت 🚀</button>
            {% endif %}
        </form>

        <form action="/speed/up" method="post">
            <button type="submit" class="btn-speed-up">⚡ زيادة سرعة الرد</button>
        </form>
        
        <form action="/speed/down" method="post">
            <button type="submit" class="btn-speed-down">⏳ تخفيف سرعة الرد (أمان أكثر)</button>
        </form>

        <div class="msg-section">
            <div class="msg-title">رسالة التكت الخاصة بك:</div>
            <form action="/update_msg" method="post">
                <textarea name="custom_msg">{{ message }}</textarea>
                <button type="submit" class="btn-save-msg">حفظ الرسالة 💾</button>
            </form>
        </div>

        <div class="log-title">سجل التكتات المحلية:</div>
        <div class="log-box">
            {% for item in logs %}
                <div>• {{ item | safe }}</div>
            {% else %}
                <div style="color: #444; text-align: center; margin-top: 20px;">لا توجد تكتات مستلمة بعد...</div>
            {% endfor %}
        </div>
        
        <a href="/logout" style="color: #ef4444; font-size: 11px; display: block; margin-top: 15px; text-decoration: none;">تسجيل خروج</a>
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
    <title>تسجيل الدخول الملكي</title>
    <style>
        body { background-color: #050505; color: #ffffff; font-family: Tahoma, sans-serif; text-align: center; margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; height: 100vh; }
        .login-card { background: linear-gradient(180deg, #101012, #070708); width: 340px; padding: 25px; border-radius: 16px; border: 1px solid #2a2212; box-shadow: 0 20px 40px rgba(0,0,0,0.95), 0 0 25px rgba(245, 158, 11, 0.08); }
        .avatar-box img { width: 85px; height: 85px; border-radius: 50%; border: 2px solid #f59e0b; box-shadow: 0 0 20px rgba(245, 158, 11, 0.4); object-fit: cover; margin-bottom: 10px; }
        h2 { color: #f59e0b; margin-bottom: 15px; font-size: 18px; }
        input { width: 100%; padding: 11px; margin: 8px 0; background: #08080a; border: 1px solid #2a2212; color: white; border-radius: 8px; box-sizing: border-box; text-align: center; }
        input:focus { border-color: #f59e0b; outline: none; }
        .btn { width: 100%; padding: 11px; margin-top: 12px; background: linear-gradient(135deg, #d97706, #b45309); color: white; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; }
        .error { color: #ef4444; font-size: 11px; margin-top: 8px; }
    </style>
</head>
<body>
    <div class="login-card">
        <div class="avatar-box">
            <img src="data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAAkGBxMTEhUTExMWFRUXGBcaGBgYGBoYGBoXFRUXFxcXGBUYHSggGBolHRUVITEhJSkrLi4uGB8zODMtNygtLisBCgoKDg0OGxAQGy0lICUtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLf/AABEIAOEA4QMBIgACEQEDEQH/xAAcAAABBQEBAQAAAAAAAAAAAAAFAAIDBAYHAQj/xAA/EAABAwIEAwUEBwYGAwEBAAABAgMRAAQFEiExBkETIlFhcYEHkaGxFBVCYnKCkuHxM1OSssHwFRcjNEOCov/EABoBAAMBAQEBAAAAAAAAAAAAAAECAwAEBQb/xAAqEQACAgICAQQCAwADAQAAAAAAAQIRAyESMQQiQVEFE2EycZEUI4FCUv/aAAwDAQACEQMRAD8AvkYONz/8AcD9tK5K0y0hISlIJG0AH5zXQJtD+8Z/Cj5zXU90K2jQfD51wU3pI9RUV0j+uC02lU8a/H9qT66Qo+9r8f2r446g482pSlp2lKh27Cvzqj8x5+6L3v9v60nI6Y/kH10hX4z+/7V8frpCjxP8j9q7r9/rQ+Iq8q+t+08eX3K40UoOISdpcQkkbHJI3/AGqKqVf/AKR0+z5/u4r+kY0v+x1/s8aT/Y6/2eNXj0qB/Q8aP2OuP7PGj0p6X6WkK/scWkK/s9b06D/E/8j0p+X+Nq12O1/5B8yvVv6Uf6H+L319T0f8Al/i99a9b0X636P6X//2Q==" alt="Avatar">
        </div>
        <h2>تسجيل الدخول الملكي</h2>
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
        .card { background: linear-gradient(180deg, #101012, #070708); width: 360px; padding: 25px; border-radius: 16px; border: 1px solid #2a2212; box-shadow: 0 20px 40px rgba(0,0,0,0.95); }
        .avatar-box img { width: 85px; height: 85px; border-radius: 50%; border: 2px solid #f59e0b; box-shadow: 0 0 20px rgba(245, 158, 11, 0.4); object-fit: cover; margin-bottom: 10px; }
        h2 { color: #f59e0b; margin-bottom: 5px; font-size: 18px; }
        .welcome { font-size: 13px; color: #34d399; margin-bottom: 15px; font-weight: bold; }
        textarea { width: 100%; height: 75px; padding: 8px; background: #08080a; border: 1px solid #2a2212; color: white; border-radius: 8px; box-sizing: border-box; resize: none; font-size: 11px; text-align: center; }
        textarea:focus { border-color: #f59e0b; outline: none; }
        .btn { width: 100%; padding: 11px; margin-top: 12px; background: linear-gradient(135deg, #059669, #047857); color: white; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; }
    </style>
</head>
<body>
    <div class="card">
        <div class="avatar-box">
            <img src="data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAAkGBxMTEhUTExMWFRUXGBcaGBgYGBoYGBoXFRUXFxcXGBUYHSggGBolHRUVITEhJSkrLi4uGB8zODMtNygtLisBCgoKDg0OGxAQGy0lICUtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLf/AABEIAOEA4QMBIgACEQEDEQH/xAAcAAABBQEBAQAAAAAAAAAAAAAFAAIDBAYHAQj/xAA/EAABAwIEAwUEBwYGAwEBAAABAgMRAAQFEiExBkETIlFhcYEHkaGxFBVCYnKCkuHxM1OSssHwFRcjNEOCov/EABoBAAMBAQEBAAAAAAAAAAAAAAECAwAEBQb/xAAqEQACAgICAQQCAwADAQAAAAAAAQIRAyESMQQiQVEFE2EycZEUI4FCUv/aAAwDAQACEQMRAD8AvkYONz/8AcD9tK5K0y0hISlIJG0AH5zXQJtD+8Z/Cj5zXU90K2jQfD51wU3pI9RUV0j+uC02lU8a/H9qT66Qo+9r8f2r446g482pSlp2lKh27Cvzqj8x5+6L3v9v60nI6Y/kH10hX4z+/7V8frpCjxP8j9q7r9/rQ+Iq8q+t+08eX3K40UoOISdpcQkkbHJI3/AGqKqVf/AKR0+z5/u4r+kY0v+x1/s8aT/Y6/2eNXj0qB/Q8aP2OuP7PGj0p6X6WkK/scWkK/s9b06D/E/8j0p+X+Nq12O1/5B8yvVv6Uf6H+L319T0f8Al/i99a9b0X636P6X//2Q==" alt="Avatar">
        </div>
        <h2>ربط الحساب</h2>
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
        logs=user_data["logs"],
        count=user_data["count"]
    )

@app.route('/toggle', methods=['POST'])
def toggle():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    username = session['user']
    user_data = user_sessions[username]
    
    if not user_data["running"]:
        if user_data["token"]:
            if user_data["count"] >= MAX_TICKETS:
                user_data["count"] = 0
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
