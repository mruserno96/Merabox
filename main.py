from flask import Flask, request
import requests, os, tempfile, re, threading

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

VALID_DOMAINS = [
    "1024tera.com",
    "terabox.fun",
    "terabox.app",
    "teraboxapp.com",
    "1024terabox.com",
]

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "✅ Terabox Downloader Bot Running"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    if "message" not in data:
        return {"ok": True}

    chat_id = data["message"]["chat"]["id"]
    text = data["message"].get("text", "")

    if text == "/start":
        send_message(chat_id, "👋 Welcome!\nSend me a Terabox link and I’ll fetch the highest quality video for you.")
        return {"ok": True}

    if any(domain in text for domain in VALID_DOMAINS):
        # Fast reply
        send_message(chat_id, "⏱ Processing your link... Please wait.")

        # Background thread for heavy work
        threading.Thread(target=process_video, args=(chat_id, text)).start()
    else:
        send_message(chat_id, "⚠️ Please send a valid Terabox link.")

    return {"ok": True}


def send_message(chat_id, text):
    requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": text})


def send_video(chat_id, file_path):
    with open(file_path, "rb") as f:
        requests.post(f"{API_URL}/sendVideo", data={"chat_id": chat_id}, files={"video": f})


def process_video(chat_id, url):
    try:
        video_path = extract_and_download(url)
        if video_path:
            send_video(chat_id, video_path)
            os.remove(video_path)
        else:
            send_message(chat_id, "⚠️ Could not extract valid video link.")
    except Exception as e:
        print("❌ Exception:", e)
        send_message(chat_id, "⚠️ Could not extract valid video link.")


def extract_and_download(url: str):
    session = requests.Session()
    res = session.get(url, allow_redirects=True, timeout=30)
    html = res.text
    print("Resolved URL:", res.url)

    # Extract surl
    surl = re.search(r"surl=([a-zA-Z0-9_-]+)", url)
    if not surl:
        print("❌ surl not found in URL")
        return None

    api = f"https://www.1024tera.com/api/play/playinfo?surl={surl.group(1)}"
    print("📡 Calling API:", api)

    r = session.get(api, timeout=30)
    if r.status_code != 200:
        print("❌ API status:", r.status_code, r.text[:200])
        return None

    try:
        data = r.json()
    except Exception as e:
        print("❌ JSON decode failed:", str(e))
        print("Response content:", r.text[:500])
        return None

    # Collect video links
    links = []
    def collect(obj):
        if isinstance(obj, dict):
            for v in obj.values():
                collect(v)
        elif isinstance(obj, list):
            for i in obj:
                collect(i)
        elif isinstance(obj, str):
            if any(ext in obj for ext in [".mp4", ".mkv", ".webm", ".mov"]):
                links.append(obj)

    collect(data)
    if not links:
        print("⚠️ No video links found in API response")
        return None

    # Choose highest quality
    pref = ["1080", "720", "480", "360"]
    selected = next((l for q in pref for l in links if q in l), links[0])
    print("🎬 Selected:", selected)

    vres = session.get(selected, stream=True, timeout=120)
    if vres.status_code == 200:
        tmp = tempfile.mktemp(suffix=".mp4")
        with open(tmp, "wb") as f:
            for chunk in vres.iter_content(1024*1024):
                if chunk:
                    f.write(chunk)
        return tmp

    return None


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
