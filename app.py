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
app.secret_key = "marshall_secret_key_ultra_luxury_v12"

USERS = {
    "Marshall": "oopp0099",
    "Bolana": "oopp00998",
    "Osama": "oopp009987",
    "Kara": "oopp009988"
}

SERVER_ID = "1272600775331414159"
API = "https://discord.com/api/v9/channels"

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
        "running": False, "speed": 0.05, "thread": None, "token": "",
        "message": "مرحباً عزيزي لاعب معك مرشال من فريق الإداري كيف يمكنني مساعدتك",
        "logs": [], "count": 0, "total_lifetime": 0, "max_tickets": 5, "cooldown_mode": False, "skip_next": False, "play_sound": False, "silent_mode": False
    },
    "Bolana": {
        "running": False, "speed": 0.05, "thread": None, "token": "",
        "message": "** أهلاً بك معك بولانا من فريق الإدارة كيف أساعدك **",
        "logs": [], "count": 0, "total_lifetime": 0, "max_tickets": 5, "cooldown_mode": False, "skip_next": False, "play_sound": False, "silent_mode": False
    },
    "Osama": {
        "running": False, "speed": 0.05, "thread": None, "token": "",
        "message": "** أهلاً بك معك أسامة، مختص حصراً بشكاوى قادة الفصائل **",
        "logs": [], "count": 0, "total_lifetime": 0, "max_tickets": 5, "cooldown_mode": False, "skip_next": False, "play_sound": False, "silent_mode": False
    },
    "Kara": {
        "running": False, "speed": 0.05, "thread": None, "token": "",
        "message": "** أهلاً بك معك كارا من فريق الإدارة كيف أساعدك **",
        "logs": [], "count": 0, "total_lifetime": 0, "max_tickets": 5, "cooldown_mode": False, "skip_next": False, "play_sound": False, "silent_mode": False
    }
}

master_global_audit = []
active_tickets = set()
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
        res = requests.post(url, json=payload, headers=headers, timeout=3)
        if res.status_code == 429:
            retry_after = res.json().get("retry_after", current_speed)
            time.sleep(retry_after)
            return safe_post(token, url, payload, current_speed)
        return res
    except Exception:
        return None

def process_ticket(username, token, ch_id, name):
    with state_lock:
        session_data = user_sessions[username]
        if not session_data["running"]:
            return
            
        if session_data["cooldown_mode"]:
            if session_data["skip_next"]:
                session_data["skip_next"] = False
                session_data["logs"].append(f"⚡ [Cooldown] تم تخطي التكت `#{name}` بنجاح.")
                return
            else:
                session_data["skip_next"] = True

        if session_data["count"] >= session_data["max_tickets"]:
            session_data["running"] = False
            return
        if ch_id in active_tickets:
            return
        active_tickets.add(ch_id)

    current_speed = session_data["speed"]
    custom_msg = session_data["message"]
    
    time.sleep(current_speed)
    
    res = safe_post(token, f"{API}/{ch_id}/messages", {"content": custom_msg}, current_speed)
    
    with state_lock:
        if res and res.status_code in [200, 201]:
            ticket_url = f"https://discord.com/channels/{SERVER_ID}/{ch_id}"
            log_text = f"🎯 تم استلام تكت **#{name}** | <a href='{ticket_url}' target='_blank'>رابط التكت</a>"
            
            if not session_data["silent_mode"]:
                session_data["play_sound"] = True
            
            global master_global_audit
            audit_entry = f"[{username}] استلم تكت <b>#{name}</b> | <a href='{ticket_url}' target='_blank'>رابط</a>"
            master_global_audit.insert(0, audit_entry)
            if len(master_global_audit) > 50:
                master_global_audit.pop()
            
            if username in LOG_CHANNELS:
                alert_channel_id = LOG_CHANNELS[username]
                alert_payload = {"content": f"🚨 **{username}** استلم تكت جديد:\n• اسم التكت: `#{name}`\n• الرابط: {ticket_url}"}
                safe_post(token, f"{API}/{alert_channel_id}/messages", alert_payload, current_speed)

            if session_data["count"] < session_data["max_tickets"]:
                session_data["count"] += 1
                session_data["total_lifetime"] += 1
                session_data["logs"].append(f"{log_text} (العدد: {session_data['count']}/{session_data['max_tickets']})")
                if session_data["count"] >= session_data["max_tickets"]:
                    session_data["running"] = False
                    session_data["logs"].append("🛑 تم الوصول للحد الأقصى المحدد من التكتات، توقف البوت.")
        else:
            status_code = res.status_code if res else "خطأ اتصال"
            session_data["logs"].append(f"<span style='color: #ef4444;'>❌ خطأ في استلام تكت #{name} (كود الحالة: {status_code})</span>")
        
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
                        
                        if username == "Osama":
                            is_leader_complaint = any(w in name for w in ["قائد", "فصيل", "ليدر"])
                            if not is_leader_complaint:
                                return

                        ch_id = d.get("id")
                        created_at = ((int(ch_id) >> 22) + 1420070400000) / 1000.0
                        if time.time() - created_at > 120:
                            return
                        with state_lock:
                            if user_sessions[username]["count"] >= user_sessions[username]["max_tickets"] or not user_sessions[username]["running"]:
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
    <title>لوحة التحكم المرعبة - السكربت الخارق</title>
    <style>
        body { 
            background: radial-gradient(circle at center, #110d05 0%, #030303 100%); 
            color: #e2e8f0; 
            font-family: Tahoma, sans-serif; 
            text-align: center; 
            margin: 0; 
            padding: 15px; 
            min-height: 100vh;
        }
        .card { 
            background: linear-gradient(180deg, #12100e 0%, #060504 100%); 
            max-width: 430px; 
            margin: 0 auto; 
            padding: 22px; 
            border-radius: 18px; 
            border: 1px solid #3d2c12; 
            box-shadow: 0 25px 50px rgba(0,0,0,0.95), 0 0 30px rgba(245, 158, 11, 0.12); 
        }
        .logo-glow {
            width: 75px; height: 75px; margin: 0 auto 10px auto;
            background: linear-gradient(135deg, #f59e0b, #b45309);
            border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            font-size: 32px;
            box-shadow: 0 0 20px rgba(245, 158, 11, 0.5);
            border: 2px solid #fbbf24;
        }
        h1 { color: #f59e0b; font-size: 19px; margin-bottom: 2px; text-shadow: 0 2px 10px rgba(245, 158, 11, 0.4); }
        .user-tag { color: #34d399; font-size: 13px; margin-bottom: 12px; font-weight: bold; letter-spacing: 0.5px; }
        
        .speed-badge { 
            background: #0d0c0a; 
            border: 1px solid #33230c; 
            padding: 10px; 
            border-radius: 10px; 
            font-size: 12px; 
            color: #facc15; 
            margin-bottom: 8px;
            box-shadow: inset 0 2px 5px rgba(0,0,0,0.8);
        }
        .stats-badge {
            background: #080706;
            border: 1px solid #2d200e;
            padding: 6px;
            border-radius: 8px;
            font-size: 11px;
            color: #38bdf8;
            margin-bottom: 12px;
        }
        
        .btn { 
            display: block; width: 100%; padding: 12px; margin: 8px 0; 
            font-size: 14px; font-weight: bold; border: none; border-radius: 10px; 
            cursor: pointer; text-decoration: none; transition: all 0.2s ease; 
        }
        .btn:active { transform: scale(0.98); }
        
        .btn-start { background: linear-gradient(135deg, #059669, #047857); color: white; box-shadow: 0 4px 15px rgba(5, 150, 105, 0.4); }
        .btn-stop { background: linear-gradient(135deg, #dc2626, #991b1b); color: white; box-shadow: 0 4px 15px rgba(220, 38, 38, 0.4); }
        .btn-turbo { background: linear-gradient(135deg, #7c3aed, #5b21b6); color: white; box-shadow: 0 4px 15px rgba(124, 58, 237, 0.4); }
        .btn-cooldown-on { background: linear-gradient(135deg, #2563eb, #1e40af); color: white; box-shadow: 0 4px 15px rgba(37, 99, 235, 0.4); }
        .btn-cooldown-off { background: linear-gradient(135deg, #334155, #1e293b); color: #94a3b8; border: 1px solid #475569; }
        .btn-silent-on { background: linear-gradient(135deg, #d97706, #b45309); color: white; box-shadow: 0 4px 15px rgba(217, 119, 6, 0.4); }
        .btn-silent-off { background: linear-gradient(135deg, #334155, #1e293b); color: #94a3b8; border: 1px solid #475569; }
        .btn-reset { background: linear-gradient(135deg, #d97706, #92400e); color: white; box-shadow: 0 4px 15px rgba(217, 119, 6, 0.4); }
        .btn-clear { background: linear-gradient(135deg, #475569, #1e293b); color: #f87171; border: 1px solid #64748b; }
        .btn-token { background: linear-gradient(135deg, #0284c7, #0369a1); color: white; }
        .btn-emergency { background: linear-gradient(135deg, #991b1b, #7f1d1d); color: #fecaca; border: 1px solid #ef4444; }
        
        .speed-row { display: flex; justify-content: space-between; gap: 6px; margin: 4px 0; }
        .btn-speed-up, .btn-speed-down { flex: 1; padding: 8px; background: #0c0b0a; border: 1px solid #33230c; color: #34d399; font-size: 12px; font-weight: bold; border-radius: 8px; cursor: pointer; transition: 0.2s; }
        
        .config-section { text-align: right; margin-top: 10px; background: #080706; padding: 10px; border-radius: 10px; border: 1px solid #2d200e; }
        .config-title { color: #f59e0b; font-size: 11px; margin-bottom: 4px; font-weight: bold; }
        input[type="number"], textarea, select { width: 100%; padding: 8px; background: #030303; border: 1px solid #33230c; color: #e2e8f0; border-radius: 8px; box-sizing: border-box; font-size: 11px; text-align: center; outline: none; }
        textarea { height: 50px; text-align: right; resize: none; }
        .btn-save { width: 100%; padding: 8px; margin-top: 6px; background: linear-gradient(135deg, #d97706, #b45309); color: white; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; font-size: 11px; }

        .log-title { color: #f59e0b; font-size: 11px; margin-top: 10px; text-align: right; font-weight: bold; }
        .log-box { 
            background: #020202; 
            border: 1px solid #261b0a; 
            border-radius: 9px; 
            padding: 8px; 
            height: 95px; 
            overflow-y: auto; 
            text-align: right; 
            font-size: 10px; 
            color: #94a3b8; 
            margin-top: 4px; 
            box-shadow: inset 0 2px 6px rgba(0,0,0,0.9);
        }
        .log-box a { color: #38bdf8; text-decoration: underline; }
        .logout-btn { color: #ef4444; font-size: 11px; display: block; margin-top: 14px; text-decoration: none; font-weight: bold; }
    </style>
    <script>
        function confirmReset() {
            return confirm("هل تريد إعادة تعيين التكتات والأخطاء بالكامل؟");
        }
        
        function confirmEmergency() {
            return confirm("⚠️ تحذير: هل أنت متأكد من إيقاف جميع البوتات لكل الحسابات فوراً؟");
        }
        
        function checkSound() {
            fetch('/check_sound')
            .then(res => res.json())
            .then(data => {
                if(data.play) {
                    let utterance = new SpeechSynthesisUtterance("تم استلام تكت جديد من عمك مرشال");
                    utterance.lang = 'ar-SA';
                    utterance.rate = 1.0;
                    window.speechSynthesis.speak(utterance);
                }
            }).catch(err => {});
        }
        setInterval(checkSound, 1500);
    </script>
</head>
<body>
    <div class="card">
        <div class="logo-glow">⚡</div>
        <h1>لوحة التحكم المرعبة</h1>
        <div class="user-tag">الحساب النشط: {{ username }}</div>
        
        <div class="speed-badge">تم استلام: <b>{{ count }}/{{ max_tickets }}</b> | السرعة: <b>{{ speed }}ث</b></div>
        <div class="stats-badge">📊 إجمالي الإنجاز التراكمي (Session): <b>{{ total_lifetime }} تكت</b></div>
        
        <form action="/toggle" method="post">
            {% if running %}
                <button type="submit" class="btn btn-stop">إيقاف البوت 🛑</button>
            {% else %}
                <button type="submit" class="btn btn-start">تشغيل البوت 🚀</button>
            {% endif %}
        </form>

        <form action="/turbo" method="post">
            <button type="submit" class="btn btn-turbo">⚡ تفعيل وضع التيربو الخارق (0.07ث)</button>
        </form>

        <form action="/toggle_cooldown" method="post">
            {% if cooldown_mode %}
                <button type="submit" class="btn btn-cooldown-on">🛡️ نظام التخطي (مفعل: يستلم ويطخت)</button>
            {% else %}
                <button type="submit" class="btn btn-cooldown-off">🛡️ نظام التخطي (معطل: استلام الكل)</button>
            {% endif %}
        </form>

        <form action="/toggle_silent" method="post">
            {% if silent_mode %}
                <button type="submit" class="btn btn-silent-on">🔇 الوضع الصامت (مفعل: بدون صوت)</button>
            {% else %}
                <button type="submit" class="btn btn-silent-off">🔊 الوضع الصامت (معطل: مع تنبيه صوتي)</button>
            {% endif %}
        </form>

        <form action="/reset_all" method="post" onsubmit="return confirmReset();">
            <button type="submit" class="btn btn-reset">🗑️ إعادة تعيين التكتات والأخطاء</button>
        </form>

        <form action="/clear_logs" method="post">
            <button type="submit" class="btn btn-clear">🧹 تفريغ السجل فقط</button>
        </form>

        <form action="/token" method="get">
            <button type="submit" class="btn btn-token">🔑 تعديل توكن الحساب</button>
        </form>

        {% if username == "Marshall" %}
        <form action="/emergency_stop" method="post" onsubmit="return confirmEmergency();">
            <button type="submit" class="btn btn-emergency">🚨 طوارئ عامة (إيقاف كل الحسابات)</button>
        </form>

        <div class="config-section" style="border-color: #f59e0b; margin-top: 12px;">
            <form action="/check_member_stats" method="post">
                <div class="config-title" style="color: #f59e0b;">🔍 فحص إحصائيات الشباب:</div>
                <select name="target_member" style="margin-bottom: 6px;">
                    {% for member in all_users %}
                        <option value="{{ member }}" {% if selected_member == member %}selected{% endif %}>{{ member }}</option>
                    {% endfor %}
                </select>
                <button type="submit" class="btn-save" style="background: linear-gradient(135deg, #2563eb, #1d4ed8);">عرض تكتات العضو 📊</button>
            </form>
            {% if selected_member %}
            <div style="margin-top: 8px; font-size: 11px; color: #34d399; font-weight: bold; background: #030303; padding: 6px; border-radius: 6px;">
                العضو ({{ selected_member }}): أنجز <b>{{ target_lifetime }}</b> تكت إجمالي، و <b>{{ target_current }}/{{ target_max }}</b> للجلسة الحالية.
            </div>
            {% endif %}
        </div>

        <div class="log-title" style="color: #38bdf8; margin-top: 12px;">🌐 سجل العمليات العام (Master Audit Log):</div>
        <div class="log-box" style="height: 110px; border-color: #1e3a8a;">
            {% for item in global_audit %}
                <div>• {{ item | safe }}</div>
            {% else %}
                <div style="color: #444; text-align: center; margin-top: 30px;">لم يتم تسجيل أي تكت عام حتى الآن...</div>
            {% endfor %}
        </div>
        {% endif %}

        <div class="speed-row" style="margin-top: 10px;">
            <form action="/speed/up" method="post" style="flex:1; display:inline;">
                <button type="submit" class="btn-speed-up">⚡ تسريع (-)</button>
            </form>
            <form action="/speed/down" method="post" style="flex:1; display:inline;">
                <button type="submit" class="btn-speed-down">⏳ إبطاء (+)</button>
            </form>
        </div>

        <div class="config-section">
            <form action="/update_settings" method="post">
                <div class="config-title">تحديد حد التكتات الأقصى:</div>
                <input type="number" name="max_tickets" value="{{ max_tickets }}" min="1" max="100" style="margin-bottom: 6px;">
                
                <div class="config-title">رسالة التكت الخاصة بك:</div>
                <textarea name="custom_msg">{{ message }}</textarea>
                
                <button type="submit" class="btn-save">حفظ الإعدادات 💾</button>
            </form>
        </div>

        <div class="log-title">سجل العمليات والأخطاء البصرية:</div>
        <div class="log-box">
            {% for item in logs %}
                <div>• {{ item | safe }}</div>
            {% else %}
                <div style="color: #444; text-align: center; margin-top: 25px;">لا توجد عمليات مسجلة حتى الآن...</div>
            {% endfor %}
        </div>
        
        <a href="/logout" class="logout-btn">تسجيل خروج من الحساب 🚪</a>
    </div>
</body>
</html>
"""

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><meta charset="UTF-8"><title>تسجيل الدخول</title>
<style>body{background:#030303;color:#fff;font-family:Tahoma;text-align:center;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}.card{background:#0c0a08;width:320px;padding:22px;border-radius:14px;border:1px solid #3d2c12;box-shadow:0 15px 35px rgba(0,0,0,0.9)}input{width:100%;padding:10px;margin:8px 0;background:#030303;border:1px solid #33230c;color:#fff;border-radius:8px;text-align:center;box-sizing:border-box;outline:none}.btn{width:100%;padding:11px;margin-top:10px;background:linear-gradient(135deg, #d97706, #b45309);color:#fff;border:none;border-radius:8px;font-weight:bold;cursor:pointer}</style></head>
<body><div class="card"><h2 style="color:#f59e0b; margin-top:0;">تسجيل الدخول</h2><form method="POST"><input type="text" name="username" placeholder="اسم المستخدم" required><input type="password" name="password" placeholder="الرمز السري" required><button type="submit" class="btn">دخول للنظام</button></form></div></body></html>
"""

TOKEN_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><meta charset="UTF-8"><title>تعديل التوكن</title>
<style>body{background:#030303;color:#fff;font-family:Tahoma;text-align:center;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}.card{background:#0c0a08;width:340px;padding:22px;border-radius:14px;border:1px solid #3d2c12;box-shadow:0 15px 35px rgba(0,0,0,0.9)}textarea{width:100%;height:75px;background:#030303;border:1px solid #33230c;color:#fff;border-radius:8px;text-align:center;resize:none;box-sizing:border-box;font-size:11px;outline:none}.btn{width:100%;padding:11px;margin-top:10px;background:linear-gradient(135deg, #0284c7, #0369a1);color:#fff;border:none;border-radius:8px;font-weight:bold;cursor:pointer}</style></head>
<body><div class="card"><h2 style="color:#38bdf8; margin-top:0;">تعديل توكن الحساب</h2><form method="POST"><textarea name="token" placeholder="الصق التوكن الجديد هنا..." required></textarea><button type="submit" class="btn">حفظ وتحديث التوكن</button></form></div></body></html>
"""

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username in USERS and USERS[username] == password:
            session['user'] = username
            if not user_sessions[username]["token"]:
                return redirect(url_for('set_token'))
            return redirect(url_for('panel'))
    return render_template_string(LOGIN_HTML)

@app.route('/token', methods=['GET', 'POST'])
def set_token():
    if 'user' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        user_sessions[session['user']]["token"] = request.form.get('token').strip()
        user_sessions[session['user']]["logs"].append("🔑 تم تحديث وتعديل توكن الحساب بنجاح.")
        return redirect(url_for('panel'))
    return render_template_string(TOKEN_HTML)

@app.route('/panel')
def panel():
    if 'user' not in session or not user_sessions[session['user']]["token"]: return redirect(url_for('login'))
    usr = session['user']
    data = user_sessions[usr]
    
    selected_member = session.get('selected_member', None)
    target_lifetime = 0
    target_current = 0
    target_max = 0
    if selected_member and selected_member in user_sessions:
        target_lifetime = user_sessions[selected_member]["total_lifetime"]
        target_current = user_sessions[selected_member]["count"]
        target_max = user_sessions[selected_member]["max_tickets"]

    return render_template_string(
        PANEL_HTML, username=usr, running=data["running"], speed=data["speed"], 
        message=data["message"], logs=data["logs"], count=data["count"], 
        total_lifetime=data["total_lifetime"], max_tickets=data["max_tickets"], 
        cooldown_mode=data["cooldown_mode"], silent_mode=data["silent_mode"],
        all_users=list(user_sessions.keys()), selected_member=selected_member, 
        target_lifetime=target_lifetime, target_current=target_current, 
        target_max=target_max, global_audit=master_global_audit
    )

@app.route('/check_sound')
def check_sound():
    if 'user' in session:
        usr = session['user']
        if user_sessions[usr]["play_sound"]:
            user_sessions[usr]["play_sound"] = False
            return {"play": True}
    return {"play": False}

@app.route('/toggle', methods=['POST'])
def toggle():
    if 'user' in session:
        usr = session['user']
        data = user_sessions[usr]
        if not data["running"]:
            if data["token"]:
                if data["count"] >= data["max_tickets"]:
                    data["count"] = 0
                data["running"] = True
                t = threading.Thread(target=run_discord_bot, args=(usr,))
                t.daemon = True
                t.start()
        else:
            data["running"] = False
    return redirect(url_for('panel'))

@app.route('/turbo', methods=['POST'])
def turbo():
    if 'user' in session:
        user_sessions[session['user']]["speed"] = 0.07
        user_sessions[session['user']]["logs"].append("⚡ تم تفعيل وضع التيربو الخارق (0.07ث).")
    return redirect(url_for('panel'))

@app.route('/toggle_cooldown', methods=['POST'])
def toggle_cooldown():
    if 'user' in session:
        usr = session['user']
        user_sessions[usr]["cooldown_mode"] = not user_sessions[usr]["cooldown_mode"]
        user_sessions[usr]["skip_next"] = False
        status_txt = "مفعل (يستلم ويتخطي)" if user_sessions[usr]["cooldown_mode"] else "معطل"
        user_sessions[usr]["logs"].append(f"🛡️ تم تغيير نظام التخطي إلى: {status_txt}")
    return redirect(url_for('panel'))

@app.route('/toggle_silent', methods=['POST'])
def toggle_silent():
    if 'user' in session:
        usr = session['user']
        user_sessions[usr]["silent_mode"] = not user_sessions[usr]["silent_mode"]
        status_txt = "مفعل (بدون صوت)" if user_sessions[usr]["silent_mode"] else "معطل"
        user_sessions[usr]["logs"].append(f"🔇 تم تغيير وضع الإسكات الصوتي إلى: {status_txt}")
    return redirect(url_for('panel'))

@app.route('/reset_all', methods=['POST'])
def reset_all():
    if 'user' in session:
        usr = session['user']
        user_sessions[usr]["count"] = 0
        user_sessions[usr]["logs"] = []
        user_sessions[usr]["logs"].append("🗑️ تم إعادة تعيين العداد وتفريغ السجل والأخطاء بالكامل.")
    return redirect(url_for('panel'))

@app.route('/clear_logs', methods=['POST'])
def clear_logs():
    if 'user' in session:
        usr = session['user']
        user_sessions[usr]["logs"] = []
    return redirect(url_for('panel'))

@app.route('/emergency_stop', methods=['POST'])
def emergency_stop():
    if 'user' in session and session['user'] == "Marshall":
        for u in user_sessions:
            user_sessions[u]["running"] = False
            user_sessions[u]["logs"].append("🚨 تم تفعيل الطوارئ العامة وإيقاف جميع البوتات بواسطة مرشال.")
    return redirect(url_for('panel'))

@app.route('/check_member_stats', methods=['POST'])
def check_member_stats():
    if 'user' in session and session['user'] == "Marshall":
        target = request.form.get('target_member')
        if target in user_sessions:
            session['selected_member'] = target
    return redirect(url_for('panel'))

@app.route('/speed/up', methods=['POST'])
def speed_up():
    if 'user' in session:
        usr = session['user']
        if user_sessions[usr]["speed"] > 0.01:
            user_sessions[usr]["speed"] = round(max(0.01, user_sessions[usr]["speed"] - 0.02), 2)
            user_sessions[usr]["logs"].append(f"⚡ تمت زيادة السرعة لتصبح: {user_sessions[usr]['speed']}ث")
    return redirect(url_for('panel'))

@app.route('/speed/down', methods=['POST'])
def speed_down():
    if 'user' in session:
        usr = session['user']
        user_sessions[usr]["speed"] = round(user_sessions[usr]["speed"] + 0.05, 2)
        user_sessions[usr]["logs"].append(f"⏳ تم تقليل السرعة لتصبح: {user_sessions[usr]['speed']}ث")
    return redirect(url_for('panel'))

@app.route('/update_settings', methods=['POST'])
def update_settings():
    if 'user' in session:
        usr = session['user']
        new_msg = request.form.get('custom_msg', '').strip()
        try:
            new_max = int(request.form.get('max_tickets', 5))
            if new_max > 0:
                user_sessions[usr]["max_tickets"] = new_max
        except ValueError:
            pass
        if new_msg:
            user_sessions[usr]["message"] = new_msg
        user_sessions[usr]["logs"].append("💾 تم حفظ وتحديث الإعدادات بنجاح.")
    return redirect(url_for('panel'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('selected_member', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
