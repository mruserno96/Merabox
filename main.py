from flask import Flask, request
import requests, os, tempfile, re, json, threading, sys

# Force log flushing
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

    print(f"🔎 Received text: {text}", flush=True)

    if any(domain in text for domain in VALID_DOMAINS):
        send_message(chat_id, "⏱ Processing your link... Please wait.")
        threading.Thread(target=process_video, args=(chat_id, text)).start()
    else:
        send_message(chat_id, "⚠️ That doesn’t look like a Terabox link.\nValid domains:\n- 1024tera.com\n- terabox.fun\n- terabox.app\n- teraboxapp.com")

    return {"ok": True}


# ✅ Telegram helpers
def send_message(chat_id, text):
    requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": text})


def send_video(chat_id, file_path):
    with open(file_path, "rb") as f:
        requests.post(f"{API_URL}/sendVideo", data={"chat_id": chat_id}, files={"video": f})


def debug_log(chat_id, text):
    """Send debug info directly to Telegram (for free Render plan)"""
    try:
        requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": text[:3500]})
    except:
        pass


# ✅ Background processor
def process_video(chat_id, url):
    try:
        video_path = extract_and_download(url, chat_id)
        if video_path:
            send_video(chat_id, video_path)
            os.remove(video_path)
        else:
            send_message(chat_id, "⚠️ Could not extract valid video link.")
    except Exception as e:
        print("❌ Exception:", e, flush=True)
        send_message(chat_id, "⚠️ Could not extract valid video link.")


# ✅ URL normalizer
def normalize_url(url: str) -> str:
    # don’t convert wap/filelist to /share anymore — handle directly
    return url


# ✅ Extractor
def extract_and_download(url: str, chat_id=None):
    session = requests.Session()

    # Use mobile headers for WAP links
    if "/wap/share/filelist" in url:
        res = session.get(url, headers=MOBILE_HEADERS, allow_redirects=True, timeout=30)
    else:
        res = session.get(url, allow_redirects=True, timeout=30)

    html = res.text
    print("🔎 Full HTML Length:", len(html), flush=True)
    if chat_id:
        debug_log(chat_id, f"🔎 HTML Length: {len(html)}")
        debug_log(chat_id, "🔎 HTML Dump (first 5000 chars):\n" + html[:5000])

    # Right now only debugging, not extracting
    return None


# ✅ Collect links recursively (future use)
def collect_video_links(obj):
    links = []
    def _scan(o):
        if isinstance(o, dict):
            for v in o.values():
                _scan(v)
        elif isinstance(o, list):
            for i in o:
                _scan(i)
        elif isinstance(o, str):
            if any(ext in o for ext in [".mp4", ".mkv", ".webm", ".mov"]):
                links.append(o.replace("\\u002F", "/"))
    _scan(obj)
    return links


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
