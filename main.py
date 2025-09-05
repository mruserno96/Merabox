from flask import Flask, request
import os, requests, re, threading, json, tempfile, sys

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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
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
        send_message(chat_id, "👋 Welcome!\nSend me a Terabox /share/filelist?surl=XXXXX link and I’ll fetch the video link.")
        return {"ok": True}

    if any(domain in text for domain in VALID_DOMAINS):
        send_message(chat_id, "⏱ Processing your link... Please wait.")
        threading.Thread(target=process_video, args=(chat_id, text)).start()
    else:
        send_message(chat_id, "⚠️ That doesn’t look like a valid Terabox link.")
    return {"ok": True}


# ================= Helper Functions =================
def send_message(chat_id, text):
    requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": text})

def send_video(chat_id, file_path):
    with open(file_path, "rb") as f:
        requests.post(f"{API_URL}/sendVideo", data={"chat_id": chat_id}, files={"video": f})

def fetch_html(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print("❌ Fetch HTML error:", e, flush=True)
        return None


# ================= Core Processing =================
def process_video(chat_id, url):
    html = fetch_html(url)
    if not html:
        send_message(chat_id, "⚠️ Could not fetch page HTML.")
        return

    # Extract playinfo API JSON from HTML <script> block
    match = re.search(r'window\.file_list\s*=\s*(\{.*?\}|\[.*?\]);', html, re.DOTALL)
    if not match:
        send_message(chat_id, "⚠️ Could not extract file_list from HTML.")
        return

    try:
        file_list = json.loads(match.group(1))
    except Exception as e:
        send_message(chat_id, f"❌ JSON parse error: {e}")
        return

    # Pick first file
    file0 = file_list[0] if isinstance(file_list, list) else list(file_list.values())[0]

    fs_id = file0.get("fs_id")
    sign = file0.get("sign")
    uk = file0.get("uk")
    timestamp = file0.get("time") or 0
    surl = file0.get("surl") or ""

    if not all([fs_id, sign, uk]):
        send_message(chat_id, "⚠️ Missing required parameters to generate video link.")
        return

    # Build playable video URL
    video_url = f"https://www.1024tera.com/api/play/playinfo?app_id=250528&fid_list=[{fs_id}]&sign={sign}&timestamp={timestamp}&uk={uk}&surl={surl}"
    send_message(chat_id, f"✅ Playable Video URL:\n{video_url}")

    # Optional: download video (size <50MB)
    path = download_video(video_url)
    if path:
        send_video(chat_id, path)
        os.remove(path)


def download_video(video_url):
    try:
        r = requests.get(video_url, stream=True, timeout=60)
        r.raise_for_status()
        fd, path = tempfile.mkstemp(suffix=".mp4")
        with os.fdopen(fd, "wb") as f:
            for chunk in r.iter_content(1024*1024):
                f.write(chunk)
        return path
    except Exception as e:
        print("❌ Download error:", e, flush=True)
        return None


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
