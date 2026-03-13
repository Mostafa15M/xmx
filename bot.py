import json
import websocket
import threading
import requests
import csv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ================== معلومات البوت ===================
API_ID = 34840178
API_HASH = 'ebcc84fa3c5b119f87dfe8884a4d5659'
TOKEN = '7044109545:AAF_2u9_HqVGZzFIubnIWCQ3dFm7MyQfmWw'
CHAT_ID = 5773032750

WSS = None
WS_THREAD = None

# ================== Helper functions ===================
def send(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

def save_odds(value):
    with open("odds_history.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([value])

# ================== WebSocket functions ===================
def start_ws():
    global WSS
    if not WSS:
        send("ℹ️ Please send WSS using /setwss command.")
        return

    def on_message(ws, message):
        try:
            data = json.loads(message)
            multiplier = data.get("multiplier")
            if multiplier:
                save_odds(multiplier)
            send(f"📊 Crash: {multiplier}x")
        except:
            send(f"📡 Raw Message:\n{message}")

    def on_close(ws, close_status_code, close_msg):
        send("⚠️ WebSocket disconnected. Send new WSS with /setwss")
        global WS_THREAD
        WS_THREAD = None

    ws = websocket.WebSocketApp(
        WSS,
        on_message=on_message,
        on_close=on_close
    )
    ws.run_forever()

# ================== Telegram commands ===================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Crash WSS Bot\nSend WSS using:\n/setwss wss://server"
    )

async def setwss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global WSS, WS_THREAD
    if not context.args:
        await update.message.reply_text("Usage:\n/setwss wss://server")
        return
    WSS = context.args[0]
    await update.message.reply_text(f"Connecting to WSS:\n{WSS}")

    if WS_THREAD is None:
        WS_THREAD = threading.Thread(target=start_ws)
        WS_THREAD.start()

# ================== Main ===================
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("setwss", setwss))
app.run_polling()
