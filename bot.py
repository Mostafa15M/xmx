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

# ================== الإعدادات ===================
TOKEN = '7044109545:AAF_2u9_HqVGZzFIubnIWCQ3dFm7MyQfmWw'
CHAT_ID = 5773032750
FILE_NAME = "odds_history.csv"

WSS = None
WS_THREAD = None

# ================== الوظائف المساعدة ===================
def send_msg(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    except Exception as e:
        print(f"Error: {e}")

def save_odds(value):
    with open(FILE_NAME, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([value])

# ================== استقبال البيانات ===================
def on_message(ws, message):
    try:
        multiplier = None
        # محاولة البحث عن رقم عشري في الرسالة (الأكثر ضماناً)
        numbers = re.findall(r"(\d+\.\d+)", message)
        if numbers:
            multiplier = float(numbers[0])
        
        if multiplier and multiplier > 0:
            save_odds(multiplier)
            send_msg(f"🚀 *Crash:* {multiplier}x")
    except:
        pass

def on_open(ws):
    send_msg("✅ *تم الاتصال بنجاح!* البوت يراقب الجولات الآن...")

def start_ws():
    global WSS
    if not WSS: return
    # تصحيح الرابط تلقائياً
    final_url = WSS.replace("Wss://", "wss://").replace("WSS://", "wss://")
    ws = websocket.WebSocketApp(final_url, on_message=on_message, on_open=on_open)
    ws.run_forever()

# ================== أوامر التيليجرام ===================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 أرسل `/setwss [الرابط]` للبدء أو `/stats` للتحليل.")

async def setwss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global WSS, WS_THREAD
    if not context.args:
        await update.message.reply_text("⚠️ أرسل الرابط بعد الأمر!")
        return
    WSS = context.args[0]
    await update.message.reply_text("⏳ جاري محاولة الاتصال...")
    WS_THREAD = threading.Thread(target=start_ws, daemon=True)
    WS_THREAD.start()

# --- دالة التحليل المصححة (تحل مشكلة الـ Concatenate) ---
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists(FILE_NAME):
        await update.message.reply_text("❌ لا توجد بيانات مسجلة بعد.")
        return
    try:
        # قراءة البيانات وتسمية العمود
        df = pd.read_csv(FILE_NAME, names=["multiplier"])
        if df.empty:
            await update.message.reply_text("📭 الملف فارغ.")
            return

        total = len(df)
        avg = df["multiplier"].mean()
        high = len(df[df["multiplier"] > 2])
        low = len(df[df["multiplier"] <= 2])

        # استخدام f-string يحول الأرقام لنصوص تلقائياً ويمنع الخطأ
        report = (
            f"📊 *تقرير تحليل Crash:*\n\n"
            f"🔢 إجمالي الجولات: {total}\n"
            f"📈 المتوسط: {avg:.2f}x\n"
            f"🟢 جولات مرتفعة (> 2x): {high}\n"
            f"🔴 جولات منخفضة (<= 2x): {low}"
        )
        await update.message.reply_text(report, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"⚠️ خطأ في التحليل: {str(e)}")

# ================== التشغيل ===================
if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setwss", setwss))
    app.add_handler(CommandHandler("stats", stats))
    
    print("Bot is running...")
    app.run_polling()
