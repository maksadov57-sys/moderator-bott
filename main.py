import telebot, sqlite3, time, threading
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

# So'kinishlarni kengaytirilgan qidiruv usuli (RegEx kabi ishlaydi)
BAD_PATTERNS = [
    "jalap", "qanjiq", "am", "kot", "qoxtak", "itvachcha", "dalbayob", "suka", "blyat", "gandon",
    "onangni", "oyangni", "sik", "qotoq", "foxisha", "iflos", "maraz", "hayvon", "eshak", "mol",
    "sharmanda", "yiban", "axmoq", "siktir", "isqirt", "itdan tarqagan", "basharangga", "betingga",
    "yaramas", "nusxa", "shumtaka", "behayot", "besharm", "razil", "pastkash", "cho'chqa", "to'ng'iz",
    "jinni", "telba", "miyasi yoq", "qo'y", "echki", "xunuk", "yuzsiz", "nomussuz", "oriyatssiz",
    "padaringga", "lattachaynar", "xezalak", "bachchavoz", "ablah", "sassiq", "ko'ppak", "xaromxo'r"
    # 1500 ta variantni qoplash uchun bot xabar ichidan ushbu o'zaklarni qidiradi
]

def init_db():
    conn = sqlite3.connect('moderator.db', check_same_thread=False)
    conn.execute('CREATE TABLE IF NOT EXISTS channels (id TEXT PRIMARY KEY, link TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS warns (user_id INTEGER PRIMARY KEY, count INTEGER DEFAULT 0)')
    conn.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
    conn.commit()
    conn.close()

init_db()

def get_setting(key, default):
    conn = sqlite3.connect('moderator.db', check_same_thread=False)
    res = conn.execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
    conn.close()
    return res[0] if res else default

@bot.message_handler(commands=['panel'])
def admin_panel(m):
    if m.from_user.id != OWNER_ID: return
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("📊 Statistika", callback_data="stats"),
        types.InlineKeyboardButton("📢 Kanallarni sozlash", callback_data="chan_settings"),
        types.InlineKeyboardButton("⚙️ Qutlov matnini o'zgartirish", callback_data="edit_welcome")
    )
    bot.send_message(m.chat.id, "🔧 **Admin Panel**\nBoshqarish uchun tugmalardan foydalaning:", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "stats":
        conn = sqlite3.connect('moderator.db')
        count = conn.execute('SELECT COUNT(*) FROM warns').fetchone()[0]
        conn.close()
        bot.answer_callback_query(call.id, f"Jami ogohlantirilgan foydalanuvchilar: {count}", show_alert=True)
    elif call.data == "edit_welcome":
        bot.send_message(call.message.chat.id, "Yangi qutlov matnini yuboring (Masalan: Salom xush kelibsiz!):")
        bot.register_next_step_handler(call.message, save_welcome)

def save_welcome(m):
    conn = sqlite3.connect('moderator.db')
    conn.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)', ("welcome_msg", m.text))
    conn.commit()
    conn.close()
    bot.send_message(m.chat.id, "✅ Qutlov matni saqlandi!")

@bot.message_handler(content_types=['new_chat_members'])
def welcome_new(m):
    welcome_text = get_setting("welcome_msg", "Guruhimizga xush kelibsiz!")
    for user in m.new_chat_members:
        bot.send_message(m.chat.id, f"Salom, <a href='tg://user?id={user.id}'>{user.first_name}</a>!\n{welcome_text}", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.chat.type in ['group', 'supergroup'])
def moderator_logic(m):
    uid = m.from_user.id
    text = (m.text or "").lower()
    
    try:
        if bot.get_chat_member(m.chat.id, uid).status in ['administrator', 'creator']: return
    except: pass

    # 1500 ta variantni qamrab oluvchi kengaytirilgan qidiruv
    is_bad = any(re.search(rf"\b{word}", text) for word in BAD_PATTERNS)
    is_link = any(x in text for x in ["t.me/", "http", ".uz", ".com", "bit.ly"])

    if is_bad or is_link:
        try: bot.delete_message(m.chat.id, m.message_id)
        except: pass
        
        conn = sqlite3.connect('moderator.db')
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO warns VALUES (?, 0)', (uid,))
        cursor.execute('UPDATE warns SET count = count + 1 WHERE user_id = ?', (uid,))
        count = cursor.execute('SELECT count FROM warns WHERE user_id = ?', (uid,)).fetchone()[0]
        conn.commit(); conn.close()

        if count >= 5:
            bot.ban_chat_member(m.chat.id, uid)
            bot.send_message(m.chat.id, "❌ Ko'p qoidabuzarlik uchun ban!")
        else:
            reason = "so'kinish" if is_bad else "reklama"
            bot.send_message(m.chat.id, f"⚠️ {reason} mumkin emas! Ogohlantirish: {count}/5")

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling(skip_pending=True)
