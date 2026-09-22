import json
import re
import time
import requests
import websocket
import threading
import random
import os
import base64
import sqlite3
from flask import Flask, render_template_string, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "saif_elite_system_core_v24_secure_key"

USERS = {
    "Saif": "12345678",
    "Marshall": "oopp0099",
    "Youssef": "oopp009987",
    "Kara": "oopp00998",
       "isso": "12345678",
    "Azmy": "12345678"

}

SERVER_ID = "1272600775331414159"
API = "https://discord.com/api/v9/channels"
SAIF_ALERT_CHANNEL = "1545711547169513483"
ADMIN_CATEGORY_ID = "1353444395575414844"

user_sessions = {
    u: {
        "running": False, "speed": 1.5, "thread": None, "token": "", "proxy": "",
        "message": f"أهلاً بك، معك {u} الإدارة العليا. كيف يمكنني مساعدتك؟",
        "reply_template": "default", "ticket_filter": "administrative" if u == "isso" else "all",
        "logs": [], "count": 0, "total_lifetime": 0, "max_tickets": 10, 
        "cooldown_mode": False, "skip_next": False, "silent_mode": False, 
        "rate_limit_errors": 0, "banned_secure": False, "last_sent_text": "", "last_sent_time": 0
    } for u in USERS.keys()
}

active_tickets = set()
state_lock = threading.Lock()
db_lock = threading.Lock()

# --- إعداد قاعدة البيانات الدائمة ---
def init_db():
    with db_lock:
        conn = sqlite3.connect('elite_system.db', check_same_thread=False)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (username TEXT PRIMARY KEY, token TEXT, proxy TEXT, message TEXT, 
                      reply_template TEXT, ticket_filter TEXT, speed REAL, max_tickets INTEGER,
                      count INTEGER, total_lifetime INTEGER)''')
        
        for u in USERS.keys():
            c.execute("SELECT username FROM users WHERE username=?", (u,))
            if not c.fetchone():
                filter_val = "administrative" if u == "isso" else "all"
                c.execute('''INSERT INTO users (username, token, proxy, message, reply_template, ticket_filter, speed, max_tickets, count, total_lifetime)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                             (u, "", "", user_sessions[u]["message"], "default", filter_val, 1.5, 10, 0, 0))
        conn.commit()
        conn.close()

def load_db():
    with db_lock:
        conn = sqlite3.connect('elite_system.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT * FROM users")
        rows = c.fetchall()
        conn.close()
        for r in rows:
            uname = r[0]
            if uname in user_sessions:
                user_sessions[uname]["token"] = r[1]
                user_sessions[uname]["proxy"] = r[2]
                user_sessions[uname]["message"] = r[3]
                user_sessions[uname]["reply_template"] = r[4]
                user_sessions[uname]["ticket_filter"] = r[5]
                user_sessions[uname]["speed"] = r[6]
                user_sessions[uname]["max_tickets"] = r[7]
                user_sessions[uname]["count"] = r[8]
                user_sessions[uname]["total_lifetime"] = r[9]

def save_db(uname):
    with db_lock:
        conn = sqlite3.connect('elite_system.db', check_same_thread=False)
        c = conn.cursor()
        d = user_sessions[uname]
        c.execute('''UPDATE users SET token=?, proxy=?, message=?, reply_template=?, ticket_filter=?, 
                     speed=?, max_tickets=?, count=?, total_lifetime=? WHERE username=?''',
                  (d["token"], d.get("proxy",""), d["message"], d["reply_template"], d["ticket_filter"],
                   d["speed"], d["max_tickets"], d["count"], d["total_lifetime"], uname))
        conn.commit()
        conn.close()

# تهيئة قاعدة البيانات عند تشغيل الملف (الحل لخطأ Render)
init_db()
load_db()

REPLY_TEMPLATES = {
    "default": "", 
    "evidence_req": "عزيزي، الشكاوي التي تتطلب دلائل يجب إرفاق مقطع فيديو يوضح كافة التفاصيل مع إظهار الهوية.\n-# **نحن بانتظار استكمال المتطلبات.**",
    "review_wait": "أهلاً بك، جاري مراجعة طلبك بكل دقة. نرجو التحلي بالصبر.\n\n-# **فريق الإدارة في خدمتكم**",
    "ban_evidence": "نرجو الانتظار قليلاً ريثما يتم جلب تفاصيل التوثيق والأدلة الخاصة بالخادم."
}

def get_secure_headers(token):
    build_num = random.randint(320000, 325000)
    props = {"os": "iOS", "browser": "Discord Client", "device": "iPhone 13, pro, max", "system_version": "17.5", "client_build_number": build_num, "client_version": "241.0"}
    b64_props = base64.b64encode(json.dumps(props).encode()).decode()
    return {
        "Authorization": token.strip(), "Content-Type": "application/json",
        "User-Agent": "Discord/241.0 CFNetwork/1498.700.2 Darwin/23.4.0",
        "X-Super-Properties": b64_props, "X-Discord-Locale": "ar", "Accept-Language": "ar,en-US;q=0.9,en;q=0.8"
    }

def check_token_health(token):
    if not token: return "❌ التوكن فارغ غير مدخل"
    try:
        res = requests.get("https://discord.com/api/v9/users/@me", headers=get_secure_headers(token), timeout=5)
        if res.status_code == 200:
            return f"✅ التوكن سليم وشغال تمام ({res.json().get('username')}#{res.json().get('discriminator', '0')})"
        elif res.status_code == 401: return "❌ التوكن غير صالح أو منتهي الصلاحية (401)"
        else: return f"⚠️ استجابة غير متوقعة من الديسكورد (كود: {res.status_code})"
    except Exception as e: return f"❌ خطأ في الاتصال بالشبكة فحص التوكن: {str(e)}"

def send_typing_bg(token, ch_id):
    try: requests.post(f"{API}/{ch_id}/typing", headers=get_secure_headers(token), timeout=2)
    except: pass

def safe_post(token, url, payload, current_speed, username=None):
    try:
        headers = get_secure_headers(token)
        
        if "messages" in url and "typing" not in url:
            ch_id = url.split("/channels/")[1].split("/")[0]
            threading.Thread(target=send_typing_bg, args=(token, ch_id)).start()
            
        time.sleep(current_speed)
        res = requests.post(url, json=payload, headers=headers, timeout=5)
        
        remaining = int(res.headers.get('X-RateLimit-Remaining', 5))
        if remaining <= 1 and res.status_code != 429:
            reset_after = float(res.headers.get('X-RateLimit-Reset-After', 1.0))
            if username: user_sessions[username]["logs"].append(f"🛡️ [الدرع الذكي] توقف استباقي لـ {reset_after}ث لتجنب الكتم.")
            time.sleep(reset_after + 0.1)
            
        if res.status_code == 429:
            if username:
                with state_lock:
                    user_sessions[username]["rate_limit_errors"] += 1
                    if user_sessions[username]["rate_limit_errors"] >= 3:
                        user_sessions[username]["running"] = False
                        user_sessions[username]["banned_secure"] = True
                        user_sessions[username]["logs"].append("🚨 [Elite Shield] تم تجميد الحساب مؤقتاً لتفادي الباند النهائي.")
            retry_after = res.json().get("retry_after", current_speed + 1.0)
            time.sleep(retry_after + 0.1)
            return safe_post(token, url, payload, current_speed, username)
        return res
    except Exception: return None

def process_ticket(username, token, ch_id, name, parent_id):
    with state_lock:
        session_data = user_sessions[username]
        if not session_data["running"] or session_data["banned_secure"]: return
            
        if session_data.get("ticket_filter", "all") == "administrative":
            if str(parent_id) != ADMIN_CATEGORY_ID: return

        if session_data["cooldown_mode"]:
            if session_data["skip_next"]:
                session_data["skip_next"] = False
                session_data["logs"].append(f"⚡ [Cooldown] تم تخطي التكت `#{name}`.")
                return
            else:
                session_data["skip_next"] = True

        if session_data["count"] >= session_data["max_tickets"]:
            session_data["running"] = False
            return
        if ch_id in active_tickets: return
        active_tickets.add(ch_id)

    current_speed = session_data["speed"]
    tpl_key = session_data.get("reply_template", "default")
    custom_msg = REPLY_TEMPLATES[tpl_key] if tpl_key != "default" and tpl_key in REPLY_TEMPLATES else session_data["message"]
    
    now_ts = time.time()
    if session_data["last_sent_text"] == custom_msg and (now_ts - session_data["last_sent_time"] < 2.0):
        custom_msg += "᠎" * random.randint(1, 2)
    session_data["last_sent_text"] = custom_msg
    session_data["last_sent_time"] = now_ts

    res = safe_post(token, f"{API}/{ch_id}/messages", {"content": custom_msg}, current_speed, username)
    
    with state_lock:
        if res and res.status_code in [200, 201]:
            ticket_url = f"https://discord.com/channels/{SERVER_ID}/{ch_id}"
            log_text = f"✨ تم استلام تكت بنجاح **#{name}** | <a href='{ticket_url}' target='_blank'>الرابط</a>"

            if username == "Saif":
                alert_payload = {"content": f"💎 **إشعار الإدارة - النظام المتقدم** 💎\n\nقام الإداري **سيف** باستلام تذكرة جديدة ✅\n\n🎫 **اسم التذكرة:** `#{name}`\n🔗 **رابط التذكرة:** {ticket_url}\n⚡ **الحالة:** تم الرد وإرسال القالب."}
                safe_post(token, f"{API}/{SAIF_ALERT_CHANNEL}/messages", alert_payload, 0.5, username)

            if session_data["count"] < session_data["max_tickets"]:
                session_data["count"] += 1
                session_data["total_lifetime"] += 1
                session_data["logs"].append(f"{log_text} ({session_data['count']}/{session_data['max_tickets']})")
                save_db(username)
                if session_data["count"] >= session_data["max_tickets"]:
                    session_data["running"] = False
                    session_data["logs"].append("🛑 تم بلوغ الحد الأقصى، توقف النظام.")
        else:
            session_data["logs"].append(f"<span style='color: #ef4444;'>❌ تعذر استلام #{name}</span>")
    with state_lock:
        if ch_id in active_tickets: active_tickets.remove(ch_id)

def run_discord_bot(username):
    token = user_sessions[username]["token"]
    user_sessions[username]["logs"].append("🚀 تم تفعيل النظام بأقصى سرعة وقاعدة بيانات آمنة...")
    
    def on_message(ws, msg):
        if not user_sessions[username]["running"] or user_sessions[username]["banned_secure"]:
            ws.close()
            return
        try:
            raw = json.loads(msg)
            if raw.get("op") == 10: ws.send(json.dumps({"op": 1, "d": None}))
            if raw.get("t") == "CHANNEL_CREATE":
                d = raw.get("d", {})
                if d.get("guild_id") == SERVER_ID and d.get("type") == 0:
                    name = d.get("name", "").lower()
                    ch_id = d.get("id")
                    parent_id = d.get("parent_id", "")
                    if time.time() - (((int(ch_id) >> 22) + 1420070400000) / 1000.0) > 90: return
                    with state_lock:
                        if user_sessions[username]["count"] >= user_sessions[username]["max_tickets"] or not user_sessions[username]["running"]: return
                    threading.Thread(target=process_ticket, args=(username, token, ch_id, name, parent_id)).start()
        except Exception: pass

    def on_open(ws):
        ws.send(json.dumps({"op": 2, "d": {"token": token, "properties": {"os": "iOS", "browser": "Discord Client", "device": "iPhone"}, "intents": 1 << 0}}))

    while user_sessions[username]["running"] and not user_sessions[username]["banned_secure"]:
        try:
            ws = websocket.WebSocketApp("wss://gateway.discord.gg/?v=9&encoding=json", on_open=on_open, on_message=on_message)
            ws.run_forever()
        except: time.sleep(2)

PANEL_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>لوحة القيادة المركزية - Lynwood Elite</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;900&display=swap');
        body { background: #0a0f1d; color: #f8fafc; font-family: 'Cairo', sans-serif; text-align: center; margin: 0; padding: 15px; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .glass-card { background: rgba(17, 24, 39, 0.85); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); max-width: 440px; width: 100%; padding: 26px; border-radius: 20px; border: 1px solid rgba(59, 130, 246, 0.2); box-shadow: 0 25px 50px rgba(0,0,0,0.9), inset 0 0 15px rgba(59, 130, 246, 0.1); }
        .logo-glow { width: 75px; height: 75px; margin: 0 auto 15px auto; background: linear-gradient(135deg, #2563eb, #1e3a8a); border-radius: 20px; display: flex; align-items: center; justify-content: center; font-size: 32px; box-shadow: 0 0 25px rgba(59, 130, 246, 0.6); border: 1px solid rgba(147, 197, 253, 0.3); }
        h1 { color: #ffffff; font-size: 22px; margin-bottom: 4px; font-weight: 900; text-shadow: 0 2px 10px rgba(0,0,0,0.5); }
        .user-tag { color: #93c5fd; font-size: 12px; margin-bottom: 16px; font-weight: 700; background: rgba(0,0,0,0.5); display: inline-block; padding: 5px 14px; border-radius: 20px; border: 1px solid rgba(59, 130, 246, 0.4); }
        
        .badge-container { display: flex; gap: 8px; margin-bottom: 15px; }
        .glass-badge { flex: 1; background: rgba(0,0,0,0.5); border: 1px solid rgba(255,255,255,0.05); padding: 10px 8px; border-radius: 12px; font-size: 11px; color: #cbd5e1; font-weight: 600; }
        .glass-badge b { color: #60a5fa; font-size: 13px; display: block; margin-top: 4px; }
        
        .chart-container { background: rgba(0,0,0,0.3); border-radius: 14px; padding: 10px; border: 1px solid rgba(255,255,255,0.05); margin-bottom: 15px; height: 130px; position: relative; }

        .btn { display: block; width: 100%; padding: 12px; margin: 8px 0; font-size: 13px; font-weight: 700; border: none; border-radius: 12px; cursor: pointer; text-decoration: none; transition: 0.3s; font-family: 'Cairo'; }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 10px 20px rgba(0,0,0,0.5); }
        .btn-start { background: linear-gradient(135deg, #059669, #047857); color: white; }
        .btn-stop { background: linear-gradient(135deg, #dc2626, #991b1b); color: white; }
        .btn-secondary { background: rgba(255,255,255,0.05); color: #cbd5e1; border: 1px solid rgba(255,255,255,0.1); }
        .btn-secondary:hover { background: rgba(255,255,255,0.1); color: #fff; }
        
        .config-section { text-align: right; margin-top: 15px; background: rgba(0,0,0,0.4); padding: 14px; border-radius: 14px; border: 1px solid rgba(255,255,255,0.05); }
        .config-title { color: #93c5fd; font-size: 11px; margin-bottom: 6px; font-weight: 700; }
        input, select, textarea { width: 100%; padding: 10px; background: rgba(0,0,0,0.6); border: 1px solid rgba(255,255,255,0.1); color: #f8fafc; border-radius: 10px; box-sizing: border-box; font-size: 11px; text-align: center; outline: none; margin-bottom: 8px; font-family: 'Cairo'; transition: 0.3s; }
        input:focus, select:focus, textarea:focus { border-color: #3b82f6; box-shadow: 0 0 15px rgba(59, 130, 246, 0.3); }
        textarea { height: 60px; text-align: right; resize: none; }
        .btn-save { background: linear-gradient(135deg, #2563eb, #1d4ed8); color: white; margin-top: 4px; }
        
        .log-box { background: rgba(0,0,0,0.7); border: 1px solid rgba(255,255,255,0.05); border-radius: 12px; padding: 10px; height: 100px; overflow-y: auto; text-align: right; font-size: 10px; color: #94a3b8; margin-top: 8px; }
        .log-box a { color: #60a5fa; font-weight: 700; }
        .logout-btn { color: #f87171; font-size: 12px; display: inline-block; margin-top: 15px; font-weight: 700; text-decoration: none; padding: 6px 16px; border-radius: 20px; background: rgba(248, 113, 113, 0.1); }
    </style>
</head>
<body>
    <div class="glass-card">
        <div class="logo-glow">🛡️</div>
        <h1>منظومة الإدارة العليا</h1>
        <div class="user-tag">الحساب النشط: {{ username }}</div>
        
        <div class="badge-container">
            <div class="glass-badge">المنجز <b>{{ count }}/{{ max_tickets }}</b></div>
            <div class="glass-badge">السرعة <b>{{ speed }}ث</b></div>
            <div class="glass-badge">التراكمي <b>{{ total_lifetime }}</b></div>
        </div>

        <div class="chart-container">
            <canvas id="progressChart"></canvas>
        </div>
        
        <form action="/toggle" method="post">
            {% if running %}
                <button type="submit" class="btn btn-stop">إيقاف النظام 🛑</button>
            {% else %}
                <button type="submit" class="btn btn-start">تشغيل النظام الآلي 🚀</button>
            {% endif %}
        </form>

        <div class="config-section">
            <form action="/update_settings" method="post">
                <div class="config-title">الحد الأقصى للتكتات:</div>
                <input type="number" name="max_tickets" value="{{ max_tickets }}" min="1" max="500">
                <div class="config-title">ضبط سرعة الاستجابة بالثواني:</div>
                <input type="number" step="0.01" name="custom_speed" value="{{ speed }}" min="0.01" max="10.0">
                <div class="config-title">نوع التكتات (فلتر):</div>
                <select name="ticket_filter">
                    <option value="all" {% if ticket_filter == 'all' %}selected{% endif %}>جميع التكتات</option>
                    <option value="administrative" {% if ticket_filter == 'administrative' %}selected{% endif %}>الشكاوى الإدارية فقط (1353444...)</option>
                </select>
                <div class="config-title">تخصيص نص الرد يدوياً:</div>
                <textarea name="custom_msg">{{ message }}</textarea>
                <button type="submit" class="btn btn-save">حفظ الإعدادات في القاعدة 💾</button>
            </form>
        </div>

        <div style="display: flex; gap: 8px; margin: 12px 0;">
            <form action="/token" method="get" style="flex:1;"><button type="submit" class="btn btn-secondary" style="margin:0;">🔑 التوكن</button></form>
            <form action="/reset_all" method="post" onsubmit="return confirm('تصفير؟');" style="flex:1;"><button type="submit" class="btn btn-secondary" style="margin:0; color: #f87171;">🗑️ تصفير</button></form>
        </div>

        <div class="log-box">
            {% for item in logs %}<div>• {{ item | safe }}</div>{% else %}<div style="text-align: center; margin-top: 25px;">النظام جاهز ومحمي بالكامل...</div>{% endfor %}
        </div>
        <a href="/logout" class="logout-btn">تسجيل خروج 🚪</a>
    </div>

    <script>
        var ctx = document.getElementById('progressChart').getContext('2d');
        var maxT = {{ max_tickets }};
        var currentT = {{ count }};
        var remaining = maxT - currentT;
        if(remaining < 0) remaining = 0;
        
        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['المنجز', 'المتبقي'],
                datasets: [{
                    data: [currentT, remaining],
                    backgroundColor: ['#3b82f6', 'rgba(255,255,255,0.05)'],
                    borderColor: ['#60a5fa', 'rgba(255,255,255,0.1)'],
                    borderWidth: 1
                }]
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, cutout: '75%' }
        });
    </script>
</body>
</html>
"""

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>تسجيل الدخول - Lynwood Elite</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap');
        body { background: #0a0f1d; color: #f8fafc; font-family: 'Cairo', sans-serif; text-align: center; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .glass-card { background: rgba(17, 24, 39, 0.85); backdrop-filter: blur(20px); width: 340px; padding: 35px 25px; border-radius: 20px; border: 1px solid rgba(59, 130, 246, 0.2); box-shadow: 0 25px 50px rgba(0,0,0,0.9); }
        .login-logo { width: 75px; height: 75px; margin: 0 auto 20px auto; background: linear-gradient(135deg, #2563eb, #1e3a8a); border-radius: 20px; display: flex; align-items: center; justify-content: center; font-size: 32px; box-shadow: 0 0 25px rgba(59, 130, 246, 0.5); }
        input { width: 100%; padding: 12px; margin: 8px 0; background: rgba(0,0,0,0.5); border: 1px solid rgba(255,255,255,0.1); color: #fff; border-radius: 10px; text-align: center; outline: none; font-size: 13px; font-family: 'Cairo'; }
        input:focus { border-color: #3b82f6; }
        .btn { width: 100%; padding: 14px; margin-top: 15px; background: linear-gradient(135deg, #2563eb, #1d4ed8); color: #fff; border: none; border-radius: 10px; font-weight: 700; cursor: pointer; font-size: 14px; font-family: 'Cairo'; }
    </style>
</head>
<body>
    <div class="glass-card">
        <div class="login-logo">🛡️</div>
        <div style="color: #60a5fa; font-size: 11px; margin-bottom: 20px; font-weight: 700;">⚡ تم التطوير بواسطة مرشال</div>
        <h2 style="margin: 0 0 20px 0; font-size: 20px; font-weight: 900;">بوابة النخبة الآمنة</h2>
        <form method="POST">
            <input type="text" name="username" placeholder="اسم المستخدم" required>
            <input type="password" name="password" placeholder="كلمة المرور" required>
            <button type="submit" class="btn">تسجيل الدخول 🚀</button>
        </form>
    </div>
</body>
</html>
"""

TOKEN_HTML = """
<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>تعديل التوكن</title>
<style>@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');body{background:#0a0f1d;color:#fff;font-family:'Cairo',sans-serif;text-align:center;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}.glass-card{background:rgba(17,24,39,0.85);backdrop-filter:blur(20px);width:340px;padding:30px;border-radius:20px;border:1px solid rgba(59,130,246,0.2)}textarea{width:100%;height:90px;background:rgba(0,0,0,0.5);border:1px solid rgba(255,255,255,0.1);color:#fff;border-radius:10px;text-align:center;resize:none;box-sizing:border-box;font-size:11px;outline:none;font-family:'Cairo';padding:12px}textarea:focus{border-color:#3b82f6}.btn{width:100%;padding:14px;margin-top:15px;background:linear-gradient(135deg,#2563eb,#1d4ed8);color:#fff;border:none;border-radius:10px;font-weight:700;cursor:pointer;font-family:'Cairo'}</style></head>
<body><div class="glass-card"><h2 style="color:#60a5fa; margin-top:0;">تحديث توكن الحساب</h2><form method="POST"><textarea name="token" placeholder="الصق التوكن..." required></textarea><button type="submit" class="btn">حفظ وتأمين 💾</button></form></div></body></html>
"""

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username in USERS and USERS[username] == password:
            session['user'] = username
            if not user_sessions[username]["token"]: return redirect(url_for('set_token'))
            return redirect(url_for('panel'))
    return render_template_string(LOGIN_HTML)

@app.route('/token', methods=['GET', 'POST'])
def set_token():
    if 'user' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        user_sessions[session['user']]["token"] = request.form.get('token').strip()
        save_db(session['user'])
        return redirect(url_for('panel'))
    return render_template_string(TOKEN_HTML)

@app.route('/panel')
def panel():
    if 'user' not in session or not user_sessions[session['user']]["token"]: return redirect(url_for('login'))
    usr = session['user']
    data = user_sessions[usr]
    return render_template_string(
        PANEL_HTML, username=usr, running=data["running"], speed=data["speed"], 
        message=data["message"], ticket_filter=data.get("ticket_filter", "all"),
        logs=data["logs"], count=data["count"], total_lifetime=data["total_lifetime"], 
        max_tickets=data["max_tickets"]
    )

@app.route('/toggle', methods=['POST'])
def toggle():
    if 'user' in session:
        usr = session['user']
        data = user_sessions[usr]
        if not data["running"] and not data["banned_secure"]:
            if data["token"]:
                if data["count"] >= data["max_tickets"]: data["count"] = 0
                data["running"] = True
                threading.Thread(target=run_discord_bot, args=(usr,), daemon=True).start()
        else: data["running"] = False
    return redirect(url_for('panel'))

@app.route('/reset_all', methods=['POST'])
def reset_all():
    if 'user' in session:
        usr = session['user']
        user_sessions[usr]["count"] = 0
        user_sessions[usr]["logs"] = []
        save_db(usr)
    return redirect(url_for('panel'))

@app.route('/update_settings', methods=['POST'])
def update_settings():
    if 'user' in session:
        usr = session['user']
        user_sessions[usr]["ticket_filter"] = request.form.get('ticket_filter', 'all')
        user_sessions[usr]["message"] = request.form.get('custom_msg', '').strip()
        try:
            new_max = int(request.form.get('max_tickets', 10))
            if new_max > 0: user_sessions[usr]["max_tickets"] = new_max
            new_speed = float(request.form.get('custom_speed', 1.5))
            if new_speed >= 0.01: user_sessions[usr]["speed"] = round(new_speed, 2)
        except ValueError: pass
        save_db(usr)
    return redirect(url_for('panel'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
