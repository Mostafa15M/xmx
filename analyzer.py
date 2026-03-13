import pandas as pd
import requests
import os

CHAT_ID = 5773032750
TOKEN = '7044109545:AAF_2u9_HqVGZzFIubnIWCQ3dFm7MyQfmWw'

def send(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url,data={"chat_id": CHAT_ID, "text": msg})

# قراءة الأودات
data = pd.read_csv("odds_history.csv")

avg = data["multiplier"].mean()
high = len(data[data["multiplier"] > 2])
low = len(data[data["multiplier"] <= 2])

msg = f"📊 Crash Analysis:\nAverage: {avg:.2f}\nHigh rounds: {high}\nLow rounds: {low}"

print(msg)
send(msg)
