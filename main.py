from flask import Flask, request
import requests
import os
import tempfile
import re

BOT_TOKEN = os.getenv("BOT_TOKEN")  # Render me set karo
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

VALID_DOMAINS = [
    "terabox.fun",
    "terabox.app",
    "1024tera.com",
    "teraboxapp.com",
    "1024terabox.com"
]

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Terabox Downloader Bot is running!"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    print("📩 Incoming update:", data)  # debug console

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        # /start command
        if text == "/start":
            send_message(chat_id, "👋 Welcome!\nSend me a Terabox link and I’ll fetch the highest quality video for you.")
            return {"ok": True}

        # Check for Terabox domains
        if any(domain in text for domain in VALID_DOMAINS):
            send_message(chat_id, "⏳ Processing your Terabox link... Please wait.")
            try:
                video_path = download_terabox_highest_quality(text)

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

# ✅ Extract highest quality video and download
def download_terabox_highest_quality(url: str):
    session = requests.Session()
    res = session.get(url, allow_redirects=True, timeout=30)

    html = res.text
    final_url = res.url
    print("🔗 Resolved URL:", final_url)

    # Extract video links (mp4/mkv/webm/mov)
    matches = re.findall(r'"src":"(https:[^"]+\.(?:mp4|mkv|webm|mov)[^"]*)"', html)

    if not matches:
        return None

    # Clean escape sequences
    video_links = [m.replace("\\u002F", "/") for m in matches]

    # Prefer highest quality (1080p > 720p > 480p > 360p)
    preferred_order = ["1080", "720", "480", "360"]

    selected_url = None
    for quality in preferred_order:
        for link in video_links:
            if quality in link:
                selected_url = link
                break
        if selected_url:
            break

    # If nothing matched, just take first
    if not selected_url:
        selected_url = video_links[0]

    print("🎬 Selected video URL:", selected_url)

    # Download the video
    video_res = session.get(selected_url, stream=True, timeout=120)

    if video_res.status_code == 200:
        tmp_file = tempfile.mktemp(suffix=".mp4")
        with open(tmp_file, "wb") as f:
            for chunk in video_res.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
        return tmp_file

    return None

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
