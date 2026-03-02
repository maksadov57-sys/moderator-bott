import telebot, sqlite3, time, threading, re
from flask import Flask
from telebot import types

app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is live!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

TOKEN = "8639157744:AAEXbAI3-7GWvfgQVzFbCtc_MmBOH5EfNRI"
bot = telebot.TeleBot(TOKEN)
OWNER_ID = 6385063814

# Taqiqlangan so'zlar ro'yxati (Kengaytirilgan: 150 tagacha)
BAD_WORDS = [
    "jalap", "qanjiq", "am", "kot", "qoxtak", "itvachcha", "shalpang", "dalbayob", 
    "skay", "suka", "blat", "blyat", "gandon", "prezervativ", "tvar", "padla", 
    "lox", "onangni", "oyangni", "ammi", "kotini", "sharmanda", "yiban", "axmoq", 
    "iflos", "maraz", "hayvon", "eshak", "mol", "qo'tqoz", "qotoq", "sikay", 
    "sikkiman", "og'zingga", "dumbul", "past", "xunasa", "gey", "foxisha", "badbaxt",
    "shumi", "dalban", "qurumsog", "xarom", "haromi", "iflos", "pastkash", "malla",
    "siktir", "dalbayob", "axlat", "manjalaqi", "isqirt", "itdan tarqagan", "beshaka",
    "qalampir", "qo'tir", "malla", "tuxum", "shatshax", "shaloq", "ko't", "ko'tni",
    "sikaman", "yamlamas", "shilliq", "vahshiy", "pastkash", "olox", "xudo urgan",
    "iblis", "murtad", "kofir", "iflos", "yaramas", "nusxa", "shumtaka", "daydi",
    "behayot", "besharm", "razil", "pastkash", "latta", "cho'chqa", "to'ng'iz",
    "tovuqmiy", "miyasiy", "jinni", "telba", "miyasi yoq", "qo'y", "echki", "mol",
    "xunuk", "basharangga", "betingga", "yuzsiz", "nomussuz", "oriyatssiz",
    "padaringga", "lattachaynar", "xezalak", "bachchavoz", "ablah", "yaxshi",
    "vaxshiy", "odamsiz", "g'irt", "ahmoq", "tentak", "ezma", "chirigan", "sasigan",
    "sassiq", "sassiqvoy", "qo'lansa", "yuvindi", "ko'ppak", "tazid", "shum",
    "itvachcha", "badbaxt", "zahar", "o'zingga", "qara", "battar", "bebaraka",
    "tuzsiz", "ko'r", "kar", "soqov", "miyav", "piyoz", "ko'tbachcha", "shlyapa",
    "shlang", "duxi", "nol", "paxsa", "do'mboq", "semiq", "ariq", "ko'cha", "bomj",
    "xaromxo'r", "xo'shoma", "laganbardor", "xoin", "olifta", "vaysaqi", "g'iybatchi"
]

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
        return bot.send_message(uid, "Botdan foydalanish uchun kanallarga a'zo bo'ling:", reply_markup=kb)
    
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Guruhga qo'shish ➕", url=f"https://t.me/{bot.get_me().username}?startgroup=true"))
    bot.send_message(uid, "Salom! Men guruhni reklama va so'kinishlardan tozalayman. Meni guruhga qo'shing va adminlik huquqini bering.", reply_markup=kb)

@bot.message_handler(func=lambda m: m.chat.type in ['group', 'supergroup'])
def monitor(m):
    uid = m.from_user.id
    text = (m.text or "").lower()
    
    # Adminlarni tekshirmaymiz
    try:
        status = bot.get_chat_member(m.chat.id, uid).status
        if status in ['administrator', 'creator']:
            return
    except:
        pass

    # Reklama yoki So'kinishni aniqlash
    has_link = any(x in text for x in ["t.me/", "http", ".uz", ".com", ".ru", "bit.ly"])
    has_bad_word = any(word in text for word in BAD_WORDS)

    if has_link or has_bad_word:
        try:
            bot.delete_message(m.chat.id, m.message_id)
        except:
            pass
        
        conn = sqlite3.connect('moderator.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO warns VALUES (?, 0)', (uid,))
        cursor.execute('UPDATE warns SET count = count + 1 WHERE user_id = ?', (uid,))
        count = cursor.execute('SELECT count FROM warns WHERE user_id = ?', (uid,)).fetchone()[0]
        conn.commit()
        conn.close()

        if count >= 5:
            try:
                bot.ban_chat_member(m.chat.id, uid)
                bot.send_message(m.chat.id, f"❌ <a href='tg://user?id={uid}'>Foydalanuvchi</a> 5 ta ogohlantirishdan keyin guruhdan haydaldi.", parse_mode="HTML")
            except:
                pass
        else:
            reason = "reklama" if has_link else "haqoratli so'z"
            bot.send_message(m.chat.id, f"⚠️ <a href='tg://user?id={uid}'>Foydalanuvchi</a>, guruhda {reason} ishlatmang!\nOgohlantirish: {count}/5", parse_mode="HTML")

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling(skip_pending=True)
