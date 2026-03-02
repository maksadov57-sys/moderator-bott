import telebot
import sqlite3
import re
import time
from datetime import datetime
from telebot import types

# --- SOZLAMALAR ---
TOKEN = "7654410573:AAHhzDMye92WMdqXlkfYjScTgkfEMaOvUiM" 
bot = telebot.TeleBot(TOKEN)
OWNER_ID = 7693012837  

# --- MA'LUMOTLAR BAZASI ---
def init_db():
    conn = sqlite3.connect('bot_manager.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS bad_words (word TEXT PRIMARY KEY)')
    cursor.execute('CREATE TABLE IF NOT EXISTS channels (channel_id TEXT PRIMARY KEY, link TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)') 
    cursor.execute('CREATE TABLE IF NOT EXISTS warns (user_id INTEGER PRIMARY KEY, count INTEGER DEFAULT 0)')
    conn.commit()
    conn.close()

init_db()

def get_db():
    return sqlite3.connect('bot_manager.db', check_same_thread=False)

# --- YORDAMCHI FUNKSIYALAR ---
def is_bot_admin(user_id):
    return user_id == OWNER_ID

def get_mention(user):
    return f"@{user.username}" if user.username else f"[{user.first_name}](tg://user?id={user.id})"

def check_sub(user_id):
    conn = get_db()
    channels = conn.execute('SELECT channel_id, link FROM channels').fetchall()
    conn.close()
    unsub_links = []
    for cid, link in channels:
        try:
            status = bot.get_chat_member(cid, user_id).status
            if status in ['left', 'kicked']: unsub_links.append(link)
        except: continue
    return unsub_links

# --- BROADCAST (XABAR YUBORISH) ---
@bot.message_handler(commands=['send'])
def broadcast(m):
    if not is_bot_admin(m.from_user.id): return
    msg_text = m.text.replace('/send ', '')
    if not msg_text or '/send' in msg_text:
        return bot.reply_to(m, "Xabar yozing: `/send Matn`")
    
    conn = get_db(); users = conn.execute('SELECT user_id FROM users').fetchall(); conn.close()
    count = 0
    for u in users:
        try:
            bot.send_message(u[0], msg_text)
            count += 1
            time.sleep(0.05)
        except: continue
    bot.reply_to(m, f"✅ {count} ta foydalanuvchiga yuborildi.")

# --- CAPTCHA TIZIMI ---
@bot.message_handler(content_types=['new_chat_members'])
def handle_new_member(m):
    for user in m.new_chat_members:
        if user.is_bot: continue
        bot.restrict_chat_member(m.chat.id, user.id, can_send_messages=False)
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("✅ Men robot emasman", callback_data=f"v_{user.id}"))
        bot.send_message(m.chat.id, f"Xush kelibsiz {get_mention(user)}!\nGuruhga yozish uchun tugmani bosing:", reply_markup=kb, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('v_'))
def verify(call):
    uid = int(call.data.split('_')[1])
    if call.from_user.id != uid:
        return bot.answer_callback_query(call.id, "Bu tugma siz uchun emas!")
    bot.restrict_chat_member(call.message.chat.id, uid, can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id, "Siz tasdiqlandingiz!")

# --- ADMIN BUYRUQLARI ---
@bot.message_handler(commands=['admin'])
def admin_panel(m):
    if not is_bot_admin(m.from_user.id): return
    text = (
        "🛠 **Super Admin Panel**\n\n"
        "📢 **Kanallar:** `/add_chan @id link`, `/chans`, `/del_chan @id` \n"
        "📝 **So'zlar:** `/add_word so'z`, `/words`, `/del_word so'z` \n"
        "📢 **E'lon:** `/send matn` (Hamma a'zolarga) \n\n"
        "💡 **Reply buyruqlari:** `/mute`, `/ban`, `/unwarn`"
    )
    bot.reply_to(m, text, parse_mode="Markdown")

@bot.message_handler(commands=['add_word'])
def add_w(m):
    if not is_bot_admin(m.from_user.id): return
    word = m.text.replace('/add_word ', '').lower().strip()
    conn = get_db(); conn.execute('INSERT OR IGNORE INTO bad_words VALUES (?)', (word,)); conn.commit(); conn.close()
    bot.reply_to(m, f"✅ '{word}' bloklandi.")

@bot.message_handler(commands=['mute', 'ban', 'unwarn'])
def punishment(m):
    if not is_bot_admin(m.from_user.id) or not m.reply_to_message: return
    cmd = m.text.split()[0][1:]
    target = m.reply_to_message.from_user
    if cmd == 'mute':
        bot.restrict_chat_member(m.chat.id, target.id, until_date=int(time.time())+900)
        bot.reply_to(m, f"🔇 {get_mention(target)} 15 daqiqa mute.")
    elif cmd == 'ban':
        bot.ban_chat_member(m.chat.id, target.id)
        bot.reply_to(m, f"🚫 {get_mention(target)} haydaldi.")
    elif cmd == 'unwarn':
        conn = get_db(); conn.execute('UPDATE warns SET count = 0 WHERE user_id = ?', (target.id,)); conn.commit(); conn.close()
        bot.reply_to(m, "✅ Ogohlantirishlar tozalandi.")

# --- ASOSIY FILTR VA NIGHT MODE ---
@bot.message_handler(func=lambda m: True, content_types=['text', 'photo', 'video', 'document'])
def main_filter(m):
    uid, cid = m.from_user.id, m.chat.id
    
    # Ma'lumotlar bazasiga foydalanuvchini qo'shish
    conn = get_db(); conn.execute('INSERT OR IGNORE INTO users VALUES (?)', (uid,)); conn.commit(); conn.close()

    # Majburiy obuna (Faqat shaxsiyda)
    if m.chat.type == 'private':
        unsub = check_sub(uid)
        if unsub:
            kb = types.InlineKeyboardMarkup()
            for l in unsub: kb.add(types.InlineKeyboardButton("A'zo bo'lish ➕", url=l))
            return bot.send_message(uid, "Kanalga a'zo bo'ling:", reply_markup=kb)

    # Guruh nazorati
    if m.chat.type in ['group', 'supergroup']:
        # Adminlarni tekshirmaslik
        try:
            if bot.get_chat_member(cid, uid).status in ['administrator', 'creator']: return
        except: pass

        # 1. Night Mode (23:00 - 07:00)
        hour = datetime.now().hour
        if hour >= 23 or hour < 7:
            try: bot.delete_message(cid, m.message_id)
            except: pass
            return

        # 2. Mazmun tekshiruvi
        text = (m.text or m.caption or "").lower()
        conn = get_db(); bad_words = [r[0] for r in conn.execute('SELECT word FROM bad_words').fetchall()]; conn.close()
        
        is_bad = any(w in text for w in bad_words) if bad_words else False
        is_link = any(x in text for x in ["t.me/", "http", "@", ".uz", ".com", ".ru"])
        is_arab = re.search(r'[\u0600-\u06FF]', text)

        if is_bad or is_link or is_arab:
            try: bot.delete_message(cid, m.message_id)
            except: pass
            
            conn = get_db(); cursor = conn.cursor()
            cursor.execute('INSERT OR IGNORE INTO warns VALUES (?, 0)', (uid,))
            cursor.execute('UPDATE warns SET count = count + 1 WHERE user_id = ?', (uid,))
            count = cursor.execute('SELECT count FROM warns WHERE user_id = ?', (uid,)).fetchone()[0]
            conn.commit(); conn.close()

            if count == 3:
                bot.restrict_chat_member(cid, uid, until_date=int(time.time())+900)
                bot.send_message(cid, f"🔇 {get_mention(m.from_user)} 15 daqiqa mute (3/5)!")
            elif count >= 5:
                bot.ban_chat_member(cid, uid)
                bot.send_message(cid, f"🚫 {get_mention(m.from_user)} BAN (5/5)!")
            else:
                bot.send_message(cid, f"⚠️ {get_mention(m.from_user)} qoida buzildi! Ogohlantirish: {count}/5")

# --- ISHGA TUSHIRISH ---
if __name__ == "__main__":
    bot.remove_webhook()
    print("Bot barcha imkoniyatlar bilan ishga tushdi...")
    bot.infinity_polling(skip_pending=True)