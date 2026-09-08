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
app.secret_key = "saif_elite_system_core_v24_secure_key"

USERS = {
    "Saif": "12345678",
    "Marshall": "oopp0099",
    "kara": "oopp00998"
}

SERVER_ID = "1272600775331414159"
API = "https://discord.com/api/v9/channels"

DEFAULT_ALERT_CHANNEL = "1545711547169513483"

LOG_CHANNELS = {
    "Saif": DEFAULT_ALERT_CHANNEL,
    "Marshall": DEFAULT_ALERT_CHANNEL,
    "Youssef": DEFAULT_ALERT_CHANNEL
}

STEALTH_DEVICE_PROFILES = [
    {
        "User-Agent": "Discord/188215 CFNetwork/1498.700.2 Darwin/23.4.0",
        "X-Super-Properties": "eyJvcyI6ImlPUyIsImJyb3dzZXIiOiJEaXNjb3JkIENsaWVudCIsImRldmljZSI6ImlQaG9uZSAxMywgcHJvLCBtYXgiLCJzeXN0ZW1fdmVyc2lvbiI6IjE3LjUif="
    },
    {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Discord/241.0",
        "X-Super-Properties": "eyJvcyI6ImlPUyIsImJyb3dzZXIiOiJkaXNjb3JkIiwiZGV2aWNlIjoiaVBob25lIDEzIiwic3lzdGVtX3ZlcnNpb24iOiIxNy40LjEif="
    },
    {
        "User-Agent": "Discord/218228 CFNetwork/1408.0.4 Darwin/22.4.0",
        "X-Super-Properties": "eyJvcyI6ImlPUyIsImJyb3dzZXIiOiJEaXNjb3JkIENsaWVudCIsImRldmljZSI6ImlQaG9ucyAxNCwgcHJvIiwic3lzdGVtX3ZlcnNpb24iOiIxNi40In="
    },
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Discord/0.0.309",
        "X-Super-Properties": "eyJvcyI6IldpbmRvd3MiLCJicm93c2VyIjoiRGlzY29yZCBDbGllbnQiLCJkZXZpY2UiOiJEZXNrdG9wIiwic3lzdGVtX3ZlcnNpb24iOiIxMC4wLjE5MDQyIn="
    }
]

user_sessions = {
    "Saif": {
        "running": False, "speed": 1.5, "thread": None, "token": "",
        "message": "أهلاً بك عزيزي، معك Saif من فريق الإدارة العليا. تفضل كيف يمكنني خدمتك؟",
        "reply_template": "default",
        "logs": [], "count": 0, "total_lifetime": 0, "max_tickets": 10, "cooldown_mode": False, "skip_next": False, "silent_mode": False, "rate_limit_errors": 0, "banned_secure": False, "last_sent_text": "", "last_sent_time": 0
    },
    "Marshall": {
        "running": False, "speed": 1.5, "thread": None, "token": "",
        "message": "أهلاً بك، معك Marshall الإدارة العليا. كيف يمكنني مساعدتك؟",
        "reply_template": "default",
        "logs": [], "count": 0, "total_lifetime": 0, "max_tickets": 10, "cooldown_mode": False, "skip_next": False, "silent_mode": False, "rate_limit_errors": 0, "banned_secure": False, "last_sent_text": "", "last_sent_time": 0
    },
    "Youssef": {
        "running": False, "speed": 1.5, "thread": None, "token": "",
        "message": "أهلاً بك، معك Youssef الإدارة العليا. تفضل بطرح مشكلتك.",
        "reply_template": "default",
        "logs": [], "count": 0, "total_lifetime": 0, "max_tickets": 10, "cooldown_mode": False, "skip_next": False, "silent_mode": False, "rate_limit_errors": 0, "banned_secure": False, "last_sent_text": "", "last_sent_time": 0
    }
}

master_global_audit = []
security_audit_logs = []
active_tickets = set()
state_lock = threading.Lock()

REPLY_TEMPLATES = {
    "default": "", 
    "evidence_req": "عزيزي، الشكاوي التي تتطلب دلائل يجب إرفاق مقطع فيديو يوضح كافة التفاصيل مع إظهار الهوية.\n-# **نحن بانتظار استكمال المتطلبات.**",
    "review_wait": "أهلاً بك، جاري مراجعة طلبك بكل دقة. نرجو التحلي بالصبر.\n\n-# **فريق الإدارة في خدمتكم**",
    "ban_evidence": "نرجو الانتظار قليلاً ريثما يتم جلب تفاصيل التوثيق والأدلة الخاصة بالخادم."
}

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
            return "❌ التوكن غير صالح أو منتهي الصلاحية (401 Unauthorized)"
        else:
            return f"⚠️ استجابة غير متوقعة من الديسكورد (كود: {res.status_code})"
    except Exception as e:
        return f"❌ خطأ في الاتصال بالشبكة فحص التوكن: {str(e)}"

def background_token_watcher(username):
    while user_sessions[username]["running"] and not user_sessions[username]["banned_secure"]:
        time.sleep(1800)
        if not user_sessions[username]["running"]:
            break
        token = user_sessions[username]["token"]
        if token:
            try:
                headers = get_secure_headers(token)
                res = requests.get("https://discord.com/api/v9/users/@me", headers=headers, timeout=5)
                if res.status_code == 401:
                    with state_lock:
                        user_sessions[username]["running"] = False
                        user_sessions[username]["banned_secure"] = True
                        user_sessions[username]["logs"].append("🚨 [Watchdog] تم رصد انتهاء صلاحية التوكن، إيقاف الحساب حفاظاً عليه.")
                        security_audit_logs.insert(0, f"⚠️ نظام الحماية: تم إيقاف الحساب <b>{username}</b> بسبب حالة التوكن.")
                    break
            except Exception:
                pass

def safe_post(token, url, payload, current_speed, username=None):
    try:
        headers = get_secure_headers(token)
        time.sleep(current_speed)
        
        res = requests.post(url, json=payload, headers=headers, timeout=5)
        if res.status_code == 429:
            if username and username in user_sessions:
                with state_lock:
                    user_sessions[username]["rate_limit_errors"] += 1
                    if user_sessions[username]["rate_limit_errors"] >= 3:
                        user_sessions[username]["running"] = False
                        user_sessions[username]["banned_secure"] = True
                        user_sessions[username]["logs"].append("🚨 [Elite Shield] تم تجميد الحساب مؤقتاً لتفادي الباند النهائي.")
                        security_audit_logs.insert(0, f"⚠️ حماية النخبة: تم إيقاف <b>{username}</b> احترازياً.")
            retry_after = res.json().get("retry_after", current_speed + 1.0)
            time.sleep(retry_after + 0.5)
            return safe_post(token, url, payload, current_speed, username)
        return res
    except Exception:
        return None

def process_ticket(username, token, ch_id, name):
    with state_lock:
        session_data = user_sessions[username]
        if not session_data["running"] or session_data["banned_secure"]:
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
        if ch_id in active_tickets:
            return
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
            
            global master_global_audit
            audit_entry = f"[{username}] استلم تكت <b>#{name}</b> | <a href='{ticket_url}' target='_blank'>رابط مباشر</a>"
            master_global_audit.insert(0, audit_entry)
            if len(master_global_audit) > 50:
                master_global_audit.pop()
            
            alert_payload = {"content": f"💎 **{username}** قام باستلام تكت جديد:\n• اسم التكت: `#{name}`\n• الرابط: {ticket_url}"}
            safe_post(token, f"{API}/{DEFAULT_ALERT_CHANNEL}/messages", alert_payload, 0.5, username)

            if session_data["count"] < session_data["max_tickets"]:
                session_data["count"] += 1
                session_data["total_lifetime"] += 1
                session_data["logs"].append(f"{log_text} (العدد: {session_data['count']}/{session_data['max_tickets']})")
                if session_data["count"] >= session_data["max_tickets"]:
                    session_data["running"] = False
                    session_data["logs"].append("🛑 تم بلوغ الحد الأقصى المحدد للتكتات، توقف النظام.")
        else:
            status_code = res.status_code if res else "خطأ اتصال"
            session_data["logs"].append(f"<span style='color: #f43f5e;'>❌ تعذر استلام التكت #{name} (كود الحالة: {status_code})</span>")
        
    with state_lock:
        if ch_id in active_tickets:
            active_tickets.remove(ch_id)

def run_discord_bot(username):
    token = user_sessions[username]["token"]
    user_sessions[username]["logs"].append("🚀 [Elite System] تم تفعيل نظام الاستلام والدرع السيبراني...")
    
    threading.Thread(target=background_token_watcher, args=(username,), daemon=True).start()

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
                    if time.time() - created_at > 90:
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
                "properties": {
                    "os": "iOS",
                    "browser": "Discord Client",
                    "device": "iPhone 13, pro, max",
                    "system_version": "17.5"
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

PANEL_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>لوحة القيادة المركزية - Elite Operations</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap');
        body { background: linear-gradient(135deg, #07090e 0%, #020407 100%); color: #e2e8f0; font-family: 'Cairo', sans-serif; text-align: center; margin: 0; padding: 15px; min-height: 100vh; }
        .card { background: linear-gradient(180deg, #101622 0%, #090d16 100%); max-width: 440px; margin: 0 auto; padding: 24px; border-radius: 20px; border: 1px solid #1e293b; box-shadow: 0 25px 60px rgba(0,0,0,0.8), 0 0 40px rgba(59, 130, 246, 0.15); }
        .logo-glow { width: 80px; height: 80px; margin: 0 auto 12px auto; background: linear-gradient(135deg, #3b82f6, #1d4ed8); border-radius: 24px; display: flex; align-items: center; justify-content: center; font-size: 34px; box-shadow: 0 0 25px rgba(59, 130, 246, 0.5); border: 2px solid #60a5fa; }
        h1 { color: #f8fafc; font-size: 21px; margin-bottom: 2px; font-weight: 900; letter-spacing: 0.5px; }
        .user-tag { color: #38bdf8; font-size: 13px; margin-bottom: 14px; font-weight: 700; background: #0c1527; display: inline-block; padding: 4px 12px; border-radius: 20px; border: 1px solid #1d4ed8; }
        .speed-badge { background: #0b111e; border: 1px solid #1e293b; padding: 11px; border-radius: 12px; font-size: 12px; color: #94a3b8; margin-bottom: 8px; font-weight: 600; }
        .speed-badge b { color: #38bdf8; }
        .stats-badge { background: #0b111e; border: 1px solid #1e293b; padding: 8px; border-radius: 10px; font-size: 11px; color: #cbd5e1; margin-bottom: 14px; }
        .stats-badge b { color: #34d399; }
        .btn { display: block; width: 100%; padding: 12px; margin: 9px 0; font-size: 14px; font-weight: 700; border: none; border-radius: 12px; cursor: pointer; text-decoration: none; transition: all 0.25s ease; font-family: 'Cairo', sans-serif; }
        .btn:hover { transform: translateY(-2px); filter: brightness(1.1); }
        .btn-start { background: linear-gradient(135deg, #10b981, #059669); color: white; box-shadow: 0 4px 20px rgba(16, 185, 129, 0.35); }
        .btn-stop { background: linear-gradient(135deg, #ef4444, #dc2626); color: white; box-shadow: 0 4px 20px rgba(239, 68, 68, 0.35); }
        .btn-cooldown-on { background: linear-gradient(135deg, #2563eb, #1d4ed8); color: white; }
        .btn-cooldown-off { background: linear-gradient(135deg, #131b2e, #1e293b); color: #94a3b8; border: 1px solid #334155; }
        .btn-silent-on { background: linear-gradient(135deg, #d97706, #b45309); color: white; }
        .btn-silent-off { background: linear-gradient(135deg, #131b2e, #1e293b); color: #94a3b8; border: 1px solid #334155; }
        .btn-reset { background: linear-gradient(135deg, #d97706, #b45309); color: white; }
        .btn-clear { background: linear-gradient(135deg, #1e293b, #0f172a); color: #f87171; border: 1px solid #334155; }
        .btn-token { background: linear-gradient(135deg, #0ea5e9, #0284c7); color: white; }
        .btn-emergency { background: linear-gradient(135deg, #7f1d1d, #450a0a); color: #fecaca; border: 1px solid #ef4444; }
        .config-section { text-align: right; margin-top: 12px; background: #0b111e; padding: 12px; border-radius: 14px; border: 1px solid #1e293b; }
        .config-title { color: #38bdf8; font-size: 11px; margin-bottom: 5px; font-weight: 700; }
        input[type="text"], input[type="password"], input[type="number"], textarea, select { width: 100%; padding: 9px; background: #05080d; border: 1px solid #1e293b; color: #f1f5f9; border-radius: 10px; box-sizing: border-box; font-size: 11px; text-align: center; outline: none; margin-bottom: 6px; font-family: 'Cairo', sans-serif; }
        input:focus, textarea:focus, select:focus { border-color: #3b82f6; }
        textarea { height: 60px; text-align: right; resize: none; }
        .btn-save { width: 100%; padding: 9px; margin-top: 4px; background: linear-gradient(135deg, #f59e0b, #d97706); color: white; border: none; border-radius: 10px; font-weight: 700; cursor: pointer; font-size: 11px; font-family: 'Cairo', sans-serif; }
        .log-title { color: #38bdf8; font-size: 11px; margin-top: 12px; text-align: right; font-weight: 700; }
        .log-box { background: #05080d; border: 1px solid #1e293b; border-radius: 11px; padding: 9px; height: 105px; overflow-y: auto; text-align: right; font-size: 10px; color: #94a3b8; margin-top: 5px; box-shadow: inset 0 2px 6px rgba(0,0,0,0.8); }
        .log-box a { color: #38bdf8; text-decoration: underline; font-weight: 600; }
        .logout-btn { color: #f43f5e; font-size: 12px; display: block; margin-top: 16px; text-decoration: none; font-weight: 700; transition: 0.2s; }
        .logout-btn:hover { color: #fb7185; }
        .section-box { border: 1px dashed #334155; border-radius: 14px; padding: 12px; margin-top: 14px; background: #0b111e; text-align: right; }
    </style>
    <script>
        function confirmReset() { return confirm("هل أنت متأكد من إعادة تعيين العدادات والأخطاء؟"); }
        function confirmEmergency() { return confirm("⚠️ تحذير: هل تريد إيقاف كافة العمليات لكل الحسابات حالاً؟"); }
    </script>
</head>
<body>
    <div class="card">
        <div class="logo-glow">🛡️</div>
        <h1>منظومة الإدارة العليا</h1>
        <div class="user-tag">الحساب النشط: {{ username }}</div>
        
        <div class="speed-badge">تم إنجاز: <b>{{ count }}/{{ max_tickets }}</b> | سرعة الاستجابة: <b>{{ speed }}ث</b></div>
        <div class="stats-badge">📊 الإجمالي التراكمي: <b>{{ total_lifetime }} تكت</b> | الأخطاء: <b>{{ rate_errors }}</b></div>
        
        <form action="/toggle" method="post">
            {% if running %}
                <button type="submit" class="btn btn-stop">إيقاف النظام 🛑</button>
            {% else %}
                <button type="submit" class="btn btn-start">تشغيل النظام الآلي 🚀</button>
            {% endif %}
        </form>

        <form action="/toggle_cooldown" method="post">
            {% if cooldown_mode %}
                <button type="submit" class="btn btn-cooldown-on">🛡️ نظام التخطي الذكي (مفعل)</button>
            {% else %}
                <button type="submit" class="btn btn-cooldown-off">🛡️ نظام التخطي الذكي (معطل)</button>
            {% endif %}
        </form>

        <form action="/toggle_silent" method="post">
            {% if silent_mode %}
                <button type="submit" class="btn btn-silent-on">🔇 الوضع الصامت (مفعل)</button>
            {% else %}
                <button type="submit" class="btn btn-silent-off">🔊 الوضع الصامت (معطل)</button>
            {% endif %}
        </form>

        <div class="config-section">
            <form action="/update_settings" method="post">
                <div class="config-title">الحد الأقصى للتكتات:</div>
                <input type="number" name="max_tickets" value="{{ max_tickets }}" min="1" max="100">
                
                <div class="config-title">ضبط سرعة الاستجابة بالثواني:</div>
                <input type="number" step="0.1" name="custom_speed" value="{{ speed }}" min="0.5" max="10.0" style="margin-bottom: 6px;">

                <div class="config-title">قالب الرد التلقائي:</div>
                <select name="reply_template" style="margin-bottom: 6px;">
                    <option value="default" {% if reply_template == 'default' %}selected{% endif %}>النص المخصص (الأساسي)</option>
                    <option value="evidence_req" {% if reply_template == 'evidence_req' %}selected{% endif %}>طلب أدلة الشكاوى والمقاطع</option>
                    <option value="review_wait" {% if reply_template == 'review_wait' %}selected{% endif %}>جاري مراجعة الطلب (تحلى بالصبر)</option>
                    <option value="ban_evidence" {% if reply_template == 'ban_evidence' %}selected{% endif %}>طلب تفاصيل الحظر للإدارة</option>
                </select>

                <div class="config-title">تخصيص نص الرد يدوياً:</div>
                <textarea name="custom_msg">{{ message }}</textarea>
                <button type="submit" class="btn-save">حفظ الإعدادات 💾</button>
            </form>
        </div>

        <form action="/reset_all" method="post" onsubmit="return confirmReset();"><button type="submit" class="btn btn-reset">🗑️ تصفير العدادات والأخطاء</button></form>
        <form action="/clear_logs" method="post"><button type="submit" class="btn btn-clear">🧹 مسح السجل الحالي</button></form>
        
        <div style="display: flex; gap: 8px; margin: 9px 0;">
            <form action="/token" method="get" style="flex:1;"><button type="submit" class="btn btn-token" style="margin:0;">🔑 تعديل التوكن</button></form>
            <form action="/check_token" method="post" style="flex:1;"><button type="submit" class="btn" style="margin:0; background: linear-gradient(135deg, #059669, #047857);">🔍 فحص التوكن</button></form>
        </div>

        {% if username == "Saif" or username == "Marshall" %}
        <div class="section-box">
            <div class="config-title" style="color: #f59e0b; font-size: 12px; margin-bottom: 8px;">👑 لوحة القيادة العليا والتحكم الإداري:</div>
            <form action="/emergency_stop" method="post" onsubmit="return confirmEmergency();" style="margin-bottom: 8px;"><button type="submit" class="btn btn-emergency">🚨 طوارئ عامة (إيقاف كافة الحسابات)</button></form>
            <form action="/create_account" method="post" style="background: #05080d; padding: 9px; border-radius: 10px; border: 1px solid #1e293b; margin-bottom: 8px;">
                <div class="config-title">➕ إضافة حساب جديد للمنظومة:</div>
                <input type="text" name="new_user" placeholder="اسم المستخدم" required>
                <input type="password" name="new_pass" placeholder="كلمة المرور" required>
                <textarea name="new_token" placeholder="توكن الحساب..." style="height: 45px;" required></textarea>
                <button type="submit" class="btn-save" style="background: linear-gradient(135deg, #10b981, #059669);">حفظ الحساب الجديد 🚀</button>
            </form>
            <form action="/manage_member_action" method="post" style="background: #05080d; padding: 9px; border-radius: 10px; border: 1px solid #1e293b; margin-bottom: 8px;">
                <div class="config-title">👥 إدارة الأفراد والأعضاء:</div>
                <select name="target_member" style="margin-bottom: 6px;">
                    {% for member in all_users %}<option value="{{ member }}">{{ member }}</option>{% endfor %}
                </select>
                <div style="display: flex; gap: 6px;">
                    <button type="submit" name="action_type" value="stats" class="btn-save" style="background: #2563eb; flex: 1;">الإحصائيات 📊</button>
                    <button type="submit" name="action_type" value="kick" class="btn-save" style="background: #dc2626; flex: 1;" onclick="return confirm('هل تريد طرد هذا الحساب نهائياً؟');">حذف 🚪</button>
                </div>
            </form>
            {% if selected_member_info %}<div style="margin-top: 6px; font-size: 10px; color: #34d399; font-weight: 700; background: #05080d; padding: 7px; border-radius: 8px; border: 1px solid #1e293b;">{{ selected_member_info | safe }}</div>{% endif %}
            <div class="config-title" style="color: #38bdf8; margin-top: 10px;">🛡️ السجل الأمني المباشر:</div>
            <div class="log-box" style="height: 80px; border-color: #1e3a8a;">
                {% for sec in security_logs %}<div>• {{ sec | safe }}</div>{% else %}<div style="color: #555; text-align: center; margin-top: 22px;">لا توجد تنبيهات أمنية حالية...</div>{% endfor %}
            </div>
            <div class="config-title" style="color: #38bdf8; margin-top: 10px;">🌐 سجل العمليات العام:</div>
            <div class="log-box" style="height: 95px; border-color: #1e3a8a;">
                {% for item in global_audit %}<div>• {{ item | safe }}</div>{% else %}<div style="color: #555; text-align: center; margin-top: 28px;">لا توجد عمليات مسجلة...</div>{% endfor %}
            </div>
        </div>
        {% endif %}

        <div class="log-title">سجل العمليات وحالة النظام اللحظية:</div>
        <div class="log-box">
            {% for item in logs %}<div>• {{ item | safe }}</div>{% else %}<div style="color: #555; text-align: center; margin-top: 30px;">النظام جاهز وفي انتظار التكتات...</div>{% endfor %}
        </div>
        <a href="/logout" class="logout-btn">تسجيل خروج من الحساب 🚪</a>
    </div>
</body>
</html>
"""

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>تسجيل الدخول الآمن - Elite Operations</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap');
        body { background: linear-gradient(135deg, #05070a 0%, #010204 100%); color: #f8fafc; font-family: 'Cairo', sans-serif; text-align: center; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: linear-gradient(145deg, #0f1523 0%, #080b12 100%); width: 350px; padding: 28px; border-radius: 22px; border: 1px solid #1e293b; box-shadow: 0 30px 60px rgba(0,0,0,0.9), 0 0 35px rgba(59, 130, 246, 0.2); }
        .login-logo { width: 70px; height: 70px; margin: 0 auto 15px auto; background: linear-gradient(135deg, #3b82f6, #1d4ed8); border-radius: 20px; display: flex; align-items: center; justify-content: center; font-size: 30px; box-shadow: 0 0 20px rgba(59, 130, 246, 0.5); border: 2px solid #60a5fa; }
        input { width: 100%; padding: 12px; margin: 10px 0; background: #05080d; border: 1px solid #1e293b; color: #f8fafc; border-radius: 11px; text-align: center; box-sizing: border-box; outline: none; font-size: 13px; font-family: 'Cairo', sans-serif; transition: 0.3s; }
        input:focus { border-color: #3b82f6; box-shadow: 0 0 10px rgba(59, 130, 246, 0.3); }
        .btn { width: 100%; padding: 13px; margin-top: 14px; background: linear-gradient(135deg, #3b82f6, #1d4ed8); color: #fff; border: none; border-radius: 11px; font-weight: 700; cursor: pointer; font-size: 14px; font-family: 'Cairo', sans-serif; box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4); transition: 0.2s; }
        .btn:hover { transform: translateY(-2px); filter: brightness(1.1); }
    </style>
</head>
<body>
    <div class="card">
        <div class="login-logo">🛡️</div>
        <h2 style="color: #f8fafc; margin-top: 0; font-size: 19px; font-weight: 900;">بوابة الدخول الآمنة</h2>
        <p style="color: #64748b; font-size: 11px; margin-bottom: 18px;">منظومة إدارة التكتات المتقدمة</p>
        <form method="POST">
            <input type="text" name="username" placeholder="اسم المستخدم (Username)" required>
            <input type="password" name="password" placeholder="كلمة المرور (Password)" required>
            <button type="submit" class="btn">تسجيل الدخول 🚀</button>
        </form>
    </div>
</body>
</html>
"""

TOKEN_HTML = """
<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>تعديل التوكن</title>
<style>@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');body{background:#020407;color:#fff;font-family:'Cairo',sans-serif;text-align:center;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}.card{background:#0f1523;width:350px;padding:25px;border-radius:18px;border:1px solid #1e293b;box-shadow:0 20px 40px rgba(0,0,0,0.9)}textarea{width:100%;height:80px;background:#05080d;border:1px solid #1e293b;color:#fff;border-radius:10px;text-align:center;resize:none;box-sizing:border-box;font-size:11px;outline:none;font-family:'Cairo',sans-serif;padding:8px}.btn{width:100%;padding:12px;margin-top:12px;background:linear-gradient(135deg, #0ea5e9, #0284c7);color:#fff;border:none;border-radius:10px;font-weight:700;cursor:pointer;font-family:'Cairo',sans-serif;}</style></head>
<body><div class="card"><h2 style="color:#38bdf8; margin-top:0; font-size:17px;">تحديث توكن الحساب</h2><form method="POST"><textarea name="token" placeholder="الصق التوكن هنا..." required></textarea><button type="submit" class="btn">حفظ التوكن الجديد</button></form></div></body></html>
"""

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username in USERS and USERS[username] == password:
            if username in user_sessions and user_sessions[username].get("kicked", False):
                return redirect(url_for('login'))
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
        user_sessions[session['user']]["logs"].append("🔑 تم تحديث توكن الحساب بنجاح.")
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
    selected_member_info = session.get('selected_member_info', None)
    return render_template_string(
        PANEL_HTML, username=usr, running=data["running"], speed=data["speed"], 
        message=data["message"], reply_template=data.get("reply_template", "default"),
        logs=data["logs"], count=data["count"], total_lifetime=data["total_lifetime"], 
        max_tickets=data["max_tickets"], cooldown_mode=data["cooldown_mode"], 
        silent_mode=data["silent_mode"], rate_errors=data["rate_limit_errors"], 
        all_users=list(user_sessions.keys()), selected_member_info=selected_member_info, 
        global_audit=master_global_audit, security_logs=security_audit_logs
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

@app.route('/emergency_stop', methods=['POST'])
def emergency_stop():
    if 'user' in session and (session['user'] == "Saif" or session['user'] == "Marshall"):
        for u in user_sessions:
            user_sessions[u]["running"] = False
    return redirect(url_for('panel'))

@app.route('/create_account', methods=['POST'])
def create_account():
    if 'user' in session and (session['user'] == "Saif" or session['user'] == "Marshall"):
        new_u = request.form.get('new_user', '').strip()
        new_p = request.form.get('new_pass', '').strip()
        new_t = request.form.get('new_token', '').strip()
        if new_u and new_p:
            USERS[new_u] = new_p
            user_sessions[new_u] = {
                "running": False, "speed": 1.5, "thread": None, "token": new_t,
                "message": f"أهلاً بك، معك {new_u} الإدارة العليا.",
                "reply_template": "default", "logs": [], "count": 0, "total_lifetime": 0, 
                "max_tickets": 10, "cooldown_mode": False, "skip_next": False, 
                "silent_mode": False, "rate_limit_errors": 0, "banned_secure": False,
                "last_sent_text": "", "last_sent_time": 0
            }
            LOG_CHANNELS[new_u] = DEFAULT_ALERT_CHANNEL
    return redirect(url_for('panel'))

@app.route('/manage_member_action', methods=['POST'])
def manage_member_action():
    if 'user' in session and (session['user'] == "Saif" or session['user'] == "Marshall"):
        target = request.form.get('target_member')
        action = request.form.get('action_type')
        if target in user_sessions:
            if action == 'stats':
                d = user_sessions[target]
                session['selected_member_info'] = f"({target}): إجمالي الإنجاز <b>{d['total_lifetime']}</b>، الحالي <b>{d['count']}/{d['max_tickets']}</b>"
            elif action == 'kick' and target != "Saif" and target != "Marshall":
                user_sessions[target]["running"] = False
                user_sessions[target]["kicked"] = True
                user_sessions[target]["token"] = ""
    return redirect(url_for('panel'))

@app.route('/update_settings', methods=['POST'])
def update_settings():
    if 'user' in session:
        usr = session['user']
        new_msg = request.form.get('custom_msg', '').strip()
        new_tpl = request.form.get('reply_template', 'default')
        user_sessions[usr]["reply_template"] = new_tpl
        try:
            new_max = int(request.form.get('max_tickets', 10))
            if new_max > 0: user_sessions[usr]["max_tickets"] = new_max
        except ValueError:
            pass
        try:
            new_speed = float(request.form.get('custom_speed', 1.5))
            if new_speed >= 0.5: user_sessions[usr]["speed"] = round(new_speed, 1)
        except ValueError:
            pass
        if new_msg: user_sessions[usr]["message"] = new_msg
    return redirect(url_for('panel'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('selected_member_info', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
