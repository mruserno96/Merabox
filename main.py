from flask import Flask, request
import requests
import os
import tempfile
import re
import json

BOT_TOKEN = os.getenv("BOT_TOKEN")  # Render dashboard me set karna
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

VALID_DOMAINS = [
    "terabox.fun",
    "terabox.app",
    "1024tera.com",
    "teraboxapp.com",
    "1024terabox.com",
    "1024terabox.com",
]

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Terabox Downloader Bot is running!"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    print("📩 Incoming update:", data)

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        if text == "/start":
            send_message(chat_id, "👋 Welcome!\nSend me a Terabox link and I’ll fetch the highest quality video for you.")
            return {"ok": True}

        if any(domain in text for domain in VALID_DOMAINS):
            send_message(chat_id, "⏳ Processing your Terabox link... Please wait.")
            try:
                video_path = extract_and_download(text)
                if video_path:
                    send_video(chat_id, video_path)
                    os.remove(video_path)
                else:
                    send_message(chat_id, "⚠️ Could not extract valid video link.")
            except Exception as e:
                send_message(chat_id, f"❌ Error: {str(e)}")
        else:
            send_message(chat_id, "⚠️ Invalid link. Please send a valid Terabox link.")

    return {"ok": True}


# ✅ Send text
def send_message(chat_id, text):
    requests.post(f"{API_URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })


# ✅ Send video file
def send_video(chat_id, file_path):
    with open(file_path, "rb") as f:
        requests.post(f"{API_URL}/sendVideo", data={"chat_id": chat_id}, files={"video": f})


# ✅ Extractor (scrape + API fallback)
def extract_and_download(url: str):
    session = requests.Session()
    res = session.get(url, allow_redirects=True, timeout=30)
    html = res.text
    final_url = res.url
    print("🔗 Resolved URL:", final_url)

    video_links = []

    # Try to parse window.playInfo JSON
    json_match = re.search(r'window\.playInfo\s*=\s*(\{.*?\});', html, re.DOTALL)
    if json_match:
        try:
            playinfo = json.loads(json_match.group(1))
            video_links = collect_video_links(playinfo)
        except:
            pass

    # If nothing found → try API fallback
    if not video_links:
        api_links = extract_via_api(html)
        if api_links:
            video_links = api_links

    if not video_links:
        return None

    # Pick highest quality (1080 > 720 > 480 > 360)
    preferred_order = ["1080", "720", "480", "360"]
    selected_url = None
    for quality in preferred_order:
        for link in video_links:
            if quality in link:
                selected_url = link
                break
        if selected_url:
            break
    if not selected_url:
        selected_url = video_links[0]

    print("🎬 Selected video URL:", selected_url)

    # Download video
    video_res = session.get(selected_url, stream=True, timeout=120)
    if video_res.status_code == 200:
        tmp_file = tempfile.mktemp(suffix=".mp4")
        with open(tmp_file, "wb") as f:
            for chunk in video_res.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
        return tmp_file

    return None


# ✅ Collect video links recursively from JSON
def collect_video_links(obj):
    video_links = []
    def _scan(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, str) and (".mp4" in v or ".mkv" in v or ".webm" in v):
                    video_links.append(v.replace("\\u002F", "/"))
                else:
                    _scan(v)
        elif isinstance(o, list):
            for item in o:
                _scan(item)
    _scan(obj)
    return video_links


# ✅ API fallback extractor
def extract_via_api(html):
    try:
        shareid_match = re.search(r"shareid=(\d+)", html)
        uk_match = re.search(r"uk=(\d+)", html)
        if not shareid_match or not uk_match:
            return []

        shareid = shareid_match.group(1)
        uk = uk_match.group(1)

        api_url = f"https://www.terabox.com/api/play/playinfo?shareid={shareid}&uk={uk}"
        print("📡 Calling API:", api_url)
        res = requests.get(api_url, timeout=30)
        data = res.json()

        return collect_video_links(data)
    except Exception as e:
        print("❌ API fallback failed:", e)
        return []


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
