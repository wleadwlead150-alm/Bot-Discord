import json
import re
import time
import requests
import websocket
import threading
import random
import os
import base64
from flask import Flask, render_template_string, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "saif_elite_system_core_v24_secure_key"

USERS = {
    "Saif": "12345678",
    "Marshall": "oopp0099",
    "Youssef": "oopp009987",
    "Kara": "oopp00998",
    "isso": "12345678"
}

SERVER_ID = "1272600775331414159"
API = "https://discord.com/api/v9/channels"
SAIF_ALERT_CHANNEL = "1545711547169513483"

user_sessions = {
    "Saif": {
        "running": False, "speed": 1.5, "thread": None, "token": "",
        "message": "أهلاً بك عزيزي، معك Saif من فريق الإدارة العليا. تفضل كيف يمكنني خدمتك؟",
        "reply_template": "default", "ticket_filter": "all",
        "logs": [], "count": 0, "total_lifetime": 0, "max_tickets": 10, "cooldown_mode": False, "skip_next": False, "silent_mode": False, "rate_limit_errors": 0, "banned_secure": False, "last_sent_text": "", "last_sent_time": 0
    },
    "Marshall": {
        "running": False, "speed": 1.5, "thread": None, "token": "",
        "message": "أهلاً بك، معك Marshall الإدارة العليا. كيف يمكنني مساعدتك؟",
        "reply_template": "default", "ticket_filter": "all",
        "logs": [], "count": 0, "total_lifetime": 0, "max_tickets": 10, "cooldown_mode": False, "skip_next": False, "silent_mode": False, "rate_limit_errors": 0, "banned_secure": False, "last_sent_text": "", "last_sent_time": 0
    },
    "Youssef": {
        "running": False, "speed": 1.5, "thread": None, "token": "",
        "message": "أهلاً بك، معك Youssef الإدارة العليا. تفضل بطرح مشكلتك.",
        "reply_template": "default", "ticket_filter": "all",
        "logs": [], "count": 0, "total_lifetime": 0, "max_tickets": 10, "cooldown_mode": False, "skip_next": False, "silent_mode": False, "rate_limit_errors": 0, "banned_secure": False, "last_sent_text": "", "last_sent_time": 0
    },
    "Kara": {
        "running": False, "speed": 1.5, "thread": None, "token": "",
        "message": "أهلاً بك، معك Kara الإدارة العليا. تفضل كيف يمكنني خدمتك؟",
        "reply_template": "default", "ticket_filter": "all",
        "logs": [], "count": 0, "total_lifetime": 0, "max_tickets": 10, "cooldown_mode": False, "skip_next": False, "silent_mode": False, "rate_limit_errors": 0, "banned_secure": False, "last_sent_text": "", "last_sent_time": 0
    },
    "isso": {
        "running": False, "speed": 1.5, "thread": None, "token": "",
        "message": "أهلاً بك، معك isso. تم استلام شكواك الإدارية وجاري معالجتها من قبل المختصين.",
        "reply_template": "default", "ticket_filter": "administrative",
        "logs": [], "count": 0, "total_lifetime": 0, "max_tickets": 10, "cooldown_mode": False, "skip_next": False, "silent_mode": False, "rate_limit_errors": 0, "banned_secure": False, "last_sent_text": "", "last_sent_time": 0
    }
}

active_tickets = set()
state_lock = threading.Lock()

REPLY_TEMPLATES = {
    "default": "", 
    "evidence_req": "عزيزي، الشكاوي التي تتطلب دلائل يجب إرفاق مقطع فيديو يوضح كافة التفاصيل مع إظهار الهوية.\n-# **نحن بانتظار استكمال المتطلبات.**",
    "review_wait": "أهلاً بك، جاري مراجعة طلبك بكل دقة. نرجو التحلي بالصبر.\n\n-# **فريق الإدارة في خدمتكم**",
    "ban_evidence": "نرجو الانتظار قليلاً ريثما يتم جلب تفاصيل التوثيق والأدلة الخاصة بالخادم."
}

def get_secure_headers(token):
    # بصمة ديناميكية متغيرة لزيادة التخفي
    build_num = random.randint(320000, 325000)
    props = {
        "os": "iOS",
        "browser": "Discord Client",
        "device": "iPhone 13, pro, max",
        "system_version": "17.5",
        "client_build_number": build_num,
        "client_version": "241.0"
    }
    b64_props = base64.b64encode(json.dumps(props).encode()).decode()
    return {
        "Authorization": token.strip(),
        "Content-Type": "application/json",
        "User-Agent": "Discord/241.0 CFNetwork/1498.700.2 Darwin/23.4.0",
        "X-Super-Properties": b64_props,
        "X-Discord-Locale": "ar",
        "Accept-Language": "ar,en-US;q=0.9,en;q=0.8"
    }

def check_token_health(token):
    if not token:
        return "❌ التوكن فارغ غير مدخل"
    try:
        headers = get_secure_headers(token)
        res = requests.get("https://discord.com/api/v9/users/@me", headers=headers, timeout=5)
        if res.status_code == 200:
            user_data = res.json()
            tag = f"{user_data.get('username')}#{user_data.get('discriminator', '0')}"
            return f"✅ التوكن سليم وشغال تمام ({tag})"
        elif res.status_code == 401:
            return "❌ التوكن غير صالح أو منتهي الصلاحية (401)"
        else:
            return f"⚠️ استجابة غير متوقعة من الديسكورد (كود: {res.status_code})"
    except Exception as e:
        return f"❌ خطأ في الاتصال بالشبكة فحص التوكن: {str(e)}"

def send_typing(token, ch_id):
    try:
        requests.post(f"{API}/{ch_id}/typing", headers=get_secure_headers(token), timeout=2)
    except:
        pass

def safe_post(token, url, payload, current_speed, username=None):
    try:
        headers = get_secure_headers(token)
        
        # محاكاة الكتابة إذا كان الطلب لإرسال رسالة
        if "messages" in url and "typing" not in url:
            ch_id = url.split("/channels/")[1].split("/")[0]
            send_typing(token, ch_id)
            time.sleep(random.uniform(0.1, 0.3)) # تأخير شبحي قصير يبدو كأن بشراً يطبع
        else:
            time.sleep(current_speed)
        
        res = requests.post(url, json=payload, headers=headers, timeout=5)
        
        # نظام الهروب الاستباقي (الدرع الشبكي)
        remaining = int(res.headers.get('X-RateLimit-Remaining', 5))
        if remaining <= 1 and res.status_code != 429:
            reset_after = float(res.headers.get('X-RateLimit-Reset-After', 1.0))
            if username and username in user_sessions:
                user_sessions[username]["logs"].append(f"🛡️ [الدرع الذكي] توقف استباقي لـ {reset_after}ث لتجنب الكتم.")
            time.sleep(reset_after + 0.1)
            
        if res.status_code == 429:
            if username and username in user_sessions:
                with state_lock:
                    user_sessions[username]["rate_limit_errors"] += 1
                    if user_sessions[username]["rate_limit_errors"] >= 3:
                        user_sessions[username]["running"] = False
                        user_sessions[username]["banned_secure"] = True
                        user_sessions[username]["logs"].append("🚨 [Elite Shield] تم تجميد الحساب مؤقتاً لتفادي الباند النهائي.")
            retry_after = res.json().get("retry_after", current_speed + 1.0)
            time.sleep(retry_after + 0.5)
            return safe_post(token, url, payload, current_speed, username)
        return res
    except Exception:
        return None

def process_ticket(username, token, ch_id, name):
    with state_lock:
        session_data = user_sessions[username]
        if not session_data["running"] or session_data["banned_secure"]: return
            
        # فلتر الشكاوى الإدارية بدقة (isso)
        filter_mode = session_data.get("ticket_filter", "all")
        if filter_mode == "administrative":
            if not ("الاداريين" in name or "الاداري" in name or "شكاوي-الاداريين" in name or "administrative" in name):
                return

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
    if tpl_key != "default" and tpl_key in REPLY_TEMPLATES:
        custom_msg = REPLY_TEMPLATES[tpl_key]
    else:
        custom_msg = session_data["message"]
    
    now_ts = time.time()
    if session_data["last_sent_text"] == custom_msg and (now_ts - session_data["last_sent_time"] < 2.0):
        custom_msg += "᠎" * random.randint(1, 2)
    
    session_data["last_sent_text"] = custom_msg
    session_data["last_sent_time"] = now_ts

    res = safe_post(token, f"{API}/{ch_id}/messages", {"content": custom_msg}, current_speed, username)
    
    with state_lock:
        if res and res.status_code in [200, 201]:
            ticket_url = f"https://discord.com/channels/{SERVER_ID}/{ch_id}"
            log_text = f"✨ تم استلام تكت بنجاح **#{name}** | <a href='{ticket_url}' target='_blank'>رابط التكت</a>"

            # تنبيه سيف المخصص
            if username == "Saif":
                alert_payload = {
                    "content": f"💎 **إشعار الإدارة - النظام المتقدم** 💎\n\nقام الإداري **سيف (Saif)** باستلام تذكرة جديدة بنجاح ✅\n\n🎫 **اسم التذكرة:** `#{name}`\n🔗 **رابط التذكرة:** {ticket_url}\n⚡ **الحالة:** تم الرد وإرسال القالب السريع."
                }
                safe_post(token, f"{API}/{SAIF_ALERT_CHANNEL}/messages", alert_payload, 0.5, username)

            if session_data["count"] < session_data["max_tickets"]:
                session_data["count"] += 1
                session_data["total_lifetime"] += 1
                session_data["logs"].append(f"{log_text} (العدد: {session_data['count']}/{session_data['max_tickets']})")
                if session_data["count"] >= session_data["max_tickets"]:
                    session_data["running"] = False
                    session_data["logs"].append("🛑 تم بلوغ الحد الأقصى المحدد للتكتات، توقف النظام.")
        else:
            status_code = res.status_code if res else "خطأ اتصال"
            session_data["logs"].append(f"<span style='color: #ff4b4b;'>❌ تعذر استلام التكت #{name} (كود الحالة: {status_code})</span>")
        
    with state_lock:
        if ch_id in active_tickets:
            active_tickets.remove(ch_id)

def run_discord_bot(username):
    token = user_sessions[username]["token"]
    user_sessions[username]["logs"].append("🚀 [Elite System] تم تفعيل النظام والدرع الشبحي بنجاح...")
    
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
                    created_at = ((int(ch_id) >> 22) + 1420070400000) / 1000.0
                    if time.time() - created_at > 90: return
                    with state_lock:
                        if user_sessions[username]["count"] >= user_sessions[username]["max_tickets"] or not user_sessions[username]["running"]: return
                    threading.Thread(target=process_ticket, args=(username, token, ch_id, name)).start()
        except Exception:
            pass

    def on_open(ws):
        payload = {
            "op": 2,
            "d": {
                "token": token,
                "properties": {
                    "os": "iOS", "browser": "Discord Client", "device": "iPhone 13, pro, max", "system_version": "17.5"
                },
                "intents": 1 << 0
            }
        }
        ws.send(json.dumps(payload))

    ws_url = "wss://gateway.discord.gg/?v=9&encoding=json"
    while user_sessions[username]["running"] and not user_sessions[username]["banned_secure"]:
        try:
            ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message)
            ws.run_forever()
        except Exception:
            time.sleep(2)

# --- الواجهة الزجاجية الفخمة (VIP Glassmorphism UI) ---

PANEL_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>لوحة القيادة المركزية - VIP Operations</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap');
        body { 
            background: linear-gradient(135deg, #09090b 0%, #17171a 100%); 
            color: #f8fafc; 
            font-family: 'Cairo', sans-serif; 
            text-align: center; 
            margin: 0; 
            padding: 15px; 
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .glass-card { 
            background: rgba(20, 20, 25, 0.65); 
            backdrop-filter: blur(16px); 
            -webkit-backdrop-filter: blur(16px); 
            max-width: 440px; 
            width: 100%;
            padding: 26px; 
            border-radius: 24px; 
            border: 1px solid rgba(255, 255, 255, 0.08); 
            box-shadow: 0 30px 60px rgba(0,0,0,0.8), inset 0 0 20px rgba(139, 92, 246, 0.05); 
        }
        .logo-glow { 
            width: 75px; height: 75px; margin: 0 auto 15px auto; 
            background: linear-gradient(135deg, #8b5cf6, #4c1d95); 
            border-radius: 22px; display: flex; align-items: center; justify-content: center; 
            font-size: 32px; box-shadow: 0 0 30px rgba(139, 92, 246, 0.4); 
            border: 1px solid rgba(255, 255, 255, 0.2); 
        }
        h1 { color: #ffffff; font-size: 22px; margin-bottom: 4px; font-weight: 900; letter-spacing: 0.5px; text-shadow: 0 2px 10px rgba(0,0,0,0.5); }
        .user-tag { color: #c4b5fd; font-size: 12px; margin-bottom: 16px; font-weight: 700; background: rgba(0,0,0,0.4); display: inline-block; padding: 5px 14px; border-radius: 20px; border: 1px solid rgba(139, 92, 246, 0.3); }
        
        .badge-container { display: flex; gap: 8px; margin-bottom: 16px; }
        .glass-badge { flex: 1; background: rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.05); padding: 12px 8px; border-radius: 14px; font-size: 11px; color: #cbd5e1; font-weight: 600; }
        .glass-badge b { color: #2dd4bf; font-size: 13px; display: block; margin-top: 4px; }
        
        .btn { display: block; width: 100%; padding: 12px; margin: 8px 0; font-size: 13px; font-weight: 700; border: none; border-radius: 14px; cursor: pointer; text-decoration: none; transition: all 0.3s ease; font-family: 'Cairo', sans-serif; text-shadow: 0 1px 3px rgba(0,0,0,0.4); }
        .btn:hover { transform: translateY(-3px); box-shadow: 0 10px 20px rgba(0,0,0,0.4); }
        .btn-start { background: linear-gradient(135deg, #10b981, #059669); color: white; box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3); }
        .btn-stop { background: linear-gradient(135deg, #ef4444, #dc2626); color: white; box-shadow: 0 4px 15px rgba(239, 68, 68, 0.3); }
        .btn-secondary { background: rgba(255,255,255,0.05); color: #cbd5e1; border: 1px solid rgba(255,255,255,0.1); }
        .btn-secondary:hover { background: rgba(255,255,255,0.1); color: #fff; }
        
        .config-section { text-align: right; margin-top: 15px; background: rgba(0,0,0,0.3); padding: 14px; border-radius: 16px; border: 1px solid rgba(255,255,255,0.05); }
        .config-title { color: #a78bfa; font-size: 11px; margin-bottom: 6px; font-weight: 700; }
        
        input, select, textarea { width: 100%; padding: 10px; background: rgba(0,0,0,0.5); border: 1px solid rgba(255,255,255,0.1); color: #fff; border-radius: 12px; box-sizing: border-box; font-size: 11px; text-align: center; outline: none; margin-bottom: 8px; font-family: 'Cairo', sans-serif; transition: 0.3s; }
        input:focus, select:focus, textarea:focus { border-color: #8b5cf6; box-shadow: 0 0 10px rgba(139, 92, 246, 0.2); }
        textarea { height: 65px; text-align: right; resize: none; }
        
        .log-box { background: rgba(0,0,0,0.6); border: 1px solid rgba(255,255,255,0.05); border-radius: 14px; padding: 10px; height: 110px; overflow-y: auto; text-align: right; font-size: 10px; color: #94a3b8; margin-top: 8px; box-shadow: inset 0 5px 15px rgba(0,0,0,0.5); }
        .log-box a { color: #38bdf8; text-decoration: none; font-weight: 700; }
        .log-box a:hover { text-decoration: underline; }
        
        .logout-btn { color: #fb7185; font-size: 12px; display: inline-block; margin-top: 18px; text-decoration: none; font-weight: 700; transition: 0.2s; background: rgba(251, 113, 133, 0.1); padding: 6px 16px; border-radius: 20px; }
        .logout-btn:hover { background: rgba(251, 113, 133, 0.2); color: #fff; }
    </style>
    <script>
        function confirmReset() { return confirm("هل أنت متأكد من إعادة تعيين العدادات والأخطاء؟"); }
    </script>
</head>
<body>
    <div class="glass-card">
        <div class="logo-glow">💎</div>
        <h1>منظومة الإدارة العليا</h1>
        <div class="user-tag">الحساب النشط: {{ username }}</div>
        
        <div class="badge-container">
            <div class="glass-badge">المنجز <b>{{ count }}/{{ max_tickets }}</b></div>
            <div class="glass-badge">السرعة <b>{{ speed }}ث</b></div>
            <div class="glass-badge">التراكمي <b>{{ total_lifetime }}</b></div>
        </div>
        
        <form action="/toggle" method="post">
            {% if running %}
                <button type="submit" class="btn btn-stop">إيقاف النظام 🛑</button>
            {% else %}
                <button type="submit" class="btn btn-start">تشغيل النظام الآلي 🚀</button>
            {% endif %}
        </form>

        <div style="display: flex; gap: 8px; margin: 10px 0;">
            <form action="/toggle_cooldown" method="post" style="flex:1;">
                <button type="submit" class="btn btn-secondary">{% if cooldown_mode %}🟢 التخطي شغال{% else %}⚪ التخطي معطل{% endif %}</button>
            </form>
            <form action="/toggle_silent" method="post" style="flex:1;">
                <button type="submit" class="btn btn-secondary">{% if silent_mode %}🔇 صامت شغال{% else %}🔊 صامت معطل{% endif %}</button>
            </form>
        </div>

        <div class="config-section">
            <form action="/update_settings" method="post">
                <div class="config-title">الحد الأقصى للتكتات:</div>
                <input type="number" name="max_tickets" value="{{ max_tickets }}" min="1" max="100">
                
                <div class="config-title">ضبط سرعة الاستجابة بالثواني:</div>
                <input type="number" step="0.1" name="custom_speed" value="{{ speed }}" min="0.5" max="10.0">

                <div class="config-title">نوع التكتات (فلتر):</div>
                <select name="ticket_filter">
                    <option value="all" {% if ticket_filter == 'all' %}selected{% endif %}>جميع التكتات</option>
                    <option value="administrative" {% if ticket_filter == 'administrative' %}selected{% endif %}>الشكاوى الإدارية فقط (خاص isso)</option>
                </select>

                <div class="config-title">قالب الرد التلقائي:</div>
                <select name="reply_template">
                    <option value="default" {% if reply_template == 'default' %}selected{% endif %}>النص المخصص (الأساسي)</option>
                    <option value="evidence_req" {% if reply_template == 'evidence_req' %}selected{% endif %}>طلب أدلة الشكاوى والمقاطع</option>
                    <option value="review_wait" {% if reply_template == 'review_wait' %}selected{% endif %}>جاري مراجعة الطلب (تحلى بالصبر)</option>
                    <option value="ban_evidence" {% if reply_template == 'ban_evidence' %}selected{% endif %}>طلب تفاصيل الحظر للإدارة</option>
                </select>

                <div class="config-title">تخصيص نص الرد يدوياً:</div>
                <textarea name="custom_msg">{{ message }}</textarea>
                <button type="submit" class="btn" style="background: linear-gradient(135deg, #8b5cf6, #6d28d9); color: #fff;">حفظ الإعدادات 💾</button>
            </form>
        </div>

        <div style="display: flex; gap: 8px; margin: 12px 0;">
            <form action="/token" method="get" style="flex:1;"><button type="submit" class="btn btn-secondary" style="margin:0;">🔑 التوكن</button></form>
            <form action="/check_token" method="post" style="flex:1;"><button type="submit" class="btn btn-secondary" style="margin:0; background: rgba(16, 185, 129, 0.1); border-color: rgba(16, 185, 129, 0.3); color: #34d399;">🔍 فحص</button></form>
            <form action="/reset_all" method="post" onsubmit="return confirmReset();" style="flex:1;"><button type="submit" class="btn btn-secondary" style="margin:0; background: rgba(239, 68, 68, 0.1); border-color: rgba(239, 68, 68, 0.3); color: #f87171;">🗑️ تصفير</button></form>
        </div>

        <div class="log-title" style="margin-top: 15px;">سجل العمليات اللحظية:</div>
        <div class="log-box">
            {% for item in logs %}<div>• {{ item | safe }}</div>{% else %}<div style="color: #475569; text-align: center; margin-top: 30px;">النظام جاهز ومحمي بالكامل...</div>{% endfor %}
        </div>
        <a href="/logout" class="logout-btn">تسجيل خروج 🚪</a>
    </div>
</body>
</html>
"""

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>تسجيل الدخول - VIP Operations</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap');
        body { background: linear-gradient(135deg, #09090b 0%, #17171a 100%); color: #f8fafc; font-family: 'Cairo', sans-serif; text-align: center; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .glass-card { background: rgba(20, 20, 25, 0.65); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); width: 340px; padding: 35px 25px; border-radius: 24px; border: 1px solid rgba(255, 255, 255, 0.08); box-shadow: 0 30px 60px rgba(0,0,0,0.8), inset 0 0 20px rgba(139, 92, 246, 0.05); }
        .login-logo { width: 75px; height: 75px; margin: 0 auto 20px auto; background: linear-gradient(135deg, #8b5cf6, #4c1d95); border-radius: 22px; display: flex; align-items: center; justify-content: center; font-size: 32px; box-shadow: 0 0 30px rgba(139, 92, 246, 0.4); border: 1px solid rgba(255, 255, 255, 0.2); }
        input { width: 100%; padding: 12px; margin: 8px 0; background: rgba(0,0,0,0.5); border: 1px solid rgba(255,255,255,0.1); color: #fff; border-radius: 12px; text-align: center; outline: none; font-size: 13px; font-family: 'Cairo', sans-serif; transition: 0.3s; }
        input:focus { border-color: #8b5cf6; box-shadow: 0 0 15px rgba(139, 92, 246, 0.2); }
        .btn { width: 100%; padding: 14px; margin-top: 15px; background: linear-gradient(135deg, #8b5cf6, #6d28d9); color: #fff; border: none; border-radius: 12px; font-weight: 700; cursor: pointer; font-size: 14px; font-family: 'Cairo', sans-serif; box-shadow: 0 5px 20px rgba(139, 92, 246, 0.4); transition: 0.3s; }
        .btn:hover { transform: translateY(-3px); box-shadow: 0 10px 25px rgba(139, 92, 246, 0.5); }
        .dev-tag { color: #a78bfa; font-size: 11px; margin-bottom: 20px; font-weight: 700; letter-spacing: 0.5px; }
    </style>
</head>
<body>
    <div class="glass-card">
        <div class="login-logo">👑</div>
        <div class="dev-tag">⚡ تم التطوير بواسطة مرشال</div>
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
<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>تعديل التوكن - VIP</title>
<style>@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');body{background: linear-gradient(135deg, #09090b 0%, #17171a 100%);color:#fff;font-family:'Cairo',sans-serif;text-align:center;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}.glass-card{background:rgba(20,20,25,0.65);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);width:340px;padding:30px;border-radius:24px;border:1px solid rgba(255,255,255,0.08);box-shadow:0 30px 60px rgba(0,0,0,0.8)}textarea{width:100%;height:90px;background:rgba(0,0,0,0.5);border:1px solid rgba(255,255,255,0.1);color:#fff;border-radius:12px;text-align:center;resize:none;box-sizing:border-box;font-size:11px;outline:none;font-family:'Cairo',sans-serif;padding:12px;transition:0.3s}textarea:focus{border-color:#8b5cf6;box-shadow:0 0 15px rgba(139,92,246,0.2)}.btn{width:100%;padding:14px;margin-top:15px;background:linear-gradient(135deg,#8b5cf6,#6d28d9);color:#fff;border:none;border-radius:12px;font-weight:700;cursor:pointer;font-family:'Cairo',sans-serif;transition:0.3s}.btn:hover{transform:translateY(-3px);box-shadow:0 10px 25px rgba(139,92,246,0.5)}</style></head>
<body><div class="glass-card"><h2 style="color:#e879f9; margin-top:0; font-size:18px;">تحديث توكن الحساب</h2><form method="POST"><textarea name="token" placeholder="قم بلصق التوكن الخاص بك هنا..." required></textarea><button type="submit" class="btn">حفظ وتأمين التوكن 💾</button></form></div></body></html>
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
        user_sessions[session['user']]["logs"].append("🔑 تم تحديث وتأمين توكن الحساب بنجاح.")
        return redirect(url_for('panel'))
    return render_template_string(TOKEN_HTML)

@app.route('/check_token', methods=['POST'])
def check_token_route():
    if 'user' in session:
        usr = session['user']
        token = user_sessions[usr]["token"]
        result_msg = check_token_health(token)
        user_sessions[usr]["logs"].append(result_msg)
    return redirect(url_for('panel'))

@app.route('/panel')
def panel():
    if 'user' not in session or not user_sessions[session['user']]["token"]: return redirect(url_for('login'))
    usr = session['user']
    data = user_sessions[usr]
    return render_template_string(
        PANEL_HTML, username=usr, running=data["running"], speed=data["speed"], 
        message=data["message"], reply_template=data.get("reply_template", "default"),
        ticket_filter=data.get("ticket_filter", "all"),
        logs=data["logs"], count=data["count"], total_lifetime=data["total_lifetime"], 
        max_tickets=data["max_tickets"], cooldown_mode=data["cooldown_mode"], 
        silent_mode=data["silent_mode"], rate_errors=data["rate_limit_errors"]
    )

@app.route('/toggle', methods=['POST'])
def toggle():
    if 'user' in session:
        usr = session['user']
        data = user_sessions[usr]
        if not data["running"] and not data["banned_secure"]:
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

@app.route('/toggle_cooldown', methods=['POST'])
def toggle_cooldown():
    if 'user' in session:
        usr = session['user']
        user_sessions[usr]["cooldown_mode"] = not user_sessions[usr]["cooldown_mode"]
        user_sessions[usr]["skip_next"] = False
    return redirect(url_for('panel'))

@app.route('/toggle_silent', methods=['POST'])
def toggle_silent():
    if 'user' in session:
        usr = session['user']
        user_sessions[usr]["silent_mode"] = not user_sessions[usr]["silent_mode"]
    return redirect(url_for('panel'))

@app.route('/reset_all', methods=['POST'])
def reset_all():
    if 'user' in session:
        usr = session['user']
        user_sessions[usr]["count"] = 0
        user_sessions[usr]["rate_limit_errors"] = 0
        user_sessions[usr]["banned_secure"] = False
        user_sessions[usr]["logs"] = []
    return redirect(url_for('panel'))

@app.route('/clear_logs', methods=['POST'])
def clear_logs():
    if 'user' in session:
        user_sessions[session['user']]["logs"] = []
    return redirect(url_for('panel'))

@app.route('/update_settings', methods=['POST'])
def update_settings():
    if 'user' in session:
        usr = session['user']
        new_msg = request.form.get('custom_msg', '').strip()
        new_tpl = request.form.get('reply_template', 'default')
        new_filter = request.form.get('ticket_filter', 'all')
        
        user_sessions[usr]["reply_template"] = new_tpl
        user_sessions[usr]["ticket_filter"] = new_filter
        
        try:
            new_max = int(request.form.get('max_tickets', 10))
            if new_max > 0: user_sessions[usr]["max_tickets"] = new_max
        except ValueError:
            pass
        try:
            new_speed = float(request.form.get('custom_speed', 1.5))
            if new_speed >= 0.1: user_sessions[usr]["speed"] = round(new_speed, 1)
        except ValueError:
            pass
        if new_msg: user_sessions[usr]["message"] = new_msg
    return redirect(url_for('panel'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
