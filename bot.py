import json
import websocket
import threading
import requests
import csv
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ================== إعدادات البوت ===================
TOKEN = '7044109545:AAF_2u9_HqVGZzFIubnIWCQ3dFm7MyQfmWw'
CHAT_ID = 5773032750

WSS = None
WS_THREAD = None

# ================== وظائف مساعدة ===================
def send_msg(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    except Exception as e:
        print(f"Telegram Error: {e}")

def save_odds(value):
    with open("odds_history.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([value])

# ================== معالجة رسائل السيرفر ===================
def on_message(ws, message):
    try:
        # طباعة الرسالة الخام في الـ Logs للمراقبة
        print(f"📡 Raw Message: {message}")
        
        multiplier = None

        # 1. محاولة استخراج الرقم لو كان JSON صريح
        try:
            data = json.loads(message)
            # جلب الرقم من المسارات المشهورة في 1x
            multiplier = data.get("f", {}).get("m") or data.get("m") or data.get("multiplier")
        except:
            pass

        # 2. محاولة استخراج الرقم باستخدام النمط (Regex) لو كان النص مختلطاً برمز
        if multiplier is None:
            # يبحث عن أي رقم عشري مثل 1.50 أو 2.0
            numbers = re.findall(r"(\d+\.\d+)", message)
            if numbers:
                # نأخذ أول رقم عشري يظهر في الرسالة
                multiplier = float(numbers[0])

        # 3. إذا وجدنا رقم، نقوم بإرساله وحفظه
        if multiplier:
            # نتجاهل الأرقام الصغيرة جداً التي قد تكون تعريفية (مثل 1.0 أو 0.0)
            if multiplier > 0:
                save_odds(multiplier)
                send_msg(f"🚀 Crash: {multiplier}x")
                print(f"✅ Captured Multiplier: {multiplier}")

    except Exception as e:
        print(f"⚠️ Error processing message: {e}")

def on_error(ws, error):
    print(f"❌ WebSocket Error: {error}")

def on_open(ws):
    print("✅ Connected to Server!")
    send_msg("✅ تم الاتصال بنجاح! البوت الآن يراقب اللعبة...")

def start_ws():
    global WSS
    if not WSS: return

    # تصحيح الرابط تلقائياً (Wss -> wss)
    final_url = WSS
    if final_url.lower().startswith("wss"):
        final_url = "wss" + final_url[3:]

    ws = websocket.WebSocketApp(
        final_url,
        on_message=on_message,
        on_error=on_error,
        on_open=on_open
    )
    ws.run_forever()

# ================== أوامر التيليجرام ===================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 مرحبًا بك في بوت Crash!\n"
        "أرسل الرابط باستخدام الأمر:\n"
        "`/setwss [الرابط]`"
    , parse_mode='Markdown')

async def setwss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global WSS, WS_THREAD
    if not context.args:
        await update.message.reply_text("⚠️ من فضلك أرسل الرابط بعد الأمر.")
        return
    
    WSS = context.args[0]
    await update.message.reply_text("⏳ جاري محاولة فتح اتصال جديد...")

    # تشغيل في خلفية البرنامج
    WS_THREAD = threading.Thread(target=start_ws, daemon=True)
    WS_THREAD.start()

# ================== تشغيل البوت ===================
if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setwss", setwss))
    
    print("Bot is running... Waiting for WSS link.")
    app.run_polling()
