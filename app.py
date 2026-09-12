import json
import re
import time
import requests
import websocket
import threading
import random
import os
from flask import Flask, render_template_string, request, redirect, url_for, session, send_file
from datetime import datetime

app = Flask(__name__)
app.secret_key = "marshall_elite_secure_core_v99_secret"

# قائمة الحسابات المعتمدة وكلمات المرور الخاصة بها
USERS = {
    "مرشال": "oopp00998",
    "سيف": "oopp00998",
    "Kara": "oopp00998"
}

SERVER_ID = "1272600775331414159"
API = "https://discord.com/api/v9/channels"
DEFAULT_ALERT_CHANNEL = "1545711547169513483"

STEALTH_DEVICE_PROFILES = [
    {
        "User-Agent": "Discord/188215 CFNetwork/1498.700.2 Darwin/23.4.0",
        "X-Super-Properties": "eyJvcyI6ImlPUyIsImJyb3dzZXIiOiJEaXNjb3JkIENsaWVudCIsImRldmljZSI6ImlQaG9uZSAxMywgcHJvLCBtYXgiLCJzeXN0ZW1fdmVyc2lvbiI6IjE3LjUif="
    },
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Discord/0.0.309",
        "X-Super-Properties": "eyJvcyI6IldpbmRvd3MiLCJicm93c2VyIjoiRGlzY29yZCBDbGllbnQiLCJkZXZpY2UiOiJEZXNrdG9wIiwic3lzdGVtX3ZlcnNpb24iOiIxMC4wLjE5MDQyIn="
    }
]

# إعداد الجلسات مع مكان مخصص لكل تكن الخاص بالحساب
user_sessions = {
    "مرشال": {
        "running": False, "speed": 0.1, "thread": None, "token": "",
        "message": "أهلاً بك، معك مرشال الإدارة العليا. كيف يمكنني مساعدتك؟",
        "logs": [], "count": 0, "total_lifetime": 0, "max_tickets": 20, 
        "rate_limit_errors": 0, "banned_secure": False, "last_sent_text": "", "last_sent_time": 0
    },
    "سيف": {
        "running": False, "speed": 0.1, "thread": None, "token": "",
        "message": "أهلاً بك، معك سيف الإدارة العليا. كيف يمكنني مساعدتك؟",
        "logs": [], "count": 0, "total_lifetime": 0, "max_tickets": 20, 
        "rate_limit_errors": 0, "banned_secure": False, "last_sent_text": "", "last_sent_time": 0
    },
    "Kara": {
        "running": False, "speed": 0.1, "thread": None, "token": "",
        "message": "أهلاً بك، معك Kara الإدارة العليا. كيف يمكنني مساعدتك؟",
        "logs": [], "count": 0, "total_lifetime": 0, "max_tickets": 20, 
        "rate_limit_errors": 0, "banned_secure": False, "last_sent_text": "", "last_sent_time": 0
    }
}

master_global_audit = []
security_audit_logs = []
active_tickets = set()
state_lock = threading.Lock()
request_counts = {}

@app.before_request
def security_waf():
    ip = request.remote_addr
    now = time.time()
    if ip not in request_counts:
        request_counts[ip] = []
    request_counts[ip] = [t for t in request_counts[ip] if now - t < 10]
    request_counts[ip].append(now)
    if len(request_counts[ip]) > 40:
        return "Access Denied: Rate Limit Exceeded (WAF Protected)", 429

def get_secure_headers(token):
    profile = random.choice(STEALTH_DEVICE_PROFILES)
    return {
        "Authorization": token.strip(),
        "Content-Type": "application/json",
        "User-Agent": profile["User-Agent"],
        "X-Super-Properties": profile["X-Super-Properties"],
        "X-Discord-Locale": "ar",
        "Accept-Language": "ar,en-US;q=0.9,en;q=0.8"
    }

def safe_post(token, url, payload, current_speed, username=None):
    try:
        headers = get_secure_headers(token)
        time.sleep(current_speed)
        res = requests.post(url, json=payload, headers=headers, timeout=5)
        if res.status_code == 429:
            if username and username in user_sessions:
                with state_lock:
                    user_sessions[username]["rate_limit_errors"] += 1
                    if user_sessions[username]["rate_limit_errors"] >= 5:
                        user_sessions[username]["running"] = False
                        user_sessions[username]["banned_secure"] = True
                        security_audit_logs.insert(0, f"⚠️ جدار الحماية: تم تجميد الحساب <b>{username}</b> مؤقتاً لتفادي الحظر.")
            retry_after = res.json().get("retry_after", current_speed + 0.5)
            time.sleep(retry_after)
            return safe_post(token, url, payload, current_speed, username)
        return res
    except Exception:
        return None

def process_ticket(username, token, ch_id, name):
    with state_lock:
        session_data = user_sessions[username]
        if not session_data["running"] or session_data["banned_secure"] or not token:
            return
        if session_data["count"] >= session_data["max_tickets"]:
            session_data["running"] = False
            return
        if ch_id in active_tickets:
            return
        active_tickets.add(ch_id)

    current_speed = session_data["speed"]
    custom_msg = session_data["message"]
    
    now_ts = time.time()
    if session_data["last_sent_text"] == custom_msg and (now_ts - session_data["last_sent_time"] < 1.0):
        custom_msg += "᠎" * random.randint(1, 2)
    
    session_data["last_sent_text"] = custom_msg
    session_data["last_sent_time"] = now_ts

    res = safe_post(token, f"{API}/{ch_id}/messages", {"content": custom_msg}, current_speed, username)
    
    with state_lock:
        if res and res.status_code in [200, 201]:
            ticket_url = f"https://discord.com/channels/{SERVER_ID}/{ch_id}"
            log_text = f"✨ تم استلام تكت **#{name}** | <a href='{ticket_url}' target='_blank'>رابط مباشر</a>"
            
            audit_entry = f"[{username}] استلم تكت <b>#{name}</b> في {datetime.now().strftime('%H:%M:%S')}"
            master_global_audit.insert(0, audit_entry)
            
            session_data["count"] += 1
            session_data["total_lifetime"] += 1
            session_data["logs"].append(f"{log_text} (العدد: {session_data['count']})")
        else:
            session_data["logs"].append(f"❌ تعذر استلام التكت #{name}")
            
    with state_lock:
        if ch_id in active_tickets:
            active_tickets.remove(ch_id)

def run_discord_bot(username):
    token = user_sessions[username]["token"]
    if not token:
        user_sessions[username]["logs"].append("❌ الخطأ: لم يتم إدخال توكن الحساب!")
        user_sessions[username]["running"] = False
        return

    user_sessions[username]["logs"].append("🚀 [Elite System] تم تشغيل درع الحماية والاتصال بنجاح...")

    def on_message(ws, msg):
        if not user_sessions[username]["running"] or user_sessions[username]["banned_secure"]:
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
                    ch_id = d.get("id")
                    threading.Thread(target=process_ticket, args=(username, token, ch_id, name)).start()
        except Exception:
            pass

    def on_open(ws):
        ws.send(json.dumps({
            "op": 2,
            "d": {
                "token": token,
                "properties": {"os": "Windows", "browser": "Discord Client", "device": "Desktop"},
                "intents": 1 << 0
            }
        }))

    while user_sessions[username]["running"] and not user_sessions[username]["banned_secure"]:
        try:
            ws = websocket.WebSocketApp("wss://gateway.discord.gg/?v=9&encoding=json", on_open=on_open, on_message=on_message)
            ws.run_forever()
        except Exception:
            time.sleep(2)

PANEL_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>لوحة التحكم الفاخرة - تم التطوير بواسطة مرشال</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap');
        body { background: #050505; color: #f1f5f9; font-family: 'Cairo', sans-serif; text-align: center; margin: 0; padding: 10px; }
        .card { background: #0c0c0e; max-width: 420px; margin: 0 auto; padding: 20px; border-radius: 16px; border: 1px solid #1f1f2e; box-shadow: 0 10px 30px rgba(0,0,0,0.9), 0 0 20px rgba(0, 255, 204, 0.05); }
        .dev-tag { color: #00ffcc; font-size: 11px; font-weight: 700; background: #121218; padding: 5px 10px; border-radius: 8px; border: 1px solid #1f2937; margin-bottom: 12px; display: inline-block; }
        h1 { color: #ffffff; font-size: 18px; margin: 5px 0; font-weight: 900; }
        .badge { background: #121218; border: 1px solid #1f1f2e; padding: 8px; border-radius: 8px; font-size: 11px; color: #94a3b8; margin: 8px 0; }
        .badge b { color: #00ffcc; }
        .btn { display: block; width: 100%; padding: 11px; margin: 6px 0; font-size: 13px; font-weight: 700; border: none; border-radius: 9px; cursor: pointer; text-decoration: none; font-family: 'Cairo', sans-serif; transition: 0.2s; }
        .btn:hover { filter: brightness(1.15); }
        .btn-start { background: linear-gradient(135deg, #059669, #047857); color: #fff; }
        .btn-stop { background: linear-gradient(135deg, #dc2626, #b91c1c); color: #fff; }
        .btn-report { background: linear-gradient(135deg, #2563eb, #1d4ed8); color: #fff; }
        .config-box { text-align: right; background: #121218; padding: 10px; border-radius: 10px; border: 1px solid #1f1f2e; margin-top: 10px; }
        input, textarea { width: 100%; padding: 8px; background: #050505; border: 1px solid #1f1f2e; color: #fff; border-radius: 8px; box-sizing: border-box; font-size: 11px; text-align: center; outline: none; margin-bottom: 6px; font-family: 'Cairo', sans-serif; }
        textarea { height: 50px; text-align: right; resize: none; }
        .log-box { background: #050505; border: 1px solid #1f1f2e; border-radius: 8px; padding: 8px; height: 90px; overflow-y: auto; text-align: right; font-size: 10px; color: #94a3b8; margin-top: 5px; }
        .log-box a { color: #00ffcc; text-decoration: underline; }
    </style>
</head>
<body>
    <div class="card">
        <div class="dev-tag">⚡ تم التطوير بواسطة مرشال</div>
        <h1>لوحة التحكم الأمنية</h1>
        <div style="color: #38bdf8; font-size: 12px; margin-bottom: 10px;">الحساب الحالي: {{ username }}</div>
        
        <div class="badge">الإنجاز: <b>{{ count }}/{{ max_tickets }}</b> | السرعة الحالية: <b>{{ speed }}ث</b></div>
        
        <form action="/toggle" method="post">
            {% if running %}
                <button type="submit" class="btn btn-stop">إيقاف النظام 🛑</button>
            {% else %}
                <button type="submit" class="btn btn-start">تشغيل النظام 🚀</button>
            {% endif %}
        </form>

        <form action="/download_report" method="post">
            <button type="submit" class="btn btn-report">📥 تحميل تقارير العمليات (ملف PC)</button>
        </form>

        <div class="config-box">
            <form action="/update_settings" method="post">
                <div style="color: #00ffcc; font-size: 10px; margin-bottom: 3px;">توكن الحساب (Token):</div>
                <input type="password" name="token" value="{{ token }}" placeholder="ضع توكن الحساب هنا">

                <div style="color: #00ffcc; font-size: 10px; margin-bottom: 3px;">السرعة الفائقة (حتى 0.01):</div>
                <input type="number" step="0.01" name="custom_speed" value="{{ speed }}" min="0.01" max="5.0">
                
                <div style="color: #00ffcc; font-size: 10px; margin-bottom: 3px;">الرسالة التلقائية:</div>
                <textarea name="custom_msg">{{ message }}</textarea>
                
                <button type="submit" style="width:100%; padding:8px; background:#d97706; color:#fff; border:none; border-radius:8px; font-weight:700; cursor:pointer; font-family:'Cairo',sans-serif;">حفظ الإعدادات 💾</button>
            </form>
        </div>

        <div style="color: #00ffcc; font-size: 11px; margin-top: 10px; text-align: right; font-weight: 700;">سجل العمليات المباشر:</div>
        <div class="log-box">
            {% for item in logs %}<div>• {{ item | safe }}</div>{% else %}<div style="color: #444; text-align: center; margin-top: 25px;">النظام بانتظار التكتات...</div>{% endfor %}
        </div>
        
        <a href="/logout" style="color: #f43f5e; font-size: 11px; display: block; margin-top: 12px; text-decoration: none; font-weight: 700;">تسجيل خروج 🚪</a>
    </div>
</body>
</html>
"""

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>تسجيل الدخول الآمن - تم التطوير بواسطة مرشال</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;900&display=swap');
        body { background: #050505; color: #fff; font-family: 'Cairo', sans-serif; text-align: center; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: #0c0c0e; width: 340px; padding: 25px; border-radius: 18px; border: 1px solid #1f1f2e; box-shadow: 0 15px 35px rgba(0,0,0,0.9); }
        input { width: 100%; padding: 11px; margin: 8px 0; background: #050505; border: 1px solid #1f1f2e; color: #fff; border-radius: 9px; text-align: center; outline: none; font-size: 12px; font-family: 'Cairo', sans-serif; }
        .btn { width: 100%; padding: 12px; margin-top: 10px; background: linear-gradient(135deg, #2563eb, #1d4ed8); color: #fff; border: none; border-radius: 9px; font-weight: 700; cursor: pointer; font-size: 13px; font-family: 'Cairo', sans-serif; }
    </style>
</head>
<body>
    <div class="card">
        <div style="color: #00ffcc; font-size: 11px; font-weight: 700; margin-bottom: 10px;">⚡ تم التطوير بواسطة مرشال</div>
        <h2 style="font-size: 16px; margin: 0 0 15px 0;">بوابة الدخول الآمنة</h2>
        <form method="POST">
            <input type="text" name="username" placeholder="اسم المستخدم (مرشال / سيف / Kara)" required>
            <input type="password" name="password" placeholder="كلمة المرور" required>
            <button type="submit" class="btn">دخول 🚀</button>
        </form>
    </div>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username in USERS and USERS[username] == password:
            session['user'] = username
            return redirect(url_for('panel'))
    return render_template_string(LOGIN_HTML)

@app.route('/panel')
def panel():
    if 'user' not in session: return redirect(url_for('login'))
    usr = session['user']
    data = user_sessions[usr]
    return render_template_string(
        PANEL_HTML, username=usr, running=data["running"], speed=data["speed"], 
        message=data["message"], logs=data["logs"], count=data["count"], max_tickets=data["max_tickets"], token=data["token"]
    )

@app.route('/toggle', methods=['POST'])
def toggle():
    if 'user' in session:
        usr = session['user']
        data = user_sessions[usr]
        if not data["running"] and not data["banned_secure"]:
            data["running"] = True
            threading.Thread(target=run_discord_bot, args=(usr,), daemon=True).start()
        else:
            data["running"] = False
    return redirect(url_for('panel'))

@app.route('/download_report', methods=['POST'])
def download_report():
    if 'user' not in session: return redirect(url_for('login'))
    usr = session['user']
    data = user_sessions[usr]
    
    report_content = f"--- تقرير عمليات نظام مرشال ---\nالحساب: {usr}\nالتاريخ: {datetime.now()}\nإجمالي العمليات: {data['total_lifetime']}\n\nالسجلات:\n" + "\n".join(data["logs"])
    file_path = f"report_{usr}.txt"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(report_content)
        
    return send_file(file_path, as_attachment=True)

@app.route('/update_settings', methods=['POST'])
def update_settings():
    if 'user' in session:
        usr = session['user']
        new_msg = request.form.get('custom_msg', '').strip()
        new_token = request.form.get('token', '').strip()
        try:
            new_speed = float(request.form.get('custom_speed', 0.1))
            if new_speed > 0: user_sessions[usr]["speed"] = round(new_speed, 2)
        except ValueError:
            pass
        if new_msg: user_sessions[usr]["message"] = new_msg
        if new_token: user_sessions[usr]["token"] = new_token
    return redirect(url_for('panel'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
