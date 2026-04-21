#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════════════════════════════════════════╗
║   🔥 ROXZ DDOS BOT - ULTIMATE TOXIC HINDI EDITION 🔥                                          ║
║   VERSION: 12.0 (FULL TOXIC HINDI + GAALI)                                                   ║
║   DEVELOPER: @Roxz_gaming                                                                     ║
╚═══════════════════════════════════════════════════════════════════════════════════════════════╝
"""

import telebot
import requests
import time
import threading
import json
import os
import random
import string
import re
import secrets
import hashlib
from datetime import datetime, timedelta
from collections import defaultdict
from pymongo import MongoClient
from urllib.parse import quote_plus
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import qrcode
from io import BytesIO

# ========== CONFIGURATION ==========
BOT_TOKEN = "7914185815:AAG_kgZVatEmQQcih3BrS1XoOUuw1m9_bLI"
ADMIN_ID = ["8487946379", "7352008650"]

# API Configuration
API_URL = ""
API_KEY = ""

# Default Settings
DEFAULT_USER_CONCURRENT = 2
DEFAULT_USER_ATTACK_TIME = 300
DEFAULT_GROUP_CONCURRENT = 1
DEFAULT_GROUP_ATTACK_TIME = 60

# ========== 🔥 TOXIC HINDI RESPONSES 🔥 ==========
# Attack Start Messages
TOXIC_START = [
    "🔥 **बेटे {target} की माँ चोद दी 🔥**\n💀 अब रोते हुए जा अपनी मम्मी को बुला 💀",
    "💀 **{target} का सर्वर रेंड हो गया 💀**\n🎯 बच्चे अब आँखें निकाल ले 🎯",
    "⚡ **{target} की तो औकात ही नहीं ⚡**\n🍼 दूध पीके सो जा नालायक 🍼",
    "🎯 **{target} का नेटवर्क पिघला दिया 🎯**\n🔥 जल के राख हो जा 🔥",
    "💅 **{target} तेरा कुछ नहीं हो सकता 💅**\n🤡 वापस जा लूडो खेल 🤡",
]

# Attack Success Messages
TOXIC_SUCCESS = [
    "💀💀 **{target} का सर्वर ख़तम हो गया भाई** 💀💀\n🔥 अब जाके रो माँ के आँचल में 🔥",
    "🎯🎯 **बेटे {target} की औकात दिखा दी** 🎯🎯\n🍼 दूध की बोतल लेके आ जा 🍼",
    "⚡⚡ **{target} का नेटवर्क फूक दिया** ⚡⚡\n💀 अब कल तक इंटरनेट भूल जा 💀",
    "🔥🔥 **{target} तेरा तो कचूमर हो गया** 🔥🔥\n🤡 कौन था रे जोश दिखाने वाला 🤡",
    "💀💀 **{target} की माँ रो रही है अब** 💀💀\n🎯 ले ले अपनी हार और निकल 🎯",
]

# Error Messages
TOXIC_ERROR = [
    "🤡 **कमबख्त सही से कमांड तो डाल** 🤡\n💀 गधा है क्या ? 💀",
    "💀 **बच्चे पहले कमांड तो सीख ले** 💀\n🍼 फिर आकर बात करियो 🍼",
    "🎯 **तेरी औकात नहीं इस बोट को चलाने की** 🎯\n🤡 चुपचाप बैठ जा 🤡",
    "🔥 **भाई कमांड गलत डाली है तूने** 🔥\n💅 सीख ले पहले फिर आना 💅",
    "⚡ **चुतिया है क्या ? सही से डाल** ⚡\n🍼 बच्चा हो क्या 🍼",
]

# Cooldown Messages
TOXIC_COOLDOWN = [
    "⏰ **{time} सेकंड इंतज़ार कर ले स्पैमर** ⏰\n💀 वरना बैन कर दूंगा 💀",
    "🍼 **रुक जा {time} सेकंड बाद करियो** 🍼\n🎯 इतनी जल्दी क्या है मरने की 🎯",
    "💀 **{time} सेकंड की कोल्डाउन है गधे** 💀\n🔥 सब तू अकेला नहीं है यहाँ 🔥",
    "🤡 **इतनी जल्दी कहाँ जा रहा है {time} सेकंड रुक** 🤡\n⚡ शांत बैठ ⚡",
    "🎯 **बच्चे पहले {time} सेकंड टोटल** 🎯\n💀 फिर मार लियो अटैक 💀",
]

# Unauthorized Messages
TOXIC_UNAUTH = [
    "🤡 **पहले पैसे दे फिर अटैक कर** 🤡\n💰 /buy या /redeem KEY कर ले 💰",
    "💀 **तेरी औकात नहीं चलाने की** 💀\n🍼 जा के खिलौने से खेल 🍼",
    "🎯 **कमबख्त प्लान लेले पहले** 🎯\n🔥 वरना निकल यहाँ से 🔥",
    "⚡ **बिना पैसे के अटैक नहीं होता बच्चे** ⚡\n💅 सब चोरी नहीं चलता 💅",
    "🍼 **दूध पी बच्चे और सो जा** 🍼\n🤡 यहाँ मत आ बेकार में 🤡",
]

# Group Not Approved
TOXIC_GROUP = [
    "👥 **इस ग्रुप की मा चोदी गयी है अभी** 👥\n💀 एडमिन से लगवा पहले 💀",
    "🤡 **ग्रुप अप्प्रूव नहीं है बेटे** 🤡\n🔥 जा के @Roxz_gaming से बात कर 🔥",
    "💀 **तू कौन होता है बिना अप्प्रूवल के अटैक करने वाला** 💀\n🎯 पहले ग्रुप एड करा 🎯",
]

# Limit Reached
TOXIC_LIMIT = [
    "📊 **तेरे {active}/{limit} स्लॉट भरे पड़े हैं** 📊\n⏰ पहले खाली होने दे फिर कर ⏰",
    "💀 **इतनी जल्दी क्या है पहले वाला खतम होने दे** 💀\n🍼 धैर्य रख बच्चे 🍼",
]

# Payment Messages
TOXIC_PAYMENT = [
    "💰 **पहले पैसे डाल फिर रो** 💰\n🤡 नहीं तो चुप बैठ 🤡",
    "💀 **भीख माँगने आया है क्या ? पैसे दे** 💀\n🔥 तेरे बाप का नहीं चल रहा 🔥",
]

# ========== PRICE PLANS ==========
PLANS = {
    "basic": {"name": "🔥 BASIC", "price": 199, "days": 1, "concurrent": 3, "time": 300, "emoji": "🔥"},
    "pro": {"name": "💎 PRO", "price": 499, "days": 3, "concurrent": 5, "time": 600, "emoji": "💎"},
    "elite": {"name": "👑 ELITE", "price": 799, "days": 7, "concurrent": 8, "time": 900, "emoji": "👑"},
    "god": {"name": "⚡ GOD", "price": 2499, "days": 30, "concurrent": 10, "time": 1200, "emoji": "⚡"}
}

# ========== MONGODB ==========
MONGO_USER = "mohitrao83076_db_user"
MONGO_PASS = quote_plus("LugF1xwlenkWRE1F")
MONGO_URI = f"mongodb+srv://{MONGO_USER}:{MONGO_PASS}@monster.ydmmckl.mongodb.net/?retryWrites=true&w=majority&appName=MONSTER"

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    print("✅ MongoDB Connected!")
    db = client["roxz_bot_mega"]
except:
    print("⚠️ MongoDB offline - using local storage")
    db = None

# Collections
if db:
    users_collection = db["users"]
    keys_collection = db["keys"]
    groups_collection = db["groups"]
    settings_collection = db["settings"]
    attacks_collection = db["attacks"]
    payments_collection = db["payments"]
else:
    class DummyCollection:
        def find_one(self, *args, **kwargs): return None
        def insert_one(self, *args, **kwargs): return None
        def update_one(self, *args, **kwargs): return None
        def delete_many(self, *args, **kwargs): return None
        def find(self, *args, **kwargs): return []
        def count_documents(self, *args, **kwargs): return 0
        def aggregate(self, *args, **kwargs): return []
    users_collection = keys_collection = groups_collection = settings_collection = attacks_collection = payments_collection = DummyCollection()

# ========== DATA STRUCTURES ==========
active_attacks = {}
active_group_attacks = {}
group_attack_targets = defaultdict(set)
cooldown = {}
group_cooldown = {}
pending_requests = {}
pending_qr_setup = {}
attack_logs = []

# ========== LOAD DATA ==========
def load_users():
    data = users_collection.find_one({"_id": "users"})
    if not data:
        data = {"_id": "users", "users": ADMIN_ID.copy(), "resellers": [], "banned": []}
        if db: users_collection.insert_one(data)
    return data

def load_keys():
    if not db: return {}
    keys = {}
    for k in keys_collection.find():
        keys[k["key"]] = {k: v for k, v in k.items() if k != "_id"}
    return keys

def save_users(data):
    if db: users_collection.update_one({"_id": "users"}, {"$set": data}, upsert=True)

def save_keys(keys_data):
    if not db: return
    keys_collection.delete_many({})
    for key, info in keys_data.items():
        keys_collection.insert_one({"key": key, **info})

def load_groups():
    if not db: return {}
    groups = {}
    for g in groups_collection.find():
        groups[g["group_id"]] = {
            "attack_time": g.get("attack_time", DEFAULT_GROUP_ATTACK_TIME),
            "concurrent": g.get("concurrent", DEFAULT_GROUP_CONCURRENT),
            "added_by": g.get("added_by"), "added_at": g.get("added_at")
        }
    return groups

def load_settings():
    if not db: return {"upi_id": "roxz@axl", "qr_code": None, "qr_code_id": None, "user_concurrent": DEFAULT_USER_CONCURRENT, "user_attack_time": DEFAULT_USER_ATTACK_TIME}
    s = settings_collection.find_one({"_id": "settings"})
    if not s:
        s = {"_id": "settings", "upi_id": "roxz@axl", "qr_code": None, "qr_code_id": None, "user_concurrent": DEFAULT_USER_CONCURRENT, "user_attack_time": DEFAULT_USER_ATTACK_TIME}
        settings_collection.insert_one(s)
    return s

def save_settings(s):
    if db: settings_collection.update_one({"_id": "settings"}, {"$set": s}, upsert=True)

users_data = load_users()
users = users_data["users"]
resellers = users_data.get("resellers", [])
banned_users = users_data.get("banned", [])
keys_data = load_keys()
groups = load_groups()
settings = load_settings()

bot = telebot.TeleBot(BOT_TOKEN)

# ========== KEY SYSTEM ==========
def generate_secure_key():
    chars = string.ascii_uppercase + string.digits
    parts = [''.join(secrets.choice(chars) for _ in range(4)) for _ in range(4)]
    return f"ROXZ-{parts[0]}-{parts[1]}-{parts[2]}-{parts[3]}"

# ========== TOXIC HELPER ==========
def toxic_start_msg(target):
    return random.choice(TOXIC_START).format(target=target)

def toxic_success_msg(target):
    return random.choice(TOXIC_SUCCESS).format(target=target)

def toxic_error_msg():
    return random.choice(TOXIC_ERROR)

def toxic_cooldown_msg(sec):
    return random.choice(TOXIC_COOLDOWN).format(time=sec)

def toxic_unauth_msg():
    return random.choice(TOXIC_UNAUTH)

def toxic_group_msg():
    return random.choice(TOXIC_GROUP)

def toxic_limit_msg(active, limit):
    return random.choice(TOXIC_LIMIT).format(active=active, limit=limit)

# ========== SLIDE BUTTONS ==========
def get_user_slide_keyboard(uid=None):
    keyboard = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    keyboard.add(KeyboardButton("💀 ATTACK"), KeyboardButton("📊 STATUS"))
    keyboard.add(KeyboardButton("💰 BUY PLAN"), KeyboardButton("👤 PROFILE"))
    keyboard.add(KeyboardButton("📜 HISTORY"), KeyboardButton("🏆 TOP"))
    keyboard.add(KeyboardButton("⚡ METHODS"), KeyboardButton("🔑 REDEEM"))
    keyboard.add(KeyboardButton("❓ HELP"), KeyboardButton("🏓 PING"))
    
    if uid and uid in ADMIN_ID:
        keyboard.add(KeyboardButton("👑 ADMIN PANEL"))
    
    return keyboard

def get_admin_slide_keyboard():
    keyboard = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    keyboard.add(KeyboardButton("👤 ADD USER"), KeyboardButton("➖ REMOVE USER"))
    keyboard.add(KeyboardButton("🚫 BAN USER"), KeyboardButton("✅ UNBAN USER"))
    keyboard.add(KeyboardButton("👑 ADD RESELLER"), KeyboardButton("➖ REMOVE RESELLER"))
    keyboard.add(KeyboardButton("👥 ADD GROUP"), KeyboardButton("👥 REMOVE GROUP"))
    keyboard.add(KeyboardButton("⏱️ SET GROUP TIME"), KeyboardButton("⚡ SET GROUP CONCURRENT"))
    keyboard.add(KeyboardButton("🗑️ CLEAR GROUP IPS"), KeyboardButton("📋 LIST GROUPS"))
    keyboard.add(KeyboardButton("🔑 GEN KEY (30D)"), KeyboardButton("🔑 GEN KEY (5H)"))
    keyboard.add(KeyboardButton("🗑️ REMOVE KEY"), KeyboardButton("📋 MY KEYS"))
    keyboard.add(KeyboardButton("⏱️ SET USER TIME"), KeyboardButton("⚡ SET USER CONCURRENT"))
    keyboard.add(KeyboardButton("💳 SET UPI"), KeyboardButton("📱 SET QR CODE"))
    keyboard.add(KeyboardButton("💰 PAYMENT REQUESTS"), KeyboardButton("📢 BROADCAST"))
    keyboard.add(KeyboardButton("📊 BOT STATS"), KeyboardButton("📋 ALL USERS"))
    keyboard.add(KeyboardButton("🔙 MAIN MENU"))
    return keyboard

def get_back_keyboard():
    keyboard = ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    keyboard.add(KeyboardButton("🔙 MAIN MENU"))
    return keyboard

def get_plans_inline():
    kb = InlineKeyboardMarkup(row_width=1)
    for pid, p in PLANS.items():
        kb.add(InlineKeyboardButton(f"{p['emoji']} {p['name']} - ₹{p['price']} ({p['days']} Days)", callback_data=f"buy_{pid}"))
    kb.add(InlineKeyboardButton("🔙 BACK", callback_data="back_main"))
    return kb

# ========== HELPER FUNCTIONS ==========
def check_user_expiry(uid):
    now = time.time()
    for k, v in keys_data.items():
        if v.get("used_by") == uid and v.get("used") and now < v["expires_at"]:
            return True
    return False

def get_remaining(uid):
    now = time.time()
    for k, v in keys_data.items():
        if v.get("used_by") == uid and v.get("used") and now < v["expires_at"]:
            rem = v["expires_at"] - now
            return int(rem // 86400), int((rem % 86400) // 3600)
    return 0, 0

def get_attack_count(uid=None):
    if uid:
        if db: return attacks_collection.count_documents({"user_id": uid})
        return len([a for a in attack_logs if a["user_id"] == uid])
    else:
        if db: return attacks_collection.count_documents({})
        return len(attack_logs)

def get_rank(attacks):
    if attacks >= 10000: return "👑 गॉड ऑफ डिस्ट्रक्शन"
    elif attacks >= 5000: return "💀 लीजेंडरी किलर"
    elif attacks >= 1000: return "🔥 एलाइट वारियर"
    elif attacks >= 500: return "⚡ प्रो अटैकर"
    elif attacks >= 100: return "🎯 फाइटर"
    elif attacks >= 50: return "💪 बिगनर"
    else: return "🍼 बेबी नौब"

def log_attack(uid, target, port, duration, status, atype="user"):
    if db:
        attacks_collection.insert_one({"user_id": uid, "target": target, "port": port, "duration": duration, "status": status, "type": atype, "timestamp": time.time()})
    attack_logs.append({"user_id": uid, "target": target, "port": port, "duration": duration, "status": status, "type": atype, "timestamp": time.time()})

def is_banned(uid): return uid in banned_users

def create_qr(upi_id, amount):
    url = f"upi://pay?pa={upi_id}&pn=ROXZ%20DDOS&am={amount}&cu=INR"
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf

def check_user_active(uid):
    now = time.time()
    return sum(1 for i in active_attacks.values() if i.get("user") == uid and now < i.get("finish_time", 0))

def check_group_active(gid):
    now = time.time()
    return sum(1 for i in active_group_attacks.values() if i.get("group") == gid and now < i.get("finish_time", 0))

def get_user_concurrent(uid):
    if uid in ADMIN_ID: return 10
    for k, v in keys_data.items():
        if v.get("used_by") == uid and v.get("used") and time.time() < v["expires_at"]:
            p = v.get("plan")
            if p and p in PLANS: return PLANS[p]["concurrent"]
    return settings.get("user_concurrent", DEFAULT_USER_CONCURRENT)

def get_user_time(uid):
    if uid in ADMIN_ID: return settings.get("user_attack_time", DEFAULT_USER_ATTACK_TIME)
    for k, v in keys_data.items():
        if v.get("used_by") == uid and v.get("used") and time.time() < v["expires_at"]:
            p = v.get("plan")
            if p and p in PLANS: return PLANS[p]["time"]
    return settings.get("user_attack_time", DEFAULT_USER_ATTACK_TIME)

def is_authorized(uid): return uid in users or uid in ADMIN_ID or uid in resellers

def add_group_attacked_ip(gid, ip):
    if gid not in group_attack_targets:
        group_attack_targets[gid] = set()
    group_attack_targets[gid].add(ip)

def check_group_ip_attacked(gid, ip):
    return ip in group_attack_targets.get(gid, set())

# ========== START COMMAND ==========
@bot.message_handler(commands=['start'])
def start(msg):
    uid = str(msg.chat.id)
    name = msg.from_user.first_name
    
    if is_banned(uid):
        bot.reply_to(msg, "💀💀 **तू बैन हो चुका है कमबख्त** 💀💀\n📞 @Roxz_gaming से बात कर", parse_mode="Markdown")
        return
    
    if msg.chat.type in ["group", "supergroup"]:
        gid = str(msg.chat.id)
        if gid in groups:
            bot.reply_to(msg, f"""
╔══════════════════════════════════════════════════════════╗
║   🔥 ROXZ DDOS BOT - GROUP MODE 🔥                       ║
╚══════════════════════════════════════════════════════════╝

✅ GROUP APPROVED!
⚡ ATTACK TIME: `{groups[gid]['attack_time']}s`
🎯 METHOD: UDP FLOOD

📝 SEND: `/attack IP PORT`
💀 EXAMPLE: `/attack 1.1.1.1 443`
""", parse_mode="Markdown", reply_markup=get_back_keyboard())
        else:
            bot.reply_to(msg, toxic_group_msg(), parse_mode="Markdown")
        return
    
    has_active = check_user_expiry(uid) if uid not in ADMIN_ID else True
    total = get_attack_count(uid)
    days, hours = get_remaining(uid) if uid not in ADMIN_ID else (999, 0)
    concurrent = get_user_concurrent(uid)
    time_limit = get_user_time(uid)
    rank = get_rank(total)
    
    welcome_msg = f"""
╔══════════════════════════════════════════════════════════╗
║   🔥 ROXZ DDOS BOT - ULTIMATE EDITION 🔥                ║
║   💀  💀                        ║
╚══════════════════════════════════════════════════════════╝

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 👤 USER: {name}                                          ┃
┃ 🆔 ID: `{uid}`                                           ┃
┃ 🏆 RANK: {rank}                                          ┃
┃ ✅ STATUS: `{'✅ ACTIVE' if has_active else '❌ EXPIRED'}`┃
┃ 🎯 ATTACKS: `{total}`                                    ┃
┃ ⏰ REMAINING: `{days}d {hours}h`                         ┃
┃ ⚡ CONCURRENT: `{concurrent}`                            ┃
┃ ⏱️ MAX TIME: `{time_limit}s`                             ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

💀 **नीचे बटन दबा के मजा ले** 💀
"""
    bot.reply_to(msg, welcome_msg, parse_mode="Markdown", reply_markup=get_user_slide_keyboard(uid))

# ========== ATTACK COMMAND ==========
@bot.message_handler(func=lambda msg: msg.text == "💀 ATTACK")
@bot.message_handler(commands=['attack'])
def attack_cmd(msg):
    uid = str(msg.chat.id)
    is_group = msg.chat.type in ["group", "supergroup"]
    
    if is_banned(uid):
        bot.reply_to(msg, toxic_error_msg(), parse_mode="Markdown")
        return
    
    if is_group:
        gid = str(msg.chat.id)
        if gid not in groups:
            bot.reply_to(msg, toxic_group_msg(), parse_mode="Markdown")
            return
        
        args = msg.text.split()
        if len(args) != 3 and msg.text != "💀 ATTACK":
            bot.reply_to(msg, "💀 **SAHI COMMAND DAL:** `/attack IP PORT`\n💀 **EXAMPLE:** `/attack 1.1.1.1 443`", parse_mode="Markdown")
            return
        
        if msg.text == "💀 ATTACK":
            bot.reply_to(msg, "💀 **BHAI COMMAND DAL:** `/attack IP PORT`\n💀 **EXAMPLE:** `/attack 1.1.1.1 443`", parse_mode="Markdown")
            return
        
        ip, port = args[1], args[2]
        try:
            port = int(port)
            if not re.match(r'^(\d{1,3}\.){3}\d{1,3}$', ip):
                bot.reply_to(msg, "❌ **GALAT IP BHAI**", parse_mode="Markdown")
                return
            if port < 1 or port > 65535:
                bot.reply_to(msg, "❌ **PORT SAHI DAL 1-65535**", parse_mode="Markdown")
                return
        except:
            bot.reply_to(msg, toxic_error_msg(), parse_mode="Markdown")
            return
        
        if check_group_ip_attacked(gid, ip):
            bot.reply_to(msg, f"💀 **IP `{ip}:{port}` पहले ही मारा जा चुका है इस ग्रुप में** 💀", parse_mode="Markdown")
            return
        
        active = check_group_active(gid)
        limit = groups[gid]["concurrent"]
        if active >= limit:
            bot.reply_to(msg, toxic_limit_msg(active, limit), parse_mode="Markdown")
            return
        
        if gid in group_cooldown:
            rem = 30 - (time.time() - group_cooldown[gid])
            if rem > 0:
                bot.reply_to(msg, toxic_cooldown_msg(int(rem)), parse_mode="Markdown")
                return
        
        group_cooldown[gid] = time.time()
        add_group_attacked_ip(gid, ip)
        atk_time = groups[gid]["attack_time"]
        
        aid = f"group_{gid}_{int(time.time())}"
        active_group_attacks[aid] = {"group": gid, "user": uid, "finish_time": time.time() + atk_time, "ip": ip, "port": port, "start_time": time.time()}
        
        bot.reply_to(msg, f"""
🔥🔥🔥 **GROUP ATTACK LAUNCHED!** 🔥🔥🔥

{toxic_start_msg(f'{ip}:{port}')}

🎯 **TARGET:** `{ip}:{port}`
⏱️ **DURATION:** `{atk_time}s`
⚡ **METHOD:** UDP FLOOD

💀 **JA KE RO AMMI KE PAAS** 💀
""", parse_mode="Markdown")
        
        def run():
            time.sleep(atk_time)
            log_attack(uid, ip, port, atk_time, "success", "group")
            bot.send_message(msg.chat.id, f"""
✅✅✅ **ATTACK FINISHED!** ✅✅✅

{toxic_success_msg(f'{ip}:{port}')}

🎯 **Target:** `{ip}:{port}`
⏱️ **Duration:** `{atk_time}s`

💀 **AGLA KON MARU ?** 💀
""", parse_mode="Markdown")
            if aid in active_group_attacks: del active_group_attacks[aid]
        threading.Thread(target=run, daemon=True).start()
        return
    
    # USER ATTACK
    if not is_authorized(uid):
        bot.reply_to(msg, toxic_unauth_msg(), parse_mode="Markdown")
        return
    
    if uid not in ADMIN_ID and not check_user_expiry(uid):
        bot.reply_to(msg, f"💀 **तेरा टाइम खतम हो गया** 💀\n💰 /buy या /redeem KEY कर", parse_mode="Markdown")
        return
    
    limit = get_user_concurrent(uid)
    time_limit = get_user_time(uid)
    
    active = check_user_active(uid)
    if active >= limit:
        bot.reply_to(msg, toxic_limit_msg(active, limit), parse_mode="Markdown")
        return
    
    if uid in cooldown and uid not in ADMIN_ID:
        rem = 10 - (time.time() - cooldown[uid])
        if rem > 0:
            bot.reply_to(msg, toxic_cooldown_msg(int(rem)), parse_mode="Markdown")
            return
    
    args = msg.text.split()
    if len(args) != 4 and msg.text != "💀 ATTACK":
        bot.reply_to(msg, f"💀 **SAHI COMMAND DAL:** `/attack IP PORT TIME`\n💀 **EXAMPLE:** `/attack 1.1.1.1 443 60`\n⚡ **MAX TIME:** `{time_limit}s`", parse_mode="Markdown")
        return
    
    if msg.text == "💀 ATTACK":
        bot.reply_to(msg, f"💀 **BHAI COMMAND DAL:** `/attack IP PORT TIME`\n💀 **EXAMPLE:** `/attack 1.1.1.1 443 60`", parse_mode="Markdown")
        return
    
    ip, port, duration = args[1], args[2], args[3]
    try:
        duration = int(duration)
        port = int(port)
        if duration < 10 or duration > time_limit:
            bot.reply_to(msg, f"❌ **{duration} सेकंड नहीं चलेगा 10-{time_limit} सेकंड लगा**", parse_mode="Markdown")
            return
        if not re.match(r'^(\d{1,3}\.){3}\d{1,3}$', ip):
            bot.reply_to(msg, "❌ **GALAT IP BHAI**", parse_mode="Markdown")
            return
        if port < 1 or port > 65535:
            bot.reply_to(msg, "❌ **PORT SAHI DAL 1-65535**", parse_mode="Markdown")
            return
    except:
        bot.reply_to(msg, toxic_error_msg(), parse_mode="Markdown")
        return
    
    cooldown[uid] = time.time()
    aid = f"user_{uid}_{int(time.time())}"
    active_attacks[aid] = {"user": uid, "finish_time": time.time() + duration, "ip": ip, "port": port, "start_time": time.time()}
    
    bot.reply_to(msg, f"""
🔥🔥🔥 **ATTACK LAUNCHED!** 🔥🔥🔥

{toxic_start_msg(f'{ip}:{port}')}

🎯 **TARGET:** `{ip}:{port}`
⏱️ **DURATION:** `{duration}s`
⚡ **METHOD:** UDP FLOOD
📊 **YOUR SLOTS:** `{active+1}/{limit}`

💀 **AB RONA MAT** 💀
""", parse_mode="Markdown")
    
    def run():
        time.sleep(duration)
        log_attack(uid, ip, port, duration, "success", "user")
        bot.send_message(msg.chat.id, f"""
✅✅✅ **ATTACK FINISHED!** ✅✅✅

{toxic_success_msg(f'{ip}:{port}')}

🎯 **Target:** `{ip}:{port}`
⏱️ **Duration:** `{duration}s`

💀 **AGLA KON MARU ?** 💀
""", parse_mode="Markdown")
        if aid in active_attacks: del active_attacks[aid]
    threading.Thread(target=run, daemon=True).start()

# ========== STATUS COMMAND ==========
@bot.message_handler(func=lambda msg: msg.text == "📊 STATUS")
@bot.message_handler(commands=['status'])
def status_cmd(msg):
    uid = str(msg.chat.id)
    
    if msg.chat.type in ["group", "supergroup"]:
        gid = str(msg.chat.id)
        if gid in groups:
            active = check_group_active(gid)
            attacked = len(group_attack_targets.get(gid, set()))
            bot.reply_to(msg, f"""
📊 **GROUP STATUS**

👥 GROUP: `{gid}`
⏱️ TIME: `{groups[gid]['attack_time']}s`
⚡ ACTIVE: `{active}/{groups[gid]['concurrent']}`
📝 ATTACKED IPS: `{attacked}`
""", parse_mode="Markdown")
        else:
            bot.reply_to(msg, toxic_group_msg(), parse_mode="Markdown")
        return
    
    if not is_authorized(uid):
        bot.reply_to(msg, toxic_unauth_msg(), parse_mode="Markdown")
        return
    
    active = check_user_active(uid)
    concurrent = get_user_concurrent(uid)
    msg_text = f"📊 **TERA STATUS**\n\n👤 **ACTIVE:** `{active}/{concurrent}`\n⚡ **SLOTS:** `{concurrent}`"
    if uid in cooldown and uid not in ADMIN_ID:
        rem = 10 - (time.time() - cooldown[uid])
        if rem > 0:
            msg_text += f"\n⏳ **COOLDOWN:** `{int(rem)}s` बाकी है जल्दीबाज"
    bot.reply_to(msg, msg_text, parse_mode="Markdown")

# ========== PROFILE COMMAND ==========
@bot.message_handler(func=lambda msg: msg.text == "👤 PROFILE")
@bot.message_handler(commands=['profile'])
def profile_cmd(msg):
    uid = str(msg.chat.id)
    if not is_authorized(uid):
        bot.reply_to(msg, toxic_unauth_msg(), parse_mode="Markdown")
        return
    
    has_active = check_user_expiry(uid) if uid not in ADMIN_ID else True
    total = get_attack_count(uid)
    days, hours = get_remaining(uid) if uid not in ADMIN_ID else (999, 0)
    rank = get_rank(total)
    concurrent = get_user_concurrent(uid)
    time_limit = get_user_time(uid)
    
    bot.reply_to(msg, f"""
👤 **TERI PROFILE**

🆔 ID: `{uid}`
🏆 RANK: {rank}
✅ STATUS: `{'✅ ACTIVE' if has_active else '❌ EXPIRED'}`
🎯 ATTACKS: `{total}`
⏰ EXPIRES: `{days}d {hours}h`
⚡ CONCURRENT: `{concurrent}`
⏱️ MAX TIME: `{time_limit}s`
""", parse_mode="Markdown")

# ========== BUY COMMAND ==========
@bot.message_handler(func=lambda msg: msg.text == "💰 BUY PLAN")
@bot.message_handler(commands=['buy'])
def buy_cmd(msg):
    bot.reply_to(msg, "💰 **PAISA LAGA KE LELE PLAN** 💰\n\n⬇️ **NICHE SE SELECT KAR** ⬇️", parse_mode="Markdown", reply_markup=get_plans_inline())

# ========== REDEEM COMMAND ==========
@bot.message_handler(func=lambda msg: msg.text == "🔑 REDEEM")
@bot.message_handler(commands=['redeem'])
def redeem_cmd(msg):
    uid = str(msg.chat.id)
    args = msg.text.split()
    
    if len(args) != 2 and msg.text != "🔑 REDEEM":
        bot.reply_to(msg, "❌ **SAHI SE DAL:** `/redeem KEY`", parse_mode="Markdown")
        return
    
    if msg.text == "🔑 REDEEM":
        bot.reply_to(msg, "🔑 **APNI KEY DAL:** `/redeem ROXZ-XXXX-XXXX-XXXX-XXXX`", parse_mode="Markdown")
        return
    
    key = args[1]
    if key not in keys_data:
        bot.reply_to(msg, "❌ **GALAT KEY BHAI**", parse_mode="Markdown")
        return
    
    info = keys_data[key]
    if info.get("used", False):
        bot.reply_to(msg, "❌ **KEY PHLE SE USE HO CHUKI HAI**", parse_mode="Markdown")
        return
    if time.time() > info["expires_at"]:
        bot.reply_to(msg, "❌ **KEY EXPIRE HO GAYI**", parse_mode="Markdown")
        del keys_data[key]
        save_keys(keys_data)
        return
    
    if uid not in users:
        users.append(uid)
        save_users(users_data)
    
    keys_data[key]["used"] = True
    keys_data[key]["used_by"] = uid
    save_keys(keys_data)
    
    expiry = datetime.fromtimestamp(info['expires_at']).strftime('%Y-%m-%d')
    duration = f"{info['duration_value']} {info['duration_unit']}(s)"
    
    bot.reply_to(msg, f"""
✅ **ACCESS MIL GAYA BHENCHOD** ✅

👤 USER: `{uid}`
⏰ DURATION: {duration}
📅 EXPIRES: {expiry}

🔥 **AB ATTACK KAR:** `/attack IP PORT TIME`
💀 **MAZA AAYEGA** 💀
""", parse_mode="Markdown")

# ========== HISTORY COMMAND ==========
@bot.message_handler(func=lambda msg: msg.text == "📜 HISTORY")
@bot.message_handler(commands=['history'])
def history_cmd(msg):
    uid = str(msg.chat.id)
    if not is_authorized(uid):
        bot.reply_to(msg, toxic_unauth_msg(), parse_mode="Markdown")
        return
    
    attacks = []
    if db:
        attacks = list(attacks_collection.find({"user_id": uid}).sort("timestamp", -1).limit(10))
    else:
        attacks = [a for a in attack_logs if a["user_id"] == uid][-10:]
    
    if not attacks:
        bot.reply_to(msg, "📜 **ABHI TAK KUCH NAHI MARA TU NE** 📜\n💀 /attack करके दिखा 💀", parse_mode="Markdown")
        return
    
    text = "📜 **TERE LAST 10 ATTACKS** 📜\n\n"
    for i, a in enumerate(attacks, 1):
        ts = datetime.fromtimestamp(a["timestamp"]).strftime('%m/%d %H:%M')
        status = "✅" if a["status"] == "success" else "❌"
        atype = "👤" if a.get("type", "user") == "user" else "👥"
        text += f"{i}. {status} {atype} `{a['target']}:{a['port']}` | {a['duration']}s | {ts}\n"
    bot.reply_to(msg, text, parse_mode="Markdown")

# ========== TOP COMMAND ==========
@bot.message_handler(func=lambda msg: msg.text == "🏆 TOP")
@bot.message_handler(commands=['top'])
def top_cmd(msg):
    if db:
        results = list(attacks_collection.aggregate([{"$group": {"_id": "$user_id", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}, {"$limit": 10}]))
    else:
        counts = defaultdict(int)
        for a in attack_logs:
            counts[a["user_id"]] += 1
        results = [{"_id": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]]
    
    if not results:
        bot.reply_to(msg, "📊 **ABHI TAK KOI TOPPER NAHI** 📊", parse_mode="Markdown")
        return
    
    text = "🏆 **TOP 10 ATTACKERS** 🏆\n\n"
    for i, r in enumerate(results, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} `{r['_id'][:10]}...` → `{r['count']}` attacks\n"
    bot.reply_to(msg, text, parse_mode="Markdown")

# ========== METHODS COMMAND ==========
@bot.message_handler(func=lambda msg: msg.text == "⚡ METHODS")
@bot.message_handler(commands=['methods'])
def methods_cmd(msg):
    bot.reply_to(msg, """
⚡ **ATTACK METHODS** ⚡

🎯 **METHOD:** UDP FLOOD
💪 **POWER:** 🔥🔥🔥🔥🔥

📝 **BEST PORTS:**
   • 443 (HTTPS) - सबसे बढ़िया
   • 8080 (Proxy) - गजब
   • 53 (DNS) - ठीक ठाक
   • 80 (HTTP) - स्टैंडर्ड

💀 **TIPS:** जितना ज्यादा समय उतनी ज्यादा मार 💀
""", parse_mode="Markdown")

# ========== HELP COMMAND ==========
@bot.message_handler(func=lambda msg: msg.text == "❓ HELP")
@bot.message_handler(commands=['help'])
def help_cmd(msg):
    help_text = """
🔥 **ROXZ DDOS BOT HELP** 🔥

💀 **USER ATTACK:**
/attack IP PORT TIME
EXAMPLE: /attack 1.1.1.1 443 60

👥 **GROUP ATTACK:**
/attack IP PORT
EXAMPLE: /attack 1.1.1.1 443

📊 **COMMANDS:**
/status - CHECK SLOTS
/profile - TERI PROFILE
/history - ATTACK HISTORY
/top - TOP ATTACKERS
/methods - ATTACK METHODS

💰 **UPGRADE:**
/buy - PLANS DEKH
/redeem KEY - KEY ACTIVATE KAR
"""
    bot.reply_to(msg, help_text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "🏓 PING")
@bot.message_handler(commands=['ping'])
def ping_cmd(msg):
    start = time.time()
    m = bot.reply_to(msg, "🏓 **PING...**", parse_mode="Markdown")
    latency = int((time.time() - start) * 1000)
    bot.edit_message_text(f"🏓 **PONG!**\n\n🤖 **LATENCY:** `{latency}ms`\n⚡ **ACTIVE:** `{len(active_attacks)}`\n💀 **BOT HAI BHAI MAST** 💀", msg.chat.id, m.message_id, parse_mode="Markdown")

# ========== ADMIN PANEL BUTTON HANDLER ==========
@bot.message_handler(func=lambda msg: msg.text == "👑 ADMIN PANEL")
def admin_panel_btn(msg):
    uid = str(msg.chat.id)
    if uid in ADMIN_ID:
        bot.reply_to(msg, """
╔══════════════════════════════════════════════════════════╗
║   👑 **ADMIN PANEL - SAARE COMMANDS** 👑                ║
╚══════════════════════════════════════════════════════════╝

💀 **NICHE BUTTONS HAI SAARE** 💀
""", parse_mode="Markdown", reply_markup=get_admin_slide_keyboard())

# ========== ADMIN SLIDE BUTTON HANDLERS ==========
@bot.message_handler(func=lambda msg: msg.text == "🔙 MAIN MENU")
def back_main_btn(msg):
    uid = str(msg.chat.id)
    bot.reply_to(msg, "💀 **MAIN MENU**", parse_mode="Markdown", reply_markup=get_user_slide_keyboard(uid))

# User Management
@bot.message_handler(func=lambda msg: msg.text == "👤 ADD USER")
def add_user_btn(msg):
    if str(msg.chat.id) in ADMIN_ID:
        bot.reply_to(msg, "📝 **COMMAND:** `/adduser USER_ID`\n💀 **EXAMPLE:** `/adduser 123456789`", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "➖ REMOVE USER")
def remove_user_btn(msg):
    if str(msg.chat.id) in ADMIN_ID:
        bot.reply_to(msg, "📝 **COMMAND:** `/removeuser USER_ID`\n💀 **EXAMPLE:** `/removeuser 123456789`", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "🚫 BAN USER")
def ban_user_btn(msg):
    if str(msg.chat.id) in ADMIN_ID:
        bot.reply_to(msg, "📝 **COMMAND:** `/ban USER_ID`\n💀 **EXAMPLE:** `/ban 123456789`", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "✅ UNBAN USER")
def unban_user_btn(msg):
    if str(msg.chat.id) in ADMIN_ID:
        bot.reply_to(msg, "📝 **COMMAND:** `/unban USER_ID`\n💀 **EXAMPLE:** `/unban 123456789`", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "👑 ADD RESELLER")
def add_reseller_btn(msg):
    if str(msg.chat.id) in ADMIN_ID:
        bot.reply_to(msg, "📝 **COMMAND:** `/addreseller USER_ID`\n💀 **EXAMPLE:** `/addreseller 123456789`", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "➖ REMOVE RESELLER")
def remove_reseller_btn(msg):
    if str(msg.chat.id) in ADMIN_ID:
        bot.reply_to(msg, "📝 **COMMAND:** `/removereseller USER_ID`\n💀 **EXAMPLE:** `/removereseller 123456789`", parse_mode="Markdown")

# Group Management
@bot.message_handler(func=lambda msg: msg.text == "👥 ADD GROUP")
def add_group_btn(msg):
    if str(msg.chat.id) in ADMIN_ID:
        bot.reply_to(msg, "📝 **COMMAND:** `/addgroup GROUP_ID TIME CONCURRENT`\n💀 **EXAMPLE:** `/addgroup -100123456789 60 2`", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "👥 REMOVE GROUP")
def remove_group_btn(msg):
    if str(msg.chat.id) in ADMIN_ID:
        bot.reply_to(msg, "📝 **COMMAND:** `/removegroup GROUP_ID`\n💀 **EXAMPLE:** `/removegroup -100123456789`", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "⏱️ SET GROUP TIME")
def set_group_time_btn(msg):
    if str(msg.chat.id) in ADMIN_ID:
        bot.reply_to(msg, "📝 **COMMAND:** `/setgrouptime GROUP_ID TIME`\n💀 **EXAMPLE:** `/setgrouptime -100123456789 120`", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "⚡ SET GROUP CONCURRENT")
def set_group_concurrent_btn(msg):
    if str(msg.chat.id) in ADMIN_ID:
        bot.reply_to(msg, "📝 **COMMAND:** `/setgroupconcurrent GROUP_ID NUMBER`\n💀 **EXAMPLE:** `/setgroupconcurrent -100123456789 3`", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "🗑️ CLEAR GROUP IPS")
def clear_group_ips_btn(msg):
    if str(msg.chat.id) in ADMIN_ID:
        bot.reply_to(msg, "📝 **COMMAND:** `/cleargroupips GROUP_ID`\n💀 **EXAMPLE:** `/cleargroupips -100123456789`", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "📋 LIST GROUPS")
def list_groups_btn(msg):
    if str(msg.chat.id) in ADMIN_ID:
        if not groups:
            bot.reply_to(msg, "📋 **ABHI TAK KOI GROUP ADD NAHI**", parse_mode="Markdown")
            return
        text = "📋 **ALL GROUPS** 📋\n\n"
        for gid, info in groups.items():
            attacked = len(group_attack_targets.get(gid, set()))
            text += f"👥 `{gid}`\n   ⏱️ {info['attack_time']}s | ⚡ {info['concurrent']}\n   📝 ATTACKED: {attacked} IPS\n\n"
        bot.reply_to(msg, text, parse_mode="Markdown")

# Key Management
@bot.message_handler(func=lambda msg: msg.text == "🔑 GEN KEY (30D)")
def genkey_30d_btn(msg):
    if str(msg.chat.id) in ADMIN_ID:
        key = generate_secure_key()
        expires = datetime.now() + timedelta(days=30)
        keys_data[key] = {"duration_value": 30, "duration_unit": "day", "generated_by": str(msg.chat.id), "generated_at": time.time(), "expires_at": expires.timestamp(), "used": False}
        save_keys(keys_data)
        bot.reply_to(msg, f"✅ **KEY GENERATED (30 DAYS)!**\n\n🔑 `{key}`\n📅 EXPIRES: {expires.strftime('%Y-%m-%d')}\n\n📤 SHARE: `/redeem {key}`", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "🔑 GEN KEY (5H)")
def genkey_5h_btn(msg):
    if str(msg.chat.id) in ADMIN_ID:
        key = generate_secure_key()
        expires = datetime.now() + timedelta(hours=5)
        keys_data[key] = {"duration_value": 5, "duration_unit": "hour", "generated_by": str(msg.chat.id), "generated_at": time.time(), "expires_at": expires.timestamp(), "used": False}
        save_keys(keys_data)
        bot.reply_to(msg, f"✅ **KEY GENERATED (5 HOURS)!**\n\n🔑 `{key}`\n📅 EXPIRES: {expires.strftime('%Y-%m-%d %H:%M:%S')}\n\n📤 SHARE: `/redeem {key}`", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "🗑️ REMOVE KEY")
def remove_key_btn(msg):
    if str(msg.chat.id) in ADMIN_ID:
        bot.reply_to(msg, "📝 **COMMAND:** `/removekey KEY`\n💀 **EXAMPLE:** `/removekey ROXZ-ABCD-EFGH-IJKL`", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "📋 MY KEYS")
def my_keys_btn(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, toxic_unauth_msg(), parse_mode="Markdown")
        return
    my_keys = []
    for k, v in keys_data.items():
        if v.get("generated_by") == uid and not v.get("used", False):
            exp = datetime.fromtimestamp(v["expires_at"]).strftime('%Y-%m-%d')
            my_keys.append(f"🔑 `{k}`\n   📅 {v['duration_value']}{v['duration_unit']} | EXP: {exp}")
    if my_keys:
        bot.reply_to(msg, "📋 **TERI GENERATED KEYS:**\n\n" + "\n\n".join(my_keys), parse_mode="Markdown")
    else:
        bot.reply_to(msg, "📋 **ABHI TAK KUCH GENERATE NAHI KIYA**", parse_mode="Markdown")

# Global Settings
@bot.message_handler(func=lambda msg: msg.text == "⏱️ SET USER TIME")
def set_user_time_btn(msg):
    if str(msg.chat.id) in ADMIN_ID:
        bot.reply_to(msg, "📝 **COMMAND:** `/setusertime SECONDS`\n💀 **EXAMPLE:** `/setusertime 300`\n⏱️ RANGE: 10-600 seconds", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "⚡ SET USER CONCURRENT")
def set_user_concurrent_btn(msg):
    if str(msg.chat.id) in ADMIN_ID:
        bot.reply_to(msg, "📝 **COMMAND:** `/setuserconcurrent NUMBER`\n💀 **EXAMPLE:** `/setuserconcurrent 5`\n⚡ RANGE: 1-20", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "💳 SET UPI")
def set_upi_btn(msg):
    if str(msg.chat.id) in ADMIN_ID:
        bot.reply_to(msg, "📝 **COMMAND:** `/setupi UPI_ID`\n💀 **EXAMPLE:** `/setupi roxz@axl`", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "📱 SET QR CODE")
def set_qr_btn(msg):
    if str(msg.chat.id) in ADMIN_ID:
        pending_qr_setup[str(msg.chat.id)] = True
        bot.reply_to(msg, "📱 **APNA QR CODE BHJ (PHOTO MEIN)**", parse_mode="Markdown")

# Payment & Broadcast
@bot.message_handler(func=lambda msg: msg.text == "💰 PAYMENT REQUESTS")
def payment_requests_btn(msg):
    if str(msg.chat.id) in ADMIN_ID:
        if not db:
            bot.reply_to(msg, "❌ DATABASE CONNECT NAHI HAI", parse_mode="Markdown")
            return
        pending = list(payments_collection.find({"status": "pending"}))
        if not pending:
            bot.reply_to(msg, "📭 **KOI PAYMENT REQUEST NAHI HAI**", parse_mode="Markdown")
            return
        for req in pending:
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("✅ APPROVE", callback_data=f"approve_{req['_id']}"), InlineKeyboardButton("❌ REJECT", callback_data=f"reject_{req['_id']}"))
            bot.send_message(msg.chat.id, f"""
💰 **PAYMENT REQUEST**

🆔 ID: `{req['_id']}`
👤 USER: `{req['user_id']}`
💎 PLAN: `{req['plan']}`
💵 AMOUNT: `₹{req['amount']}`
""", parse_mode="Markdown", reply_markup=kb)
            if req.get('photo_id'):
                bot.send_photo(msg.chat.id, req['photo_id'])

@bot.message_handler(func=lambda msg: msg.text == "📢 BROADCAST")
def broadcast_btn(msg):
    if str(msg.chat.id) in ADMIN_ID:
        bot.reply_to(msg, "📝 **COMMAND:** `/broadcast MESSAGE`\n💀 **EXAMPLE:** `/broadcast SAB LOG ATTACK KARO`", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "📊 BOT STATS")
def bot_stats_btn(msg):
    if str(msg.chat.id) in ADMIN_ID:
        bot.reply_to(msg, f"""
📊 **BOT STATISTICS**

👑 ADMINS: {len(ADMIN_ID)}
💎 RESELLERS: {len(resellers)}
👤 USERS: {len(users)}
💀 BANNED: {len(banned_users)}
🔑 KEYS: {len(keys_data)}
👥 GROUPS: {len(groups)}
🎯 TOTAL ATTACKS: {get_attack_count()}
⚡ ACTIVE USER ATTACKS: {len(active_attacks)}
⚡ ACTIVE GROUP ATTACKS: {len(active_group_attacks)}
""", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "📋 ALL USERS")
def all_users_btn(msg):
    if str(msg.chat.id) in ADMIN_ID:
        bot.reply_to(msg, f"""
📋 **ALL USERS LIST**

👑 ADMINS: {len(ADMIN_ID)}
💎 RESELLERS: {len(resellers)}
👤 TOTAL USERS: {len(users)}
💀 BANNED: {len(banned_users)}
""", parse_mode="Markdown")

# ========== ADMIN COMMANDS (TEXT) ==========
@bot.message_handler(commands=['adduser'])
def add_user_admin(msg):
    if str(msg.chat.id) not in ADMIN_ID: return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /adduser USER_ID")
        return
    nu = args[1]
    if nu in users:
        bot.reply_to(msg, "❌ User already exists!")
        return
    users.append(nu)
    save_users(users_data)
    bot.reply_to(msg, f"✅ User added: `{nu}`", parse_mode="Markdown")

@bot.message_handler(commands=['removeuser'])
def remove_user_admin(msg):
    if str(msg.chat.id) not in ADMIN_ID: return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /removeuser USER_ID")
        return
    target = args[1]
    if target in users:
        users.remove(target)
        save_users(users_data)
        bot.reply_to(msg, f"✅ User removed: `{target}`", parse_mode="Markdown")
    else:
        bot.reply_to(msg, "❌ User not found!")

@bot.message_handler(commands=['ban'])
def ban_admin(msg):
    if str(msg.chat.id) not in ADMIN_ID: return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /ban USER_ID")
        return
    target = args[1]
    if target in banned_users:
        bot.reply_to(msg, "❌ Already banned!")
        return
    banned_users.append(target)
    users_data["banned"] = banned_users
    save_users(users_data)
    bot.reply_to(msg, f"✅ Banned: `{target}`", parse_mode="Markdown")

@bot.message_handler(commands=['unban'])
def unban_admin(msg):
    if str(msg.chat.id) not in ADMIN_ID: return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /unban USER_ID")
        return
    target = args[1]
    if target in banned_users:
        banned_users.remove(target)
        users_data["banned"] = banned_users
        save_users(users_data)
        bot.reply_to(msg, f"✅ Unbanned: `{target}`", parse_mode="Markdown")
    else:
        bot.reply_to(msg, "❌ Not banned!")

@bot.message_handler(commands=['addreseller'])
def add_reseller_admin(msg):
    if str(msg.chat.id) not in ADMIN_ID: return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /addreseller USER_ID")
        return
    nr = args[1]
    if nr in resellers:
        bot.reply_to(msg, "❌ Already a reseller!")
        return
    resellers.append(nr)
    users_data["resellers"] = resellers
    save_users(users_data)
    if nr not in users:
        users.append(nr)
        save_users(users_data)
    bot.reply_to(msg, f"✅ Reseller added: `{nr}`", parse_mode="Markdown")

@bot.message_handler(commands=['removereseller'])
def remove_reseller_admin(msg):
    if str(msg.chat.id) not in ADMIN_ID: return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /removereseller USER_ID")
        return
    target = args[1]
    if target in resellers:
        resellers.remove(target)
        users_data["resellers"] = resellers
        save_users(users_data)
        bot.reply_to(msg, f"✅ Reseller removed: `{target}`", parse_mode="Markdown")
    else:
        bot.reply_to(msg, "❌ Not a reseller!")

@bot.message_handler(commands=['addgroup'])
def add_group_admin(msg):
    if str(msg.chat.id) not in ADMIN_ID: return
    args = msg.text.split()
    if len(args) != 4:
        bot.reply_to(msg, "Usage: /addgroup GROUP_ID TIME CONCURRENT\nExample: /addgroup -100123456789 60 2")
        return
    gid = args[1]
    try:
        atk_time = int(args[2])
        concurrent = int(args[3])
        if atk_time < 10 or atk_time > 300:
            bot.reply_to(msg, "❌ Time 10-300s!")
            return
        if concurrent < 1 or concurrent > 5:
            bot.reply_to(msg, "❌ Concurrent 1-5!")
            return
        if not db:
            groups[gid] = {"attack_time": atk_time, "concurrent": concurrent, "added_by": str(msg.chat.id), "added_at": time.time()}
        else:
            groups_collection.update_one({"group_id": gid}, {"$set": {"attack_time": atk_time, "concurrent": concurrent, "added_by": str(msg.chat.id), "added_at": time.time()}}, upsert=True)
            groups[gid] = {"attack_time": atk_time, "concurrent": concurrent, "added_by": str(msg.chat.id), "added_at": time.time()}
        bot.reply_to(msg, f"✅ Group added: `{gid}`\n⏱️ Time: {atk_time}s\n⚡ Concurrent: {concurrent}", parse_mode="Markdown")
    except:
        bot.reply_to(msg, "❌ Invalid parameters!")

@bot.message_handler(commands=['removegroup'])
def remove_group_admin(msg):
    if str(msg.chat.id) not in ADMIN_ID: return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /removegroup GROUP_ID")
        return
    gid = args[1]
    if gid in groups:
        if db: groups_collection.delete_one({"group_id": gid})
        del groups[gid]
        if gid in group_attack_targets: del group_attack_targets[gid]
        bot.reply_to(msg, f"✅ Group removed: `{gid}`", parse_mode="Markdown")
    else:
        bot.reply_to(msg, "❌ Group not found!")

@bot.message_handler(commands=['setgrouptime'])
def set_group_time_admin(msg):
    if str(msg.chat.id) not in ADMIN_ID: return
    args = msg.text.split()
    if len(args) != 3:
        bot.reply_to(msg, "Usage: /setgrouptime GROUP_ID TIME")
        return
    gid = args[1]
    try:
        nt = int(args[2])
        if nt < 10 or nt > 300:
            bot.reply_to(msg, "❌ Time 10-300s!")
            return
        if gid not in groups:
            bot.reply_to(msg, "❌ Group not found!")
            return
        groups[gid]["attack_time"] = nt
        if db: groups_collection.update_one({"group_id": gid}, {"$set": {"attack_time": nt}})
        bot.reply_to(msg, f"✅ Group `{gid}` time set to `{nt}s`!", parse_mode="Markdown")
    except:
        bot.reply_to(msg, "❌ Invalid!")

@bot.message_handler(commands=['setgroupconcurrent'])
def set_group_concurrent_admin(msg):
    if str(msg.chat.id) not in ADMIN_ID: return
    args = msg.text.split()
    if len(args) != 3:
        bot.reply_to(msg, "Usage: /setgroupconcurrent GROUP_ID NUMBER")
        return
    gid = args[1]
    try:
        nc = int(args[2])
        if nc < 1 or nc > 5:
            bot.reply_to(msg, "❌ Concurrent 1-5!")
            return
        if gid not in groups:
            bot.reply_to(msg, "❌ Group not found!")
            return
        groups[gid]["concurrent"] = nc
        if db: groups_collection.update_one({"group_id": gid}, {"$set": {"concurrent": nc}})
        bot.reply_to(msg, f"✅ Group `{gid}` concurrent set to `{nc}`!", parse_mode="Markdown")
    except:
        bot.reply_to(msg, "❌ Invalid!")

@bot.message_handler(commands=['cleargroupips'])
def clear_group_ips_admin(msg):
    if str(msg.chat.id) not in ADMIN_ID: return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /cleargroupips GROUP_ID")
        return
    gid = args[1]
    if gid in groups:
        if gid in group_attack_targets:
            group_attack_targets[gid].clear()
        bot.reply_to(msg, f"✅ Cleared attacked IPs for group `{gid}`!", parse_mode="Markdown")
    else:
        bot.reply_to(msg, "❌ Group not found!")

@bot.message_handler(commands=['setusertime'])
def set_user_time_admin(msg):
    if str(msg.chat.id) not in ADMIN_ID: return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /setusertime SECONDS")
        return
    try:
        t = int(args[1])
        if t < 10 or t > 600:
            bot.reply_to(msg, "❌ 10-600 seconds!")
            return
        settings["user_attack_time"] = t
        save_settings(settings)
        bot.reply_to(msg, f"✅ User time set to `{t}s`!", parse_mode="Markdown")
    except:
        bot.reply_to(msg, "❌ Invalid!")

@bot.message_handler(commands=['setuserconcurrent'])
def set_user_concurrent_admin(msg):
    if str(msg.chat.id) not in ADMIN_ID: return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /setuserconcurrent NUMBER")
        return
    try:
        c = int(args[1])
        if c < 1 or c > 20:
            bot.reply_to(msg, "❌ 1-20!")
            return
        settings["user_concurrent"] = c
        save_settings(settings)
        bot.reply_to(msg, f"✅ User concurrent set to `{c}`!", parse_mode="Markdown")
    except:
        bot.reply_to(msg, "❌ Invalid!")

@bot.message_handler(commands=['setupi'])
def setupi_admin(msg):
    if str(msg.chat.id) not in ADMIN_ID: return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /setupi UPI_ID")
        return
    settings["upi_id"] = args[1]
    save_settings(settings)
    bot.reply_to(msg, f"✅ UPI set to: `{args[1]}`", parse_mode="Markdown")

@bot.message_handler(commands=['setqr'])
def setqr_admin(msg):
    if str(msg.chat.id) not in ADMIN_ID: return
    pending_qr_setup[str(msg.chat.id)] = True
    bot.reply_to(msg, "📱 Send QR code image")

@bot.message_handler(commands=['broadcast'])
def broadcast_admin(msg):
    if str(msg.chat.id) not in ADMIN_ID: return
    args = msg.text.split(maxsplit=1)
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /broadcast MESSAGE")
        return
    success = 0
    for user in users:
        try:
            bot.send_message(user, f"📢 **BROADCAST**\n\n{args[1]}\n\n- ROXZ DDOS TEAM", parse_mode="Markdown")
            success += 1
            time.sleep(0.05)
        except:
            pass
    bot.reply_to(msg, f"✅ Sent to `{success}` users!", parse_mode="Markdown")

@bot.message_handler(commands=['removekey'])
def remove_key_admin(msg):
    if str(msg.chat.id) not in ADMIN_ID: return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /removekey KEY")
        return
    key = args[1]
    if key in keys_data:
        del keys_data[key]
        save_keys(keys_data)
        bot.reply_to(msg, f"✅ Key removed: `{key}`", parse_mode="Markdown")
    else:
        bot.reply_to(msg, "❌ Key not found!")

# ========== PHOTO HANDLER ==========
@bot.message_handler(content_types=['photo'])
def handle_photo(msg):
    uid = str(msg.chat.id)
    
    if uid in pending_qr_setup:
        file_id = msg.photo[-1].file_id
        settings["qr_code"] = file_id
        settings["qr_code_id"] = file_id
        save_settings(settings)
        del pending_qr_setup[uid]
        bot.reply_to(msg, "✅ **QR CODE SAVE HO GAYA** ✅\n💀 AB USE KARO 💀", parse_mode="Markdown")
        return
    
    if uid in pending_requests:
        req_id = pending_requests[uid]
        if db:
            req = payments_collection.find_one({"_id": req_id})
            if req:
                file_id = msg.photo[-1].file_id
                payments_collection.update_one({"_id": req_id}, {"$set": {"photo_id": file_id}})
                for admin_id in ADMIN_ID:
                    kb = InlineKeyboardMarkup()
                    kb.add(InlineKeyboardButton("✅ APPROVE", callback_data=f"approve_{req_id}"), InlineKeyboardButton("❌ REJECT", callback_data=f"reject_{req_id}"))
                    bot.send_photo(admin_id, file_id, caption=f"💰 **PAYMENT REQUEST**\n👤 USER: `{uid}`\n💎 PLAN: `{req['plan']}`\n💵 AMOUNT: `₹{req['amount']}`", parse_mode="Markdown", reply_markup=kb)
                bot.reply_to(msg, "✅ **PAYMENT PROOF ADMIN KE PAAS CHALA GAYA** ✅\n⏰ **AB KEY AAYEGI TERI**", parse_mode="Markdown")
                del pending_requests[uid]
        return
    
    bot.reply_to(msg, "❓ **YEH PHOTO KAHAN SE AAGAYI ?**\n\n💀 PAYMENT KARNA HAI TOH /buy KAR\n💀 ADMIN QR SET KARNA HAI TOH /setqr KAR", parse_mode="Markdown")

# ========== CALLBACK HANDLERS ==========
@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    uid = str(call.from_user.id)
    data = call.data
    
    if data == "back_main":
        bot.edit_message_text("💀 **MAIN MENU**", call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.send_message(call.message.chat.id, "💀 **SELECT OPTION:**", reply_markup=get_user_slide_keyboard(uid))
    
    elif data.startswith("buy_"):
        plan_id = data.replace("buy_", "")
        plan = PLANS.get(plan_id)
        if not plan: return
        
        upi_id = settings.get("upi_id", "roxz@axl")
        qr_file = settings.get("qr_code_id")
        req_id = f"{uid}_{int(time.time())}"
        
        if db:
            payments_collection.insert_one({"_id": req_id, "user_id": uid, "plan": plan_id, "amount": plan['price'], "status": "pending", "timestamp": time.time()})
        
        pending_requests[uid] = req_id
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📸 I HAVE PAID", callback_data=f"paid_{req_id}"), InlineKeyboardButton("🔙 BACK", callback_data="back_main"))
        
        msg_text = f"""
💰 **PAYMENT DETAILS**

💎 PLAN: {plan['name']}
💵 AMOUNT: ₹{plan['price']}
📅 DAYS: {plan['days']}
📱 UPI: `{upi_id}`

**STEPS:**
1️⃣ ₹{plan['price']} भेज {upi_id}
2️⃣ SCREENSHOT LE
3️⃣ "I HAVE PAID" DABA
4️⃣ SCREENSHOT BHJ

💀 **JALDI KAR VARNA MAARUNGA** 💀
"""
        
        if qr_file:
            try:
                bot.send_photo(call.message.chat.id, qr_file, caption=msg_text, parse_mode="Markdown", reply_markup=kb)
            except:
                bot.send_photo(call.message.chat.id, create_qr(upi_id, plan['price']), caption=msg_text, parse_mode="Markdown", reply_markup=kb)
        else:
            bot.send_photo(call.message.chat.id, create_qr(upi_id, plan['price']), caption=msg_text, parse_mode="Markdown", reply_markup=kb)
        
        bot.delete_message(call.message.chat.id, call.message.message_id)
    
    elif data.startswith("paid_"):
        req_id = data.replace("paid_", "")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.send_message(call.message.chat.id, "📸 **SCREENSHOT BHJ JALDI**", parse_mode="Markdown")
        pending_requests[uid] = req_id
    
    elif data.startswith("approve_"):
        if uid not in ADMIN_ID:
            bot.answer_callback_query(call.id, "ADMIN ONLY!")
            return
        req_id = data.replace("approve_", "")
        if db:
            req = payments_collection.find_one({"_id": req_id})
            if req:
                plan = req['plan']
                days = PLANS[plan]['days']
                user_id = req['user_id']
                key = generate_secure_key()
                expires = datetime.now() + timedelta(days=days)
                keys_data[key] = {"duration_value": days, "duration_unit": "day", "generated_by": "system", "generated_at": time.time(), "expires_at": expires.timestamp(), "used": False, "plan": plan}
                save_keys(keys_data)
                payments_collection.update_one({"_id": req_id}, {"$set": {"status": "approved", "key": key}})
                if user_id not in users:
                    users.append(user_id)
                    save_users(users_data)
                bot.answer_callback_query(call.id, "APPROVED!")
                bot.edit_message_text(f"✅ **APPROVED! KEY:** `{key}`", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
                try:
                    bot.send_message(user_id, f"✅ **PAYMENT APPROVED!**\n🔑 **KEY:** `{key}`\n/redeem {key}", parse_mode="Markdown")
                except:
                    pass
    
    elif data.startswith("reject_"):
        if uid not in ADMIN_ID:
            bot.answer_callback_query(call.id, "ADMIN ONLY!")
            return
        req_id = data.replace("reject_", "")
        if db:
            payments_collection.update_one({"_id": req_id}, {"$set": {"status": "rejected"}})
            bot.answer_callback_query(call.id, "REJECTED!")
            bot.edit_message_text("❌ **REQUEST REJECTED!**", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

# ========== CLEANUP ==========
def cleanup():
    while True:
        time.sleep(30)
        now = time.time()
        for aid, info in list(active_attacks.items()):
            if now >= info.get("finish_time", 0):
                del active_attacks[aid]
        for aid, info in list(active_group_attacks.items()):
            if now >= info.get("finish_time", 0):
                del active_group_attacks[aid]
        for key, info in list(keys_data.items()):
            if now > info.get("expires_at", 0):
                if info.get("used_by") and info["used_by"] in users and info["used_by"] not in ADMIN_ID:
                    users.remove(info["used_by"])
                    save_users(users_data)
                del keys_data[key]
        save_keys(keys_data)
        if db:
            payments_collection.delete_many({"status": "pending", "timestamp": {"$lt": time.time() - 1800}})

threading.Thread(target=cleanup, daemon=True).start()

# ========== MAIN ==========
print("""
╔═══════════════════════════════════════════════════════════════════════════╗
║   🔥 ROXZ DDOS BOT - TOXIC HINDI EDITION 🔥                              ║
║   VERSION: 12.0 (FULL TOXIC + GAALI + STYLISH)                          ║
║   DEVELOPER: @Roxz_gaming                                                ║
║   STATUS: ONLINE ✅  |  USERS: {}  |  GROUPS: {}  |  KEYS: {}             ║
║   💀 HAR REPLY PE TOXIC GAALI MILEGI 💀                                  ║
╚═══════════════════════════════════════════════════════════════════════════╝
""".format(len(users), len(groups), len(keys_data)))

while True:
    try:
        bot.infinity_polling(timeout=60)
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(5)
