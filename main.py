from flask import Flask, request
import requests, os, re, threading, sys

sys.stdout.reconfigure(line_buffering=True)

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

VALID_DOMAINS = [
    "1024tera.com",
    "terabox.fun",
    "terabox.app",
    "teraboxapp.com",
    "1024terabox.com",
]

MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"
}

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "✅ Terabox Downloader Bot Running"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    print("📩 Incoming update:", data, flush=True)

    if "message" not in data:
        return {"ok": True}

    chat_id = data["message"]["chat"]["id"]
    text = data["message"].get("text", "").strip()

    if text == "/start":
        send_message(chat_id, "👋 Welcome!\nSend me a Terabox link and I’ll fetch the highest quality video for you.")
        return {"ok": True}

    if any(domain in text for domain in VALID_DOMAINS):
        send_message(chat_id, "⏱ Processing your link... Please wait.")
        threading.Thread(target=process_video, args=(chat_id, text)).start()
    else:
        send_message(chat_id, "⚠️ That doesn’t look like a Terabox link.")
    return {"ok": True}


# ✅ Telegram helpers
def send_message(chat_id, text):
    requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": text})


def debug_log(chat_id, text):
    try:
        requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": text[:3500]})
    except:
        pass


# ✅ Worker
def process_video(chat_id, url):
    try:
        html = fetch_html(url)
        if not html:
            send_message(chat_id, "⚠️ Could not fetch page HTML.")
            return

        # Extract <script> blocks containing window.file_list or window.playInfo
        scripts = re.findall(r'<script.*?>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
        target_scripts = []
        for s in scripts:
            if "window.file_list" in s or "window.playInfo" in s:
                target_scripts.append(s.strip())

        if not target_scripts:
            send_message(chat_id, "⚠️ Could not find file_list / playInfo scripts.")
            return

        for i, scr in enumerate(target_scripts):
            debug_log(chat_id, f"🔎 Script Block {i+1} (first 3000 chars):\n{scr[:3000]}")

        send_message(chat_id, f"✅ Extracted {len(target_scripts)} script block(s). Use these to generate video link next.")

    except Exception as e:
        print("❌ Exception:", e, flush=True)
        send_message(chat_id, "⚠️ Error while processing link.")


def fetch_html(url):
    try:
        res = requests.get(url, headers=MOBILE_HEADERS, timeout=30)
        res.raise_for_status()
        return res.text
    except Exception as e:
        print("❌ Fetch HTML error:", e, flush=True)
        return None


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
