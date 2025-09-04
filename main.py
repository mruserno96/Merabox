from flask import Flask, request
import requests, os, tempfile, re, json

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
VALID_DOMAINS = ["1024tera.com", "terabox.fun", "terabox.app", "teraboxapp.com", "1024terabox.com"]

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "✅ Bot Running"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    if "message" not in data:
        return {"ok": True}
    chat_id = data["message"]["chat"]["id"]
    text = data["message"].get("text", "")

    if text == "/start":
        send_message(chat_id, "👋 Send a valid Terabox link to fetch highest quality video.")
        return {"ok": True}

    if any(domain in text for domain in VALID_DOMAINS):
        send_message(chat_id, "⏱ Processing link…")
        video_path = extract_and_download(text)
        if video_path:
            send_video(chat_id, video_path)
            os.remove(video_path)
        else:
            send_message(chat_id, "⚠️ Could not extract valid video link.")
    else:
        send_message(chat_id, "Send a valid Terabox share link.")

    return {"ok": True}

def send_message(chat_id, text):
    requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": text})

def send_video(chat_id, file_path):
    with open(file_path, "rb") as f:
        requests.post(f"{API_URL}/sendVideo", data={"chat_id": chat_id}, files={"video": f})

def extract_and_download(url: str):
    session = requests.Session()
    res = session.get(url, allow_redirects=True, timeout=30)
    html = res.text
    print("Resolved URL:", res.url)

    shareid = re.search(r"surl=([a-zA-Z0-9_-]+)", url)
    if not shareid:
        print("No surl found")
        return None

    api = f"https://www.1024tera.com/api/play/playinfo?shareid={shareid.group(1)}"
    print("Calling API:", api)
    r = session.get(api, timeout=30)
    if r.status_code != 200:
        print("API failed:", r.status_code)
        return None

    data = r.json()
    links = []
    def collect(obj):
        if isinstance(obj, dict):
            for v in obj.values(): collect(v)
        elif isinstance(obj, list):
            for i in obj: collect(i)
        elif isinstance(obj, str):
            if v := obj.strip():
                links.append(v)

    collect(data)
    video_links = [l for l in links if any(ext in l for ext in [".mp4", ".mkv", ".webm", ".mov"])]
    if not video_links:
        print("No video links in API response")
        return None

    pref = ["1080", "720", "480", "360"]
    selected = next((l for q in pref for l in video_links if q in l), video_links[0])
    print("Selected:", selected)

    vres = session.get(selected, stream=True, timeout=120)
    if vres.status_code == 200:
        tmp = tempfile.mktemp(suffix=".mp4")
        with open(tmp, "wb") as f:
            for chunk in vres.iter_content(1024*1024):
                if chunk: f.write(chunk)
        return tmp
    return None

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
