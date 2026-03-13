import json
import websocket
import threading
import requests
import csv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ================== معلومات البوت ===================
TOKEN = '7044109545:AAF_2u9_HqVGZzFIubnIWCQ3dFm7MyQfmWw'
CHAT_ID = 5773032750

WSS = None
WS_THREAD = None

# ================== دالة إرسال الرسائل ===================
def send_msg(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    except Exception as e:
        print(f"Error sending to Telegram: {e}")

# ================== دالة حفظ البيانات ===================
def save_odds(value):
    with open("odds_history.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([value])

# ================== منطق الـ WebSocket ===================
def on_message(ws, message):
    try:
        data = json.loads(message)
        # تعديل المسار ليتناسب مع صيغة 1x (f -> m)
        multiplier = data.get("f", {}).get("m")
        
        if multiplier:
            save_odds(multiplier)
            send_msg(f"🚀 Crash Multiplier: {multiplier}x")
            print(f"✅ تم تسجيل رقم: {multiplier}")
        else:
            # طباعة الرسائل الأخرى في الـ Logs للمراقبة فقط
            print(f"📡 بيانات تقنية: {message}")
    except:
        # التعامل مع الرسائل التي ليست بتنسيق JSON (مثل رسائل البنج)
        pass

def on_error(ws, error):
    print(f"❌ WS Error: {error}")

def on_open(ws):
    print("✅ تم الاتصال بالسيرفر بنجاح!")
    send_msg("✅ Connection Established! Monitoring Crash rounds...")

def start_ws():
    global WSS
    if not WSS:
        return

    # تصحيح البروتوكول تلقائياً ليكون سمول (wss)
    if WSS.lower().startswith("wss"):
        final_url = "wss" + WSS[3:]
    else:
        final_url = WSS

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
        "👋 مرحبًا بك يا درش!\n"
        "ارسل رابط الـ WSS باستخدام الأمر:\n"
        "`/setwss [الرابط]`"
    , parse_mode='Markdown')

async def setwss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global WSS, WS_THREAD
    if not context.args:
        await update.message.reply_text("⚠️ يرجى إرسال الرابط بعد الأمر!")
        return
    
    WSS = context.args[0]
    await update.message.reply_text("⏳ جاري محاولة الاتصال...")

    # تشغيل الاتصال في Thread منفصل
    WS_THREAD = threading.Thread(target=start_ws, daemon=True)
    WS_THREAD.start()

# ================== التشغيل الأساسي ===================
if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setwss", setwss))
    
    print("البوت يعمل الآن... في انتظار الرابط.")
    app.run_polling()
