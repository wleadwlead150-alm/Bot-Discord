import json
import time
import requests
import websocket
import threading
import os
import base64
import sqlite3
import random
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "MR_ELITE_SECRET_CORE_STABLE_V101"

INITIAL_USERS = {
    "Saif": "12345678", "Marshall": "oopp0099", "Youssef": "oopp009987",
    "Kara": "oopp00998", "isso": "12345678", "Azmy": "12345678", "Dark": "123456789"
}

SERVER_ID = "1272600775331414159"
API = "https://discord.com/api/v9/channels"
SAIF_ALERT_CHANNEL = "1545711547169513483"

CATEGORY_IDS = {
    "administrative": "1353444395575414844",
    "players": "1353444390387060736",
    "factions": "1353444400679747665"
}

THEMES = {
    "cyber_red": {"name": "أحمر Cyberpunk", "prim": "#dc2626", "sec": "#7f1d1d", "bg": "#170505"},
    "lynwood": {"name": "أزرق Lynwood Police", "prim": "#2563eb", "sec": "#1e3a8a", "bg": "#0a0f1d"}
}

user_sessions = {}
db_lock = threading.Lock()

def cipher(text, encrypt=True):
    if not text: return ""
    key = app.secret_key
    if not encrypt:
        try: text = base64.b64decode(text.encode()).decode()
        except: return text
    res = "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(text))
    if encrypt: return base64.b64encode(res.encode()).decode()
    return res

def create_default_session_data(uname, pwd):
    return {
        "password": pwd, "status": "stopped", "thread": None, "token": "",
        "message": f"أهلاً بك، معك {uname} الإدارة العليا. كيف يمكنني مساعدتك؟",
        "speed": 0.5, "max_tickets": 10, "count": 0, "logs": [], 
        "active_tickets": set(), "lock": threading.Lock(), "theme": "cyber_red", "claimed_history": []
    }

def init_db():
    with db_lock:
        conn = sqlite3.connect('elite_system.db', check_same_thread=False)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, token TEXT, message TEXT, speed REAL, max_tickets INTEGER, count INTEGER, theme TEXT)''')
        for uname, pwd in INITIAL_USERS.items():
            c.execute("SELECT username FROM users WHERE username=?", (uname,))
            if not c.fetchone():
                c.execute('''INSERT INTO users (username, password, token, message, speed, max_tickets, count, theme) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (uname, pwd, "", f"أهلاً بك، معك {uname} الإدارة العليا. كيف يمكنني مساعدتك؟", 0.5, 10, 0, "cyber_red"))
        conn.commit()
        conn.close()

def load_db():
    global user_sessions
    with db_lock:
        conn = sqlite3.connect('elite_system.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT * FROM users")
        rows = c.fetchall()
        col_names = [description[0] for description in c.description]
        conn.close()
        for r in rows:
            row_dict = dict(zip(col_names, r))
            uname = row_dict["username"]
            if uname not in user_sessions:
                user_sessions[uname] = create_default_session_data(uname, row_dict.get("password", "12345678"))
            user_sessions[uname]["password"] = row_dict.get("password", "12345678")
            user_sessions[uname]["token"] = cipher(row_dict.get("token", ""), False)
            user_sessions[uname]["message"] = row_dict.get("message", "")
            user_sessions[uname]["speed"] = row_dict.get("speed", 0.5)
            user_sessions[uname]["max_tickets"] = row_dict.get("max_tickets", 10)
            user_sessions[uname]["count"] = row_dict.get("count", 0)
            user_sessions[uname]["theme"] = row_dict.get("theme", "cyber_red")

def save_db(uname):
    with db_lock:
        conn = sqlite3.connect('elite_system.db', check_same_thread=False)
        c = conn.cursor()
        d = user_sessions[uname]
        enc_token = cipher(d["token"], True)
        c.execute('''UPDATE users SET password=?, token=?, message=?, speed=?, max_tickets=?, count=?, theme=? WHERE username=?''', (d["password"], enc_token, d["message"], d["speed"], d["max_tickets"], d["count"], d.get("theme","cyber_red"), uname))
        conn.commit()
        conn.close()

init_db()
load_db()

def process_ticket(username, ch_id, name):
    session_data = user_sessions[username]
    with session_data["lock"]:
        if session_data["status"] != "running": return
        if session_data["count"] >= session_data["max_tickets"]:
            session_data["status"] = "stopped"
            return
        if ch_id in session_data["active_tickets"]: return
        session_data["active_tickets"].add(ch_id)
        session_data["count"] += 1
        current_count = session_data["count"]
        max_lim = session_data["max_tickets"]

    headers = {
        "Authorization": session_data["token"].strip(),
        "Content-Type": "application/json",
        "User-Agent": "Discord-iOS/241.0 (iPhone13,4; iOS 17.5)"
    }
    
    nonce = str(int(time.time() * 1000000)) + str(random.randint(10000, 99999))
    payload = {"content": session_data["message"], "nonce": nonce}

    res = None
    max_retries = 3 
    attempts = 0
    
    try:
        if session_data["speed"] > 0: 
            time.sleep(session_data["speed"])
            
        while attempts < max_retries:
            res = requests.post(f"{API}/{ch_id}/messages", json=payload, headers=headers, timeout=5)
            if res.status_code == 429:
                try:
                    data = res.json()
                    retry_after = float(data.get("retry_after", 1.0))
                except:
                    retry_after = 1.0
                time.sleep(retry_after + 0.1)
                attempts += 1
                continue
            elif res.status_code in [200, 201]:
                break
            else:
                break
    except:
        res = None

    with session_data["lock"]:
        if res and res.status_code in [200, 201]:
            t_time = datetime.now().strftime("%I:%M %p")
            session_data["claimed_history"].append({"id": ch_id, "name": name, "time": t_time})
            session_data["logs"].insert(0, f"✨ تم قنص تكت جديد بنجاح: **#{name}** ({current_count}/{max_lim})")
            
            if username == "Saif":
                try: 
                    requests.post(f"{API}/{SAIF_ALERT_CHANNEL}/messages", json={"content": f"💎 الإداري **{username}** استلم تذكرة ✅\n🎫 `#{name}`\n🔗 https://discord.com/channels/{SERVER_ID}/{ch_id}", "nonce": nonce}, headers=headers, timeout=3)
                except: pass
                
            save_db(username)
            if current_count >= max_lim:
                session_data["status"] = "stopped"
                session_data["logs"].insert(0, "🛑 تم بلوغ الحد الأقصى.")
        else:
            session_data["count"] -= 1
            err_code = res.status_code if res else "Connection Drop"
            session_data["logs"].insert(0, f"<span style='color: #ef4444;'>❌ تعذر استلام #{name} (خطأ: {err_code})</span>")
            
        if ch_id in session_data["active_tickets"]: session_data["active_tickets"].remove(ch_id)

def run_discord_bot(username):
    d = user_sessions[username]
    token = d["token"]
    d["logs"].insert(0, "🚀 تم تفعيل محرك الاتصال الثابت والمحصن ضد الأخطاء...")
    
    def on_message(ws, msg):
        if d["status"] == "stopped": ws.close(); return
        if d["status"] == "paused": return
        try:
            raw = json.loads(msg)
            if raw.get("op") == 10: 
                ws.send(json.dumps({"op": 1, "d": None}))
            if raw.get("t") == "CHANNEL_CREATE" and raw.get("d", {}).get("guild_id") == SERVER_ID:
                ch_id = str(raw["d"]["id"])
                name = raw["d"].get("name", "غير-معروف")
                
                parent_id = str(raw["d"].get("parent_id", ""))
                valid_categories = list(CATEGORY_IDS.values())
                if parent_id not in valid_categories:
                    return
                
                created_ts = ((int(ch_id) >> 22) + 1420070400000) / 1000.0
                if time.time() - created_ts < 15:
                    threading.Thread(target=process_ticket, args=(username, ch_id, name)).start()
        except: pass

    def on_open(ws):
        ws.send(json.dumps({
            "op": 2, 
            "d": {
                "token": token, 
                "properties": {"os": "iOS", "browser": "Discord Client", "device": "iPhone"}, 
                "intents": 1 | 512
            }
        }))

    while d["status"] in ["running", "paused"]:
        try:
            ws = websocket.WebSocketApp("wss://gateway.discord.gg/?v=9&encoding=json", on_open=on_open, on_message=on_message)
            ws.run_forever(ping_interval=30, ping_timeout=10)
        except: 
            time.sleep(2)

# ================= واجهات HTML =================

MANIFEST_JSON = """{"name": "M.R Sniper", "short_name": "Sniper", "start_url": "/login", "display": "standalone", "background_color": "#030712", "theme_color": "#ef4444"}"""

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>بوابة الدخول</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@600;800&display=swap');
        body { background: #030712; color: #fff; font-family: 'Cairo', sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: rgba(15, 23, 42, 0.8); padding: 40px; border-radius: 16px; border: 1px solid rgba(59, 130, 246, 0.2); width: 320px; text-align: center; }
        input { width: 100%; padding: 12px; margin: 10px 0; background: rgba(0,0,0,0.6); border: 1px solid #1e293b; color: #fff; border-radius: 8px; text-align: center; box-sizing: border-box; font-size: 16px;}
        button { width: 100%; padding: 12px; background: #3b82f6; color: #fff; border: none; border-radius: 8px; font-weight: 800; font-family: 'Cairo'; cursor: pointer; margin-top: 15px;}
    </style>
</head>
<body>
    <div class="card">
        <h2>تسجيل الدخول</h2>
        <form method="POST">
            <input type="text" name="username" placeholder="اسم المستخدم" required>
            <input type="password" name="password" placeholder="كلمة المرور" required>
            <button type="submit">دخول 🚀</button>
        </form>
        {% if error %}<p style="color:#ef4444; font-size:12px;">{{ error }}</p>{% endif %}
    </div>
</body>
</html>
"""

PANEL_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>M.R Command Center</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;900&display=swap');
        :root { --prim: {{ theme_data.prim }}; --sec: {{ theme_data.sec }}; --bg: {{ theme_data.bg }}; }
        body { background: var(--bg); color: #f8fafc; font-family: 'Cairo', sans-serif; text-align: center; margin: 0; padding: 15px;}
        .glass-card { background: rgba(0, 0, 0, 0.6); max-width: 440px; width: 100%; padding: 26px; border-radius: 20px; border: 1px solid rgba(255,255,255, 0.1); margin: 0 auto;}
        h1 { color: #fff; font-size: 20px; margin-bottom: 5px; font-weight: 900; }
        .user-tag { color: var(--prim); font-size: 13px; background: rgba(0,0,0,0.5); padding: 5px 15px; border-radius: 20px; border: 1px solid var(--prim); display: inline-block; margin-bottom: 15px;}
        .badge-container { display: flex; gap: 5px; margin-bottom: 15px; }
        .glass-badge { flex: 1; background: rgba(0,0,0,0.5); border: 1px solid rgba(255,255,255,0.05); padding: 8px; border-radius: 12px; font-size: 11px; }
        .glass-badge b { color: var(--prim); font-size: 13px; display: block; margin-top: 3px; }
        .action-row { display: flex; gap: 8px; margin-bottom: 15px; }
        .btn { flex: 1; padding: 12px; font-size: 14px; font-weight: 800; border: none; border-radius: 12px; cursor: pointer; font-family: 'Cairo'; color: #fff;}
        .btn-start { background: #059669; }
        .btn-pause { background: #fbbf24; color: #000;}
        .btn-stop { background: #dc2626; }
        .btn-secondary { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); width: 100%; margin-top: 5px;}
        .config-title { color: var(--prim); font-size: 12px; margin-bottom: 4px; font-weight: 700; text-align: right;}
        input, textarea { width: 100%; padding: 12px; background: rgba(0,0,0,0.6); border: 1px solid rgba(255,255,255,0.1); color: #fff; border-radius: 10px; box-sizing: border-box; font-size: 12px; margin-bottom: 10px; font-family: 'Cairo';}
        textarea { height: 60px; resize: none; }
        .log-box { background: #000; border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; padding: 10px; height: 90px; overflow-y: auto; text-align: right; font-size: 11px; color: #94a3b8; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="glass-card">
        <h1>M.R COMMAND CENTER</h1>
        <div class="user-tag">👤 {{ username }}</div>
        
        <div class="badge-container">
            <div class="glass-badge">الهدف <b id="count_disp">{{ count }}/{{ max_tickets }}</b></div>
            <div class="glass-badge">السرعة <b id="speed_disp">{{ speed }}s</b></div>
            <div class="glass-badge">الوضع <b id="status_disp" style="color: {% if status == 'running' %}#10b981{% elif status == 'paused' %}#fbbf24{% else %}#ef4444{% endif %};">
                {% if status == 'running' %}نشط 🚀{% elif status == 'paused' %}استراحة ⏸️{% else %}متوقف 🛑{% endif %}
            </b></div>
        </div>

        <form action="/set_status" method="post" class="action-row">
            {% if status == 'stopped' %}
                <button type="submit" name="new_status" value="running" class="btn btn-start">تشغيل النظام 🚀</button>
            {% else %}
                {% if status == 'running' %}<button type="submit" name="new_status" value="paused" class="btn btn-pause">استراحة ⏸</button>
                {% else %}<button type="submit" name="new_status" value="running" class="btn btn-start">استئناف ▶️</button>{% endif %}
                <button type="submit" name="new_status" value="stopped" class="btn btn-stop" style="flex: 0.5;">إيقاف 🛑</button>
            {% endif %}
        </form>

        <form action="/update_main" method="post">
            <div style="display:flex; gap:8px;">
                <div style="flex:1;"><div class="config-title">الحد الأقصى:</div><input type="number" name="max_tickets" value="{{ max_tickets }}" min="1"></div>
                <div style="flex:1;"><div class="config-title">السرعة:</div><input type="number" step="0.01" name="custom_speed" value="{{ speed }}"></div>
            </div>
            <div class="config-title">نص الرد المباشر:</div>
            <textarea name="custom_msg">{{ message }}</textarea>
            <button type="submit" class="btn btn-secondary">حفظ التغييرات السريعة 💾</button>
        </form>

        <div class="log-box" id="log_box">{% for item in logs %}<div>• {{ item | safe }}</div>{% else %}<div>النظام جاهز...</div>{% endfor %}</div>
        
        <form action="/logout" method="get" style="margin-top:15px;"><button type="submit" class="btn btn-stop" style="background:transparent; border:1px solid #ef4444; color:#ef4444;">تسجيل خروج</button></form>
    </div>

    <script>
        if ("Notification" in window && Notification.permission !== "granted") { Notification.requestPermission(); }
        let lastCount = {{ count }};

        setInterval(async () => {
            try {
                let res = await fetch('/api/status');
                let data = await res.json();
                
                if (data.count > lastCount) {
                    let newTicket = data.history[data.history.length - 1];
                    if ("Notification" in window && Notification.permission === "granted") {
                        new Notification("M.R Command Center 🚀", { body: "تم قنص تكت جديد بنجاح: #" + (newTicket ? newTicket.name : "")});
                    }
                    lastCount = data.count;
                } else if (data.count < lastCount) { lastCount = data.count; }

                document.getElementById('count_disp').innerText = data.count + '/' + data.max_tickets;
                document.getElementById('speed_disp').innerText = data.speed + 's';
                
                let sDisp = document.getElementById('status_disp');
                if(data.status === 'running') { sDisp.innerText = 'نشط 🚀'; sDisp.style.color = '#10b981'; }
                else if(data.status === 'paused') { sDisp.innerText = 'استراحة ⏸️'; sDisp.style.color = '#fbbf24'; }
                else { sDisp.innerText = 'متوقف 🛑'; sDisp.style.color = '#ef4444'; }

                let logHtml = '';
                data.logs.forEach(l => { logHtml += '<div>• ' + l + '</div>'; });
                document.getElementById('log_box').innerHTML = logHtml || '<div>النظام جاهز...</div>';
            } catch(e) {}
        }, 2000); 
    </script>
</body>
</html>
"""

@app.route('/manifest.json')
def manifest():
    return app.response_class(response=MANIFEST_JSON, mimetype='application/json')

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username in user_sessions and user_sessions[username]["password"] == password:
            session['user'] = username
            if not user_sessions[username]["token"]: return redirect(url_for('set_token'))
            return redirect(url_for('panel'))
        return render_template_string(LOGIN_HTML, error="بيانات غير صحيحة")
    return render_template_string(LOGIN_HTML)

@app.route('/token', methods=['GET', 'POST'])
def set_token():
    if 'user' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        user_sessions[session['user']]["token"] = request.form.get('token').strip()
        save_db(session['user'])
        return redirect(url_for('panel'))
    return render_template_string("""<body style="background:#030712; color:#fff; text-align:center; padding-top:100px;"><form method="POST"><textarea name="token" required style="width:300px; height:80px;"></textarea><br><button type="submit" style="padding:10px; background:#3b82f6; color:#fff; border:none; margin-top:10px;">حفظ التوكن 🔒</button></form></body>""")

@app.route('/panel')
def panel():
    if 'user' not in session or not user_sessions[session['user']]["token"]: return redirect(url_for('login'))
    usr = session['user']
    d = user_sessions[usr]
    theme_key = d.get("theme", "cyber_red")
    return render_template_string(PANEL_HTML, username=usr, max_tickets=d["max_tickets"], count=d["count"], speed=d["speed"], message=d["message"], theme=theme_key, theme_data=THEMES[theme_key], status=d["status"], logs=d["logs"])

@app.route('/api/status')
def api_status():
    if 'user' not in session: return json.dumps({"error": "unauth"})
    d = user_sessions[session['user']]
    return json.dumps({"count": d["count"], "max_tickets": d["max_tickets"], "speed": d["speed"], "status": d["status"], "logs": d["logs"], "history": d.get("claimed_history", [])})

@app.route('/set_status', methods=['POST'])
def set_status():
    if 'user' in session:
        usr = session['user']
        new_status = request.form.get('new_status')
        if new_status in ["running", "paused", "stopped"]:
            old_status = user_sessions[usr]["status"]
            user_sessions[usr]["status"] = new_status
            if new_status == "running" and old_status == "stopped":
                if user_sessions[usr]["count"] >= user_sessions[usr]["max_tickets"]: user_sessions[usr]["count"] = 0
                threading.Thread(target=run_discord_bot, args=(usr,), daemon=True).start()
    return redirect(url_for('panel'))

@app.route('/update_main', methods=['POST'])
def update_main():
    if 'user' in session:
        usr = session['user']
        user_sessions[usr]["message"] = request.form.get('custom_msg', '').strip()
        try:
            user_sessions[usr]["max_tickets"] = int(request.form.get('max_tickets', 10))
            user_sessions[usr]["speed"] = float(request.form.get('custom_speed', 0.5))
        except: pass
        save_db(usr)
    return redirect(url_for('panel'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
