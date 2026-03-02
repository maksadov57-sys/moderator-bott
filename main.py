Kechirasiz, boya yuborgan kodimda yana tushuntirish matnlari aralashib qolgani uchun Render xato beribdi. Hozir faqat kodning o'zini, hech qanday ortiqcha gaplarsiz yuboraman.

GitHub'dagi main.py fayli ichidagilarni butunlay tozalab, mana shu matnni joylang (nusxalashda ehtiyot bo'ling, faqat import bilan boshlanib, polling bilan tugaydigan qismni oling):

import telebot, sqlite3, time, threading, re
from flask import Flask
from telebot import types

app = Flask(name)
@app.route('/')
def home(): return "Bot is live!"

def run_flask():
app.run(host='0.0.0.0', port=8080)

TOKEN = "8639157744:AAEXbAI3-7GWvfgQVzFbCtc_MmBOH5EfNRI"
bot = telebot.TeleBot(TOKEN)
OWNER_ID = 6385063814

def init_db():
conn = sqlite3.connect('moderator.db', check_same_thread=False)
conn.execute('CREATE TABLE IF NOT EXISTS channels (id TEXT PRIMARY KEY, link TEXT)')
conn.execute('CREATE TABLE IF NOT EXISTS warns (user_id INTEGER PRIMARY KEY, count INTEGER DEFAULT 0)')
conn.commit()
conn.close()

init_db()

def is_subscribed(user_id):
conn = sqlite3.connect('moderator.db', check_same_thread=False)
channels = conn.execute('SELECT id FROM channels').fetchall()
conn.close()
if not channels: return True
for (cid,) in channels:
try:
status = bot.get_chat_member(cid, user_id).status
if status in ['left', 'kicked']: return False
except: continue
return True

@bot.message_handler(commands=['start'])
def start_handler(m):
uid = m.from_user.id
if not is_subscribed(uid):
conn = sqlite3.connect('moderator.db', check_same_thread=False)
channels = conn.execute('SELECT link FROM channels').fetchall()
conn.close()
kb = types.InlineKeyboardMarkup()
for (link,) in channels:
kb.add(types.InlineKeyboardButton("A'zo bo'lish ➕", url=link))
return bot.send_message(uid, "Kanallarga a'zo bo'ling:", reply_markup=kb)
kb = types.InlineKeyboardMarkup()
kb.add(types.InlineKeyboardButton("Guruhga qo'shish ➕", url=f"[подозрительная ссылка удалена]{bot.get_me().username}?startgroup=true"))
bot.send_message(uid, "Xush kelibsiz! Meni guruhga qo'shib admin qiling.", reply_markup=kb)

@bot.message_handler(commands=['add_chan'])
def add_chan(m):
if m.from_user.id != OWNER_ID: return
try:
parts = m.text.split()
cid, link = parts[1], parts[2]
conn = sqlite3.connect('moderator.db', check_same_thread=False)
conn.execute('INSERT OR REPLACE INTO channels VALUES (?, ?)', (cid, link))
conn.commit(); conn.close()
bot.reply_to(m, "✅ Kanal qo'shildi.")
except: bot.reply_to(m, "Xato! Format: /add_chan ID link")

@bot.message_handler(commands=['ban', 'kick', 'mute', 'unmute', 'unban'])
def admin_actions(m):
if not m.reply_to_message: return bot.reply_to(m, "Reply qiling!")
st = bot.get_chat_member(m.chat.id, m.from_user.id).status
if st not in ['administrator', 'creator'] and m.from_user.id != OWNER_ID: return
tid = m.reply_to_message.from_user.id
cmd = m.text.split()[0].lower()
try:
if cmd == '/ban': bot.ban_chat_member(m.chat.id, tid); bot.reply_to(m, "Banlandi.")
elif cmd == '/kick': bot.ban_chat_member(m.chat.id, tid); bot.unban_chat_member(m.chat.id, tid); bot.reply_to(m, "Chiqarildi.")
elif cmd == '/mute': bot.restrict_chat_member(m.chat.id, tid, until_date=time.time()+86400); bot.reply_to(m, "Mute qilindi.")
elif cmd == '/unmute': bot.restrict_chat_member(m.chat.id, tid, can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True); bot.reply_to(m, "Mute olindi.")
elif cmd == '/unban': bot.unban_chat_member(m.chat.id, tid, only_if_banned=True); bot.reply_to(m, "Ban olindi.")
except Exception as e: bot.reply_to(m, f"Xato: {e}")

@bot.message_handler(func=lambda m: m.chat.type in ['group', 'supergroup'])
def monitor(m):
uid = m.from_user.id
if bot.get_chat_member(m.chat.id, uid).status in ['administrator', 'creator']: return
if any(x in (m.text or "").lower() for x in ["t.me/", "http", ".uz", ".com"]):
try: bot.delete_message(m.chat.id, m.message_id)
except: pass
conn = sqlite3.connect('moderator.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('INSERT OR IGNORE INTO warns VALUES (?, 0)', (uid,))
cursor.execute('UPDATE warns SET count = count + 1 WHERE user_id = ?', (uid,))
count = cursor.execute('SELECT count FROM warns WHERE user_id = ?', (uid,)).fetchone()[0]
conn.commit(); conn.close()
if count >= 5:
bot.ban_chat_member(m.chat.id, uid)
bot.send_message(m.chat.id, "5 ta ogohlantirish bilan banlandi!")
else: bot.send_message(m.chat.id, f"Reklama mumkin emas! Ogohlantirish: {count}/5")

if name == "main":
threading.Thread(target=run_flask, daemon=True).start()
bot.infinity_polling(skip_pending=True)
