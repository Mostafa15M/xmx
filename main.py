import os
import time
import csv
import re
import cv2
import numpy as np
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import easyocr
from scipy import stats
import requests
import random
from collections import deque

# ===== CONFIG =====
TELEGRAM_TOKEN = "7044109545:AAF_2u9_HqVGZzFIubnIWCQ3dFm7MyQfmWw"
CHAT_ID = "5773032750"
CSV_FILE = "crash_odds_PRO.csv"
WORKING_PROXIES_FILE = "working_proxies.txt"

# قائمة proxies (أضفت بعض جديدة شغالة نسبياً 2026)
PROXY_LIST = [
    {"server": "socks5://206.189.92.74:7777"},
    {"server": "socks5://128.199.111.243:34418"},
    {"server": "socks5://47.241.61.60:9050"},
    {"server": "socks5://51.79.156.122:9050"},
    {"server": "http://128.199.202.122:3128"},
    {"server": "http://51.79.135.131:8080"},
    {"server": "http://152.42.213.210:8080"},
    {"server": "http://143.42.66.91:80"},
    {"server": "http://8.219.97.248:80"},
    # أضف المزيد لو لقيت
]

# روابط crash محدثة 2026 (مرايا شغالة في مصر/المغرب)
CRASH_URLS = [
    "https://ma-1xbet.com/en/games/crash",
    "https://ma-1xbet.com/en/games/crash-point",
    "https://1xbetmaroc.com/en/games/crash",
    "https://egyptonex.com/en/mirror-1xbet",  # mirror entry ثم navigate
    "https://1xbets.plus/en/games/crash",
    "https://1x-bet.mobi/en/games/crash",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
]

class CrashPredictor:
    def __init__(self):
        self.odds_history = deque(maxlen=200)
        self.streaks = {'low': 0, 'mid': 0, 'high': 0}

    def add_odd(self, odd):
        try:
            odd_val = float(odd)
            self.odds_history.append(odd_val)
            self.update_streaks(odd_val)
        except:
            pass

    def update_streaks(self, odd):
        self.streaks = {'low': 0, 'mid': 0, 'high': 0}
        for o in list(self.odds_history)[-10:]:
            if o < 2.0: self.streaks['low'] += 1
            elif o < 5.0: self.streaks['mid'] += 1
            else: self.streaks['high'] += 1

    def predict(self):
        if len(self.odds_history) < 15:
            return "⏳ انتظر", 0.4, 0.0

        recent = list(self.odds_history)[-30:]
        x = np.arange(len(recent))

        predictions = []
        try:
            slope, intercept, r_value, _, _ = stats.linregress(x, recent)
            lin_pred = max(1.1, intercept + slope * (len(recent) + 1))
            predictions.append(lin_pred * (0.7 + r_value**2 * 0.3))
        except:
            pass

        alpha = 0.3
        ema = recent[0]
        for val in recent[1:]:
            ema = alpha * val + (1 - alpha) * ema
        predictions.append(ema * 1.1)

        streak_boost = 1.0
        if self.streaks['low'] >= 5: streak_boost = 2.2
        elif self.streaks['low'] >= 3: streak_boost = 1.6
        elif self.streaks['high'] >= 4: streak_boost = 0.75

        final_pred = np.mean(predictions) * streak_boost if predictions else np.mean(recent)
        confidence = min(0.92, 0.4 + len(recent)/200 + abs(streak_boost-1)*0.3)

        if final_pred > 4.0 and confidence > 0.8:
            return "🚀 شراء قوي", confidence, final_pred
        elif final_pred > 2.4 and confidence > 0.7:
            return "✅ شراء", confidence, final_pred
        else:
            return "⏳ انتظر", confidence, final_pred


def preprocess_image(image):
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8,8))
    l = clahe.apply(l)
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    sharpened = cv2.filter2D(l, -1, kernel)
    l = cv2.addWeighted(l, 0.7, sharpened, 0.3, 0)
    enhanced = cv2.merge([l, a, b])
    enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
    enhanced = cv2.fastNlMeansDenoisingColored(enhanced, None, 10, 10, 7, 21)
    return enhanced


def extract_odd_from_image(image_path):
    try:
        reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        img = cv2.imread(image_path)
        if img is None:
            return None

        # regions محسنة لـ multiplier live (من وسط/أعلى الشاشة)
        height, width = img.shape[:2]
        regions = [
            img[int(height*0.15):int(height*0.45), int(width*0.35):int(width*0.65)],  # multiplier كبير وسط
            img[int(height*0.1):int(height*0.3), int(width*0.4):int(width*0.6)],     # أعلى
            img[int(height*0.2):int(height*0.5), int(width*0.3):int(width*0.7)],
            img[100:400, 600:1300],
            img[200:500, 700:1200],
        ]

        all_texts = []
        for region in regions:
            if region.size == 0:
                continue
            processed = preprocess_image(region)
            results = reader.readtext(processed)
            all_texts.extend(results)

        candidates = []
        for (_, text, conf) in all_texts:
            if conf > 0.22:  # خفضت شوية عشان نلقط أكتر
                match = re.search(r'(\d+\.?\d*)[xX]?', text, re.IGNORECASE)
                if match:
                    try:
                        odd = float(match.group(1))
                        if 1.01 <= odd <= 1000:
                            candidates.append((odd, conf))
                    except:
                        continue

        if candidates:
            best = max(candidates, key=lambda x: x[1])
            print(f"اكتشاف odd: {best[0]:.2f}x (ثقة {best[1]:.2f}) من {os.path.basename(image_path)}")
            return f"{best[0]:.2f}"
        else:
            print("ما لقاش odd في الصورة")
    except Exception as e:
        print(f"خطأ OCR: {e}")
    return None


def send_telegram(message, image_paths=None):
    base_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

    text_url = f"{base_url}/sendMessage"
    text_data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(text_url, data=text_data, timeout=15)
        print("تم إرسال الرسالة")
    except Exception as e:
        print(f"فشل الإرسال: {e}")

    if image_paths:
        photo_url = f"{base_url}/sendPhoto"
        for i, path in enumerate(image_paths):
            if os.path.exists(path):
                try:
                    with open(path, 'rb') as photo:
                        files = {'photo': photo}
                        data = {'chat_id': CHAT_ID, 'caption': f"صورة {i+1}/{len(image_paths)} - {os.path.basename(path)}"}
                        requests.post(photo_url, data=data, files=files, timeout=20)
                    print(f"تم إرسال الصورة {i+1}")
                    if i < len(image_paths) - 1:
                        time.sleep(25)
                except Exception as e:
                    print(f"فشل الصورة {i+1}: {e}")


def load_csv_data():
    data = []
    if os.path.exists(CSV_FILE):
        try:
            with open(CSV_FILE, 'r') as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if len(row) >= 2:
                        try:
                            data.append(float(row[1]))
                        except:
                            pass
        except:
            pass
    return data


def save_to_csv(odd):
    try:
        file_exists = os.path.exists(CSV_FILE)
        with open(CSV_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['timestamp', 'odd'])
            writer.writerow([datetime.now().isoformat(), odd])
        print(f"تم حفظ: {odd}")
    except Exception as e:
        print(f"خطأ CSV: {e}")


def save_working_proxy(proxy):
    with open(WORKING_PROXIES_FILE, 'a') as f:
        f.write(f"{proxy['server']}\n")


def get_random_proxy():
    if os.path.exists(WORKING_PROXIES_FILE):
        with open(WORKING_PROXIES_FILE, 'r') as f:
            lines = [line.strip() for line in f if line.strip()]
            if lines:
                return {"server": random.choice(lines)}
    return random.choice(PROXY_LIST) if PROXY_LIST else None


def run_once():
    print("البوت شغال - تحديث مارس 2026: wait أطول + OCR محسن")
    predictor = CrashPredictor()
    history = load_csv_data()
    predictor.odds_history.extend(history[-200:])
    print(f"تم تحميل {len(predictor.odds_history)} odd سابقة")

    odd = None
    screenshots = []
    used_url = ""
    used_proxy = ""

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])

            for url in CRASH_URLS:
                print(f"\nجاري تجربة: {url}")
                proxy = get_random_proxy()
                print(f"  باستخدام proxy: {proxy['server'] if proxy else 'بدون proxy'}")

                try:
                    context_args = {
                        'user_agent': random.choice(USER_AGENTS),
                        'viewport': {'width': 1920, 'height': 1080},
                        'ignore_https_errors': True,
                        'bypass_csp': True,
                        'java_script_enabled': True,
                    }
                    if proxy:
                        context_args['proxy'] = proxy

                    context = browser.new_context(**context_args)
                    page = context.new_page()

                    page.goto(url, wait_until="domcontentloaded", timeout=300000)

                    try:
                        page.wait_for_load_state("networkidle", timeout=180000)  # انتظر network هادئ
                    except:
                        print("networkidle timeout - reload...")
                        page.reload(wait_until="domcontentloaded", timeout=120000)

                    # انتظر طويل عشان اللعبة تحمل (JS/WebSocket/canvas)
                    print("انتظار تحميل اللعبة الكامل (3-5 دقايق)...")
                    time.sleep(random.uniform(180, 300))

                    # حاول wait لـ live multiplier selector
                    selectors = [
                        '[class*="multiplier"]', '.current-multiplier', '.multiplier-value',
                        '.crash-multiplier', 'div[class*="multi"]', 'span.multiplier',
                        'canvas', '[data-testid="multiplier"]'
                    ]
                    found = False
                    for sel in selectors:
                        try:
                            page.wait_for_selector(sel, timeout=120000, state="visible")
                            print(f"تم العثور على selector: {sel}")
                            found = True
                            break
                        except:
                            pass

                    if not found:
                        print("ما لقاش selector live - هنجرب screenshots على أي حال")

                    # خد screenshots متعددة مع فواصل (عشان نلقط round)
                    for i in range(10):  # 10 shots
                        path = f"debug_shot_{url.split('/')[-1]}_{i}_{int(time.time())}.png"
                        try:
                            page.screenshot(path=path, full_page=True, timeout=90000)
                            screenshots.append(path)
                            print(f"تم التقاط shot {i+1}")
                        except Exception as e:
                            print(f"خطأ screenshot {i+1}: {e}")
                        time.sleep(random.uniform(20, 35))  # انتظر round جديد

                    # استخراج odd من الصور
                    for scr in screenshots:
                        if os.path.exists(scr):
                            detected = extract_odd_from_image(scr)
                            if detected:
                                odd = detected
                                used_url = url
                                used_proxy = proxy['server'] if proxy else "بدون"
                                if proxy:
                                    save_working_proxy(proxy)
                                break

                    if odd:
                        break

                    context.close()

                except Exception as e:
                    print(f"فشل على {url} مع {proxy['server'] if proxy else 'no proxy'}: {str(e)}")
                    time.sleep(15)

            browser.close()

    except Exception as e:
        print(f"خطأ عام في run_once: {str(e)}")

    images_to_send = [p for p in screenshots if os.path.exists(p)][:8]  # max 8 صور

    if odd:
        save_to_csv(odd)
        predictor.add_odd(odd)
        signal, conf, pred = predictor.predict()

        msg = f"""
<b>نجاح! استخراج odd من Crash</b>

URL: {used_url}
Proxy: {used_proxy}
odd الحالي: <code>{odd}x</code>
إشارة: {signal}
هدف مقترح: <code>{pred:.2f}x</code>
ثقة: <code>{conf:.0%}</code>
وقت: {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}
"""
        send_telegram(msg, images_to_send)
    else:
        msg = f"""
<b>ما زال ما لقاش odd live</b>

جربنا {len(CRASH_URLS)} روابط + proxies
اللعبة حملت lobby بس مش animation/live multiplier
تحقق الصور - ممكن تحتاج VPN أقوى أو APK emulator
وقت: {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}
"""
        send_telegram(msg, images_to_send)


if __name__ == "__main__":
    print("البوت محدث - wait طويل + selectors محسنة + OCR أفضل")
    while True:
        try:
            run_once()
        except KeyboardInterrupt:
            print("تم إيقاف البوت")
            break
        except Exception as e:
            print(f"خطأ في الحلقة: {e}")
            time.sleep(300)

        wait = random.uniform(240, 480)  # 4-8 دقايق
        print(f"التشغيل التالي بعد ≈ {wait//60:.0f} دقيقة")
        time.sleep(wait)
