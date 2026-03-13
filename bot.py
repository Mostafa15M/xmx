import json
import websocket
import threading
import requests
import csv
import re
import os
import pandas as pd
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ================== إعدادات البوت ===================
TOKEN = '7044109545:AAF_2u9_HqVGZzFIubnIWCQ3dFm7MyQfmWw'
CHAT_ID = 5773032750  # سيتم إرسال النتائج لهذا الحساب تلقائياً

WSS = None
WS_THREAD = None
FILE_NAME = "odds_history.csv"

# ================== وظائف مساعدة ===================
def send_msg(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    except Exception as e:
        print(f"Telegram Error: {e}")

def save_odds(value):
    # حفظ الرقم في ملف CSV
    file_exists = os.path.isfile(FILE_NAME)
    with open(FILE_NAME, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([value])

# ================== معالجة رسائل السيرفر ===================
def on_message(ws, message):
    try:
        multiplier = None
        # 1. محاولة استخراج الرقم لو كان JSON
        try:
            data = json.loads(message)
            multiplier = data.get("f", {}).get("m") or data.get("m")
        except:
            pass

        # 2. محاولة استخراج الرقم باستخدام Regex (صائد الأرقام)
        if multiplier is None:
            numbers = re.findall(r"(\d+\.\d+)", message)
            if numbers:
                multiplier = float(numbers[0])

        # 3. إذا وجدنا رقم (أكبر من 0) نقوم بحفظه وإرساله
        if multiplier and multiplier > 0:
            save_odds(multiplier)
            send_msg(f"🚀 *Crash:* {multiplier}x")
            print(f"✅ Captured: {multiplier}")

    except Exception as e:
        print(f"⚠️ Error: {e}")

def on_error(ws, error):
    print(f"❌ WS Error: {error}")

def on_open(ws):
    send_msg("✅ *تم الاتصال بنجاح!* البوت يراقب الجولات الآن...")

def start_ws():
    global WSS
    if not WSS: return
    # تصحيح الرابط تلقائياً
    final_url = WSS.replace("Wss://", "wss://").replace("WSS://", "wss://")
    ws = websocket.WebSocketApp(final_url, on_message=on_message, on_error=on_error, on_open=on_open)
    ws.run_forever()

# ================== أوامر التيليجرام ===================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 أهلاً يا درش! أرسل `/setwss [الرابط]` للبدء أو `/stats` للتحليل.")

async def setwss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global WSS, WS_THREAD
    if not context.args:
        await update.message.reply_text("⚠️ أرسل الرابط بعد الأمر!")
        return
    WSS = context.args[0]
    await update.message.reply_text("⏳ جاري الاتصال...")
    WS_THREAD = threading.Thread(target=start_ws, daemon=True)
    WS_THREAD.start()

# --- دالة التحليل باستخدام Pandas ---
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists(FILE_NAME):
        await update.message.reply_text("❌ لا توجد بيانات مسجلة بعد.")
        return
    try:
        # قراءة البيانات
        df = pd.read_csv(FILE_NAME, names=["multiplier"])
        if df.empty:
            await update.message.reply_text("📭 الملف فارغ.")
            return

        avg = df["multiplier"].mean()
        high = len(df[df["multiplier"] > 2])
        low = len(df[df["multiplier"] <= 2])
        total = len(df)

        report = (
            f"📊 *Crash Analysis Report:*\n\n"
            f"🔢 Total Rounds: {total}\n"
            f"📈 Average: {avg:.2f}x\n"
            f"🟢 High (> 2x): {high}\n"
            f"🔴 Low (<= 2x): {low}"
        )
        await update.message.reply_text(report, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"⚠️ خطأ في التحليل: {e}")

# ================== التشغيل الأساسي ===================
if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setwss", setwss))
    app.add_handler(CommandHandler("stats", stats)) # إضافة أمر التحليل
    
    print("Bot is running...")
    app.run_polling()
