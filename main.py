from flask import Flask, request
import requests, os, tempfile, re, sys, threading
from urllib.parse import urlparse, parse_qs

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
        send_message(chat_id, "⚠️ That doesn’t look like a Terabox link.")
    return {"ok": True}


# ✅ Telegram helpers
def send_message(chat_id, text):
    requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": text})


def send_video(chat_id, file_path):
    with open(file_path, "rb") as f:
        requests.post(f"{API_URL}/sendVideo", data={"chat_id": chat_id}, files={"video": f})


def debug_log(chat_id, text):
    try:
        requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": text[:3500]})
    except:
        pass


# ✅ Worker
def process_video(chat_id, url):
    try:
        video_url = extract_video_url(url, chat_id)
        if video_url:
            send_message(chat_id, f"✅ Found Video Link:\n{video_url}")
            # If file small enough, download & send
            path = download_video(video_url)
            if path:
                send_video(chat_id, path)
                os.remove(path)
        else:
            send_message(chat_id, "⚠️ Could not extract valid video link.")
    except Exception as e:
        print("❌ Exception:", e, flush=True)
        send_message(chat_id, "⚠️ Could not extract valid video link.")


def extract_video_url(url: str, chat_id=None):
    res = requests.get(url, headers=MOBILE_HEADERS, timeout=30)
    html = res.text

    # Extract og:image
    m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
    if not m:
        if chat_id:
            debug_log(chat_id, "❌ og:image not found")
        return None

    og_image = m.group(1)
    if chat_id:
        debug_log(chat_id, f"🔎 og:image:\n{og_image}")

    # Parse query params
    parsed = urlparse(og_image)
    params = parse_qs(parsed.query)

    fid = params.get("fid", [""])[0]
    sign = params.get("sign", [""])[0]
    ts = params.get("time", [""])[0]
    vuk = params.get("vuk", [""])[0]

    if not all([fid, sign, ts, vuk]):
        if chat_id:
            debug_log(chat_id, f"❌ Missing params: fid={fid}, sign={sign}, time={ts}, vuk={vuk}")
        return None

    # Build test streaming link
    video_url = f"https://data.1024tera.com/streaming?fid={fid}&time={ts}&sign={sign}&vuk={vuk}"
    return video_url


def download_video(video_url):
    try:
        r = requests.get(video_url, stream=True, timeout=60)
        r.raise_for_status()
        fd, path = tempfile.mkstemp(suffix=".mp4")
        with os.fdopen(fd, "wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                f.write(chunk)
        return path
    except Exception as e:
        print("❌ Download error:", e, flush=True)
        return None


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
